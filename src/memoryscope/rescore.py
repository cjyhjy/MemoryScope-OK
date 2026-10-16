"""Re-grade a finished run from its saved evidence with the current evaluator.

Agents are never called again. Probe responses come from ``probe`` events;
memory/file checks reuse the text captured in their ``evaluation`` events.
The original results stay untouched; a new ``rescore-<time>/`` directory holds
the recomputed results and every status change.
"""

import json
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memoryscope.evaluator import EVALUATOR_VERSION, evaluate
from memoryscope.io import sha256_bytes, write_json
from memoryscope.models import BenchmarkCase, CheckFileStep, CheckMemoryStep, Evaluation, ProbeStep
from memoryscope.runner import _case_status, dimension_summary, overall_score
from memoryscope.reporting import load_results


def rescore_run(run_dir: Path) -> tuple[Path, dict[str, Any]]:
    original = load_results(run_dir)
    sources = {}
    for name in ("results.json", "dataset.snapshot.jsonl", "events.jsonl", "config.snapshot.yaml", "metadata.json"):
        path = run_dir / name
        if path.is_file():
            sources[name] = path.read_bytes()
    source_hashes = {name: sha256_bytes(raw) for name, raw in sources.items()}
    cases = {}
    for line in sources["dataset.snapshot.jsonl"].decode("utf-8").splitlines():
        case = BenchmarkCase.model_validate(json.loads(line))
        cases[case.id] = case
    responses: dict[tuple[str, str, str], str] = {}
    captured: dict[tuple[str, str, str], str | None] = {}
    for sequence, line in enumerate(sources["events.jsonl"].decode("utf-8").splitlines(), 1):
        event = json.loads(line)
        if (event.get("schema_version") != "1.0" or event.get("run_id") != original["run_id"]
                or event.get("sequence") != sequence):
            raise ValueError("invalid evidence version, run ID or event sequence")
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
    out = run_dir / f"rescore-{stamp}-{uuid.uuid4().hex[:8]}"
    result = dict(original, agent_results=agents, rescored_from=original["run_id"],
                  evaluator_version=EVALUATOR_VERSION, status_changes=changes)
    staged = Path(tempfile.mkdtemp(prefix=".rescore-", dir=run_dir))
    try:
        # Keep evidence references local and make re-scoring the revision work
        # without agents or implicit access to a parent directory.
        for name in ("dataset.snapshot.jsonl", "events.jsonl", "config.snapshot.yaml"):
            if name in sources:
                (staged / name).write_bytes(sources[name])
        write_json(staged / "results.json", result)
        original_metadata = json.loads(sources["metadata.json"]) if "metadata.json" in sources else {}
        metadata = dict(original_metadata, schema_version="1.1", run_id=result["run_id"],
                        status=result["status"], synthetic=result["synthetic"],
                        rescore={"timestamp": stamp, "evaluator_version": EVALUATOR_VERSION,
                                 "source_run_id": original["run_id"], "source_artifacts": source_hashes,
                                 "source_evaluator": original_metadata.get("evaluator")})
        metadata["evaluator"] = {**original_metadata.get("evaluator", {}), "version": EVALUATOR_VERSION}
        metadata["artifacts"] = {path.name: {"sha256": sha256_bytes(path.read_bytes())}
                                 for path in staged.iterdir()}
        write_json(staged / "metadata.json", metadata)
        staged.rename(out)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return out, result
