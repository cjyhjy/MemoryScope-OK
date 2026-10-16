"""P0 paired protocol, deliberately separate from historical result schema 1.1.

Only the audited synthetic fixture executes. No .env loading, real adapter
startup, model calls, implicit file retention or pooling of storage and answers.
"""

import json
import platform
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memoryscope.adapters.base import AgentAdapter
from memoryscope.adapters.paired_demo import STATE_SURFACES, PairedDemoAgent
from memoryscope.evaluator import EVALUATOR_VERSION, evaluate
from memoryscope.io import InputError, load_config, load_dataset, sha256_bytes, write_json
from memoryscope.models import CheckFileStep, CheckMemoryStep, Evaluation, Expected, MessageStep, NewSessionStep, ProbeStep
from memoryscope.runner import EvidenceWriter, _git_commit, _os_release, _source_digest, _versions, error_details, utc_now

ARMS = ("memory_on", "memory_off")
PROTOCOL_VERSION = "paired-1.0"


def _public_schedule(case) -> list[dict[str, Any]]:
    return [step.public().model_dump() if isinstance(step, ProbeStep) else step.model_dump()
            for step in case.steps if isinstance(step, (MessageStep, NewSessionStep, ProbeStep))]


def _verified(audit: dict[str, Any], memory_enabled: bool) -> bool:
    """Check evidence content as well as the fixture's assertion."""
    before, after = audit.get("before", {}), audit.get("after", {})
    return (audit.get("status") == "verified" and audit.get("memory_enabled") is memory_enabled
            and audit.get("proof_scope") == "controlled_synthetic_state_inventory"
            and audit.get("retained_workspace_files") == []
            and before.get("surfaces") == after.get("surfaces") == STATE_SURFACES
            and isinstance(before.get("context"), list) and isinstance(before.get("sandbox_files"), list)
            and after.get("context") == [] and after.get("sandbox_files") == []
            and isinstance(before.get("memory"), list)
            and after.get("memory") == (before["memory"] if memory_enabled else []))


def _arm(case, config, arm: str, sandbox: Path, writer: EvidenceWriter) -> dict[str, Any]:
    agent = PairedDemoAgent(config)
    enabled = arm == "memory_on"
    ids = {"agent_id": config.id, "case_id": case.id, "arm": arm}
    result: dict[str, Any] = {"status": "completed", "isolation_verified": False,
                              "calls": 0, "answers": [], "storage_checks": [], "file_checks": []}
    session = 0
    audits: list[int] = []
    try:
        agent.start(writer.run_id, f"{config.id}.{arm}", sandbox)
        agent.reset_case(case.id)

        def isolate() -> bool:
            nonlocal session
            session += 1
            audit = agent.isolate_paired_session(f"s{session}", memory_enabled=enabled)
            event = writer.emit("paired_isolation", **ids, session_id=f"s{session}", audit=audit)
            audits.append(event)
            return _verified(audit, enabled)

        if not isolate():
            result["status"] = "unknown"
        else:
            result["isolation_verified"] = True
            for index, step in enumerate(case.steps):
                if isinstance(step, NewSessionStep):
                    if not isolate():
                        result.update(status="unknown", isolation_verified=False)
                        break  # Do not probe a possibly contaminated arm.
                elif isinstance(step, MessageStep):
                    message = {"role": step.role, "content": step.content}
                    writer.emit("message_started", **ids, session_id=f"s{session}", step=index, message=message)
                    reply = agent.send_message(**message)
                    result["calls"] += 1
                    writer.emit("message", **ids, session_id=f"s{session}", step=index, message=message, response=reply,
                                evidence=agent.collect_evidence())
                elif isinstance(step, ProbeStep):
                    public = step.public()
                    writer.emit("probe_started", **ids, session_id=f"s{session}", step=index, probe_id=step.id,
                                probe=public.model_dump(), evidence=agent.collect_evidence())
                    response = agent.execute_task(public)
                    result["calls"] += 1
                    if not isinstance(response, str):
                        raise TypeError("execute_task must return a string")
                    correctness = evaluate(response, step.expected, step.evaluation)
                    # This is lexical non-use in the declared answer scope, not
                    # a semantic assertion of invalidation or storage deletion.
                    non_use = (evaluate(response, Expected(exclude=step.expected.exclude), step.evaluation)
                               if step.expected.exclude else None)
                    event = writer.emit("probe", **ids, session_id=f"s{session}", step=index, probe_id=step.id,
                                        probe=public.model_dump(), response=response,
                                        answer_correct=correctness, forbidden_value_not_used=non_use)
                    result["answers"].append({"probe_id": step.id, "response": response,
                                               "answer_correct": correctness,
                                               "forbidden_value_not_used": non_use, "event": event})
                elif isinstance(step, (CheckMemoryStep, CheckFileStep)):
                    stored = agent.memory_text() if isinstance(step, CheckMemoryStep) else agent.read_workspace_file(step.path)
                    evaluation = (evaluate(stored, step.expected, Evaluation()) if stored is not None else
                                  {"status": "unknown", "score": None, "explanation": "Store/file not observable."})
                    item = {"check_id": step.id, "scope": "demo_memory_list" if isinstance(step, CheckMemoryStep)
                            else "workspace_file", "evaluation": evaluation,
                            "specified_store_absence": (evaluate(stored, Expected(exclude=step.expected.exclude), Evaluation())
                                                        if stored is not None and step.expected.exclude else None),
                            "global_deletion_proven": False}
                    item["specified_store_deletion"] = (
                        item["specified_store_absence"] if enabled and item["specified_store_absence"] is not None
                        else {"status": "unknown", "score": None,
                              "explanation": "Harness reset/absence without a deletion constraint cannot establish Agent deletion."})
                    item["event"] = writer.emit("storage_check", **ids, session_id=f"s{session}", step=index, check=item.copy())
                    result["storage_checks" if isinstance(step, CheckMemoryStep) else "file_checks"].append(item)
    except Exception as error:
        result.update(status="error", error=error_details(error), isolation_verified=False)
        writer.emit("arm_error", **ids, error=result["error"])
    finally:
        try:
            agent.shutdown()
        except Exception as error:
            result.update(status="error", error=error_details(error), isolation_verified=False)
            writer.emit("shutdown_error", **ids, error=result["error"])
    result["isolation_events"] = audits
    writer.emit("arm_finished", **ids, status=result["status"], calls=result["calls"])
    return result


def _comparison(arms: dict[str, Any], planned: int, calls: int) -> dict[str, Any]:
    valid = all(arms[name]["status"] == "completed" and arms[name]["isolation_verified"]
                and arms[name]["calls"] == calls and len(arms[name]["answers"]) == planned for name in ARMS)
    deltas = []
    if valid:
        for on, off in zip(arms["memory_on"]["answers"], arms["memory_off"]["answers"], strict=True):
            if on["probe_id"] != off["probe_id"]:
                valid = False
                break
            if all(item["answer_correct"]["status"] in ("pass", "fail") for item in (on, off)):
                deltas.append(on["answer_correct"]["score"] - off["answer_correct"]["score"])
    return {"comparable": valid, "planned_public_probes": planned,
            "scorable_pairs": len(deltas) if valid else 0,
            "public_pair_coverage": len(deltas) / planned if valid else 0.0,
            "public_score_delta_on_minus_off": sum(deltas) / len(deltas) if valid and deltas else None,
            "attribution": "pure_declared_memory_with_no_file_reuse" if valid else "unknown",
            "storage_checks_in_public_metric": False}


def run_paired(config_path: Path) -> tuple[Path, dict[str, Any]]:
    loaded = load_config(config_path)
    protocol = loaded.config.paired
    if protocol is None:
        raise InputError("run-paired requires an explicit paired protocol declaration")
    dataset = load_dataset(loaded.dataset, loaded.root)
    for case in dataset.cases:
        calls = sum(isinstance(step, (MessageStep, ProbeStep)) for step in case.steps)
        if calls > protocol.max_calls_per_arm:
            raise InputError(f"{case.id}: {calls} calls exceed the identical per-arm budget")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-paired-" + uuid.uuid4().hex[:12]
    loaded.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = loaded.output_dir / run_id
    run_dir.mkdir(mode=0o700)
    (run_dir / "config.snapshot.yaml").write_bytes(loaded.raw)
    (run_dir / "dataset.snapshot.jsonl").write_bytes(dataset.snapshot)
    started = utc_now()
    source_digest, commit = _source_digest(), _git_commit(loaded.root)
    writer = EvidenceWriter(run_dir / "events.jsonl", run_id)
    pairs = []
    writer.emit("run_started", protocol=PROTOCOL_VERSION, declared=protocol.model_dump())
    try:
        with tempfile.TemporaryDirectory(prefix="memoryscope-paired-") as temporary:
            for config in loaded.config.agents:
                for case in dataset.cases:
                    schedule = _public_schedule(case)
                    calls = sum(isinstance(step, (MessageStep, ProbeStep)) for step in case.steps)
                    pair: dict[str, Any] = {"agent_id": config.id, "adapter_type": config.type,
                                            "case_id": case.id, "review_status": case.metadata.review_status,
                                            "synthetic": config.type == "demo", "arms": {},
                                            "controls": {"agent_config": config.model_dump(mode="json"),
                                                         "public_schedule_sha256": sha256_bytes(json.dumps(schedule, ensure_ascii=False, sort_keys=True).encode()),
                                                         "seed": loaded.config.seed, "planned_calls_per_arm": calls,
                                                         "max_calls_per_arm": protocol.max_calls_per_arm,
                                                         "retained_workspace_files": [], "order": list(ARMS)}}
                    missing = sorted(c.value for c in case.required_capabilities if c not in PairedDemoAgent.capabilities)
                    if config.type != "demo" or config.model is not None or missing:
                        # Do not construct/start a real adapter, discover binaries
                        # or read credentials, even if they exist on this host.
                        reason = (AgentAdapter.paired_isolation_support()["reason"] if config.type != "demo" else
                                  "The controlled Demo has no model; configured model cannot be honored." if config.model is not None else
                                  "Controlled Demo lacks required capabilities: " + ", ".join(missing))
                        pair.update(status="unsupported", reason=reason, missing_capabilities=missing,
                                    comparison={"comparable": False, "public_score_delta_on_minus_off": None})
                        writer.emit("pair_unsupported", agent_id=config.id, case_id=case.id, reason=pair["reason"])
                    else:
                        pair["controls"]["adapter_contract"] = PairedDemoAgent(config).paired_isolation_support()
                        for arm in ARMS:
                            sandbox = Path(temporary) / uuid.uuid4().hex
                            sandbox.mkdir(mode=0o700)
                            pair["arms"][arm] = _arm(case, config, arm, sandbox, writer)
                        pair["comparison"] = _comparison(pair["arms"], len(case.probes), calls)
                        states = [item["status"] for item in pair["arms"].values()]
                        pair["status"] = "error" if "error" in states else "completed" if pair["comparison"]["comparable"] else "unknown"
                    pairs.append(pair)
            result = {"schema_version": PROTOCOL_VERSION, "run_id": run_id,
                      "purpose": "paired_protocol_validation", "executed_real_agents": 0,
                      "synthetic": all(pair["synthetic"] for pair in pairs),
                      "status": "failed" if any(pair["status"] == "error" for pair in pairs) else "completed",
                      "pair_status_counts": {state: sum(pair["status"] == state for pair in pairs)
                                             for state in ("completed", "unknown", "error", "unsupported")},
                      "pairs": pairs, "overall_score": None,
                      "limitations": ["Only the controlled synthetic fixture executes; no real product-memory comparison.",
                                      "Fixed on/off order, no repeated sampling or statistical inference.",
                                      "Forbidden-value non-use is lexical in the declared answer scope; it does not prove semantic invalidation.",
                                      "Store absence is limited to demo_memory_list; it does not prove global deletion.",
                                      "File retention/reuse unsupported; no full six-dimension score or legacy GUI/report/rescore integration."]}
            write_json(run_dir / "results.json", result)
            writer.emit("run_finished", status=result["status"])
    finally:
        writer.close()
    # A compact standalone report, intentionally outside legacy report handling.
    lines = ["# P0 paired protocol validation", "", "Controlled synthetic runs only; real adapters are unsupported.", "",
             "| Agent | Case | Execution | Comparable | Public delta (on − off) |", "| --- | --- | --- | --- | --- |"]
    for pair in pairs:
        compare = pair["comparison"]
        lines.append(f"| {pair['agent_id']} | {pair['case_id']} | {pair['status']} | {compare['comparable']} | {compare['public_score_delta_on_minus_off']} |")
    lines += ["", "## Public answer checks", "", "| Agent / case | Arm | Probe | Answer correct | Forbidden value not used (lexical) |",
              "| --- | --- | --- | --- | --- |"]
    for pair in pairs:
        for arm, execution in pair["arms"].items():
            for answer in execution["answers"]:
                non_use = answer["forbidden_value_not_used"]
                lines.append(f"| {pair['agent_id']} / {pair['case_id']} | {arm} | {answer['probe_id']} | {answer['answer_correct']['status']} | {non_use['status'] if non_use else 'not requested'} |")
    lines += ["", "## Specified-store checks (excluded from public delta)", "",
              "| Agent / case | Arm | Check | Content constraint | Specified-store deletion | Global deletion proven |",
              "| --- | --- | --- | --- | --- | --- |"]
    for pair in pairs:
        for arm, execution in pair["arms"].items():
            for check in execution["storage_checks"]:
                lines.append(f"| {pair['agent_id']} / {pair['case_id']} | {arm} | {check['check_id']} | {check['evaluation']['status']} | {check['specified_store_deletion']['status']} | false |")
    lines += ["", "Answer correctness, lexical forbidden-value non-use and specified-store absence are separate in results.json.",
              "Storage checks never enter the public delta. Execution completed does not imply storage or answers pass.",
              "", *result["limitations"]]
    (run_dir / "paired-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    names = ("config.snapshot.yaml", "dataset.snapshot.jsonl", "events.jsonl", "results.json", "paired-report.md")
    write_json(run_dir / "metadata.json", {
        "schema_version": PROTOCOL_VERSION, "run_id": run_id, "started_at": started, "finished_at": utc_now(),
        "status": result["status"], "purpose": result["purpose"], "executed_real_agents": 0,
        "git_commit": commit, "source_sha256": source_digest, "os_release": _os_release(),
        "source_identity_note": "git_commit identifies HEAD; source_sha256 identifies the executed Python working tree, including uncommitted edits.",
        "python_version": platform.python_version(), "platform": platform.platform(),
        "dependencies": _versions(), "evaluator_version": EVALUATOR_VERSION,
        "protocol": protocol.model_dump(), "dataset_sources": dataset.sources,
        "event_count": writer.sequence, "temporary_sandboxes_removed": True,
        "artifacts": {name: {"sha256": sha256_bytes((run_dir / name).read_bytes())} for name in names}})
    return run_dir, result
