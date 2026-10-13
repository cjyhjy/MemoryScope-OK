"""Re-grade a finished run from its saved evidence with the current evaluator.

Agents are never called again. Probe responses come from ``probe`` events;
memory/file checks reuse the text captured in their ``evaluation`` events.
The original results stay untouched; a new ``rescore-<time>/`` directory holds
the recomputed results and every status change.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memoryscope.evaluator import EVALUATOR_VERSION, evaluate
from memoryscope.io import write_json
from memoryscope.models import BenchmarkCase, CheckFileStep, CheckMemoryStep, Evaluation, ProbeStep
from memoryscope.runner import _case_status, dimension_summary, overall_score


def rescore_run(run_dir: Path) -> tuple[Path, dict[str, Any]]:
    original = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    cases = {}
    for line in (run_dir / "dataset.snapshot.jsonl").read_text(encoding="utf-8").splitlines():
        case = BenchmarkCase.model_validate(json.loads(line))
        cases[case.id] = case
    responses: dict[tuple[str, str, str], str] = {}
    captured: dict[tuple[str, str, str], str | None] = {}
    for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        payload = event["payload"]
        key = (event["agent_id"], event["case_id"], payload.get("probe_id"))
        if event["event"] == "probe":
            responses[key] = payload["response"]
        elif event["event"] == "evaluation" and payload["evaluation"].get("type") in ("check_memory", "check_file"):
            captured[key] = payload["evaluation"].get("scored_text")
    changes = []
    agents = []
    for agent in original["agent_results"]:
        new_cases = []
        for case_result in agent["cases"]:
            updated = dict(case_result)
            if case_result["status"] in ("pass", "fail", "unknown"):
                case = cases[case_result["case_id"]]
                steps = {step.id: step for step in case.steps if hasattr(step, "id")}
                probes = []
                for check in case_result["probes"]:
                    step = steps[check["probe_id"]]
                    key = (agent["agent_id"], case.id, step.id)
                    if isinstance(step, ProbeStep):
                        evaluation = evaluate(responses[key], step.expected, step.evaluation)
                    elif captured.get(key) is not None:
                        evaluation = evaluate(captured[key], step.expected, Evaluation(type="contains"))
                    else:
                        evaluation = check["evaluation"]
                    if evaluation["status"] != check["status"]:
                        changes.append({"agent_id": agent["agent_id"], "case_id": case.id, "check_id": step.id,
                                        "old": check["status"], "new": evaluation["status"],
                                        "old_version": (check["evaluation"] or {}).get("version"),
                                        "new_version": EVALUATOR_VERSION})
                    probes.append(dict(check, status=evaluation["status"], evaluation=evaluation,
                                       original_status=check["status"]))
                status = _case_status(probes)
                updated.update(probes=probes, status=status, original_status=case_result["status"],
                               score=1.0 if status == "pass" else 0.0 if status == "fail" else None)
            new_cases.append(updated)
        summary = dimension_summary(new_cases)
        agents.append(dict(agent, cases=new_cases, dimensions=summary,
                           dimension_scores={name: item["score"] for name, item in summary.items()},
                           overall_score=overall_score(summary)))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = run_dir / f"rescore-{stamp}"
    out.mkdir()
    result = dict(original, agent_results=agents, rescored_from=original["run_id"],
                  evaluator_version=EVALUATOR_VERSION, status_changes=changes)
    write_json(out / "results.json", result)
    return out, result
