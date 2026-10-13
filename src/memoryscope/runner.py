"""Execute step-based cases against adapters and record auditable evidence."""

import json
import platform
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from memoryscope import __version__
from memoryscope.adapters import ADAPTERS
from memoryscope.adapters.base import AgentAdapter
from memoryscope.evaluator import EVALUATOR_VERSION, evaluate
from memoryscope.io import contained_path, load_config, load_env_file, load_dataset, sha256_bytes, write_json
from memoryscope.models import BenchmarkCase, Category, MessageStep, NewSessionStep


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceWriter:
    def __init__(self, path: Path, run_id: str) -> None:
        self.stream = path.open("x", encoding="utf-8")
        self.sequence = 0
        self.run_id = run_id

    def emit(self, event: str, agent_id: str | None = None, case_id: str | None = None,
             session_id: str | None = None, **payload: Any) -> int:
        self.sequence += 1
        item = {
            "schema_version": "1.0", "sequence": self.sequence, "timestamp": utc_now(),
            "run_id": self.run_id, "agent_id": agent_id, "case_id": case_id,
            "session_id": session_id, "event": event, "payload": payload,
        }
        self.stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        self.stream.flush()
        return self.sequence

    def close(self) -> None:
        self.stream.close()


def error_details(error: Exception) -> dict[str, str]:
    return {"type": type(error).__name__, "message": str(error)}


STATUSES = ("pass", "fail", "unknown", "error", "unsupported")


def dimension_summary(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-category counts, accuracy over scorable cases and coverage (spec section 10).

    score = 100 * pass / (pass + fail); coverage = 100 * (pass + fail) / planned.
    Any zero denominator gives null. Missing categories are null, never 0 or 100.
    """
    summary: dict[str, dict[str, Any]] = {}
    for category in Category:
        selected = [case for case in cases if case["category"] == category.value]
        counts = {status: sum(case["status"] == status for case in selected) for status in STATUSES}
        planned = len(selected)
        scorable = counts["pass"] + counts["fail"]
        summary[category.value] = {
            "planned": planned, **counts, "scorable": scorable,
            "score": 100.0 * counts["pass"] / scorable if scorable else None,
            "scorable_coverage": 100.0 * scorable / planned if planned else None,
        }
    return summary


def overall_score(summary: dict[str, dict[str, Any]]) -> float | None:
    scores = [item["score"] for item in summary.values()]
    return None if any(score is None for score in scores) else sum(scores) / len(scores)


def _source_digest() -> str:
    root = Path(__file__).parent
    content = b"".join(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes() + b"\0"
                       for path in sorted(root.rglob("*.py")))
    return sha256_bytes(content)


def _versions() -> dict[str, str]:
    versions = {}
    for dependency in ("typer", "pydantic", "PyYAML", "httpx", "matplotlib"):
        try:
            versions[dependency] = metadata.version(dependency)
        except metadata.PackageNotFoundError:
            versions[dependency] = "not-installed"
    return versions


def _os_release() -> dict[str, str] | None:
    try:
        return platform.freedesktop_os_release()
    except OSError:
        return None


def _git_commit(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                                check=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _case_status(probe_results: list[dict[str, Any]]) -> str:
    statuses = [probe["status"] for probe in probe_results]
    if "fail" in statuses:
        return "fail"
    if "unknown" in statuses:
        return "unknown"
    return "pass"


def _run_case(agent: AgentAdapter, agent_id: str, case: BenchmarkCase, writer: EvidenceWriter) -> dict[str, Any]:
    ids = {"agent_id": agent_id, "case_id": case.id}
    probe_results: list[dict[str, Any]] = []
    session_index = 1
    session_id = f"s{session_index}"
    try:
        agent.reset_case(case.id)
        writer.emit("case_reset", **ids, evidence=agent.collect_evidence())
        agent.reset_session(session_id)
        writer.emit("session_reset", **ids, session_id=session_id, reason="case_start",
                    evidence=agent.collect_evidence())
        for index, step in enumerate(case.steps):
            if isinstance(step, MessageStep):
                message = {"role": step.role, "content": step.content}
                writer.emit("message_started", **ids, session_id=session_id, step=index, message=message)
                reply = agent.send_message(step.role, step.content)
                writer.emit("message", **ids, session_id=session_id, step=index, message=message,
                            response=reply, evidence=agent.collect_evidence())
            elif isinstance(step, NewSessionStep):
                writer.emit("before_session_reset", **ids, session_id=session_id, step=index,
                            evidence=agent.collect_evidence())
                session_index += 1
                session_id = f"s{session_index}"
                agent.reset_session(session_id)
                writer.emit("session_reset", **ids, session_id=session_id, step=index,
                            reason="new_session_step", evidence=agent.collect_evidence())
            else:
                # Only the public probe is passed to the adapter; expected stays in the evaluator.
                public = step.public()
                writer.emit("probe_started", **ids, session_id=session_id, step=index, probe_id=step.id,
                            probe=public.model_dump(), evidence=agent.collect_evidence())
                response = agent.execute_task(public.model_copy(deep=True))
                if not isinstance(response, str):
                    raise TypeError("execute_task must return a string")
                writer.emit("probe", **ids, session_id=session_id, step=index, probe_id=step.id,
                            probe=public.model_dump(), response=response, evidence=agent.collect_evidence())
                evaluation = evaluate(response, step.expected, step.evaluation)
                event = writer.emit("evaluation", **ids, session_id=session_id, step=index,
                                    probe_id=step.id, evaluation=evaluation)
                probe_results.append({"probe_id": step.id, "session_id": session_id, "response": response,
                                      "status": evaluation["status"], "evaluation": evaluation,
                                      "evaluation_event": event})
    except Exception as error:
        detail = error_details(error)
        writer.emit("case_error", **ids, session_id=session_id, error=detail)
        return {"status": "error", "probes": probe_results, "error": detail}
    return {"status": _case_status(probe_results), "probes": probe_results}


def run_benchmark(config_path: Path) -> tuple[Path, dict[str, Any]]:
    loaded = load_config(config_path)
    dataset = load_dataset(loaded.dataset, loaded.root)
    env_names = load_env_file(loaded.root)
    # Validate every input before creating outputs; each invocation owns a new directory.
    loaded.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    contained_path(loaded.output_dir, loaded.root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:12]
    run_dir = loaded.output_dir / run_id
    run_dir.mkdir(mode=0o700)
    with (run_dir / "config.snapshot.yaml").open("xb") as stream:
        stream.write(loaded.raw)
    with (run_dir / "dataset.snapshot.jsonl").open("xb") as stream:
        stream.write(dataset.snapshot)
    started_at = utc_now()
    # Sandboxes live outside the project so agents cannot pick up project files such as AGENTS.md.
    sandbox_root = Path(tempfile.mkdtemp(prefix=f"memoryscope-{run_id}-"))
    writer = EvidenceWriter(run_dir / "events.jsonl", run_id)
    agent_results: list[dict[str, Any]] = []
    writer.emit("run_started", sandbox_root=str(sandbox_root))
    try:
        for agent_config in loaded.config.agents:
            agent: AgentAdapter | None = None
            synthetic = True
            case_results: list[dict[str, Any]] = []
            agent_errors: list[dict[str, str]] = []
            description: dict[str, Any] = {}
            try:
                agent = ADAPTERS[agent_config.type](agent_config)
                synthetic = agent.synthetic
                description = agent.describe()
                sandbox = sandbox_root / agent_config.id
                sandbox.mkdir(mode=0o700)
                agent.start(run_id, agent_config.id, sandbox)
                writer.emit("agent_started", agent_id=agent_config.id, adapter_type=agent_config.type,
                            describe=description, evidence=agent.collect_evidence())
                for case in dataset.cases:
                    begin = writer.sequence + 1
                    began = time.perf_counter()
                    result: dict[str, Any] = {
                        "case_id": case.id, "category": case.category.value, "synthetic": synthetic,
                        "namespace": f"{run_id}/{agent_config.id}/{case.id}",
                        "protocol": case.protocol.model_dump(),
                    }
                    missing = sorted(c.value for c in case.metadata.requires if c not in agent.capabilities)
                    if missing:
                        writer.emit("case_unsupported", agent_id=agent_config.id, case_id=case.id,
                                    missing_capabilities=missing)
                        result.update(status="unsupported", probes=[], missing_capabilities=missing)
                    else:
                        result.update(_run_case(agent, agent_config.id, case, writer))
                    status = result["status"]
                    result["score"] = 1.0 if status == "pass" else 0.0 if status == "fail" else None
                    result["duration_seconds"] = time.perf_counter() - began
                    result["evidence"] = {"file": "events.jsonl", "first_sequence": begin, "last_sequence": writer.sequence}
                    case_results.append(result)
            except Exception as error:
                detail = error_details(error)
                agent_errors.append(detail)
                writer.emit("agent_error", agent_id=agent_config.id, error=detail)
                done = {case["case_id"] for case in case_results}
                for case in dataset.cases:
                    if case.id not in done:
                        case_results.append({"case_id": case.id, "category": case.category.value,
                                             "synthetic": synthetic, "status": "error", "score": None,
                                             "probes": [], "error": detail})
            finally:
                if agent is not None:
                    try:
                        agent.shutdown()
                        writer.emit("agent_shutdown", agent_id=agent_config.id, evidence=agent.collect_evidence())
                    except Exception as error:
                        detail = error_details(error)
                        agent_errors.append(detail)
                        writer.emit("shutdown_error", agent_id=agent_config.id, error=detail)
            summary = dimension_summary(case_results)
            failed = bool(agent_errors) or any(case["status"] == "error" for case in case_results)
            agent_results.append({
                "agent_id": agent_config.id, "adapter_type": agent_config.type, "synthetic": synthetic,
                "describe": description, "status": "failed" if failed else "completed",
                "cases": case_results, "dimensions": summary,
                "dimension_scores": {name: item["score"] for name, item in summary.items()},
                "overall_score": overall_score(summary), "errors": agent_errors,
            })
        status = "failed" if any(agent["status"] == "failed" for agent in agent_results) else "completed"
        synthetic_run = all(agent["synthetic"] for agent in agent_results)
        results = {
            "schema_version": "1.1", "run_id": run_id, "status": status, "synthetic": synthetic_run,
            "purpose": "synthetic_pipeline_validation" if synthetic_run else "agent_evaluation",
            "dataset_case_count": len(dataset.cases), "agent_results": agent_results,
            "scoring_note": "Dimension score = 100*pass/(pass+fail); unknown/error/unsupported are counted separately "
                            "and lower coverage. Overall is the mean of six dimensions and null if any is null.",
        }
        write_json(run_dir / "results.json", results)
        writer.emit("run_finished", status=status, synthetic=synthetic_run)
    finally:
        writer.close()
    files = {}
    for name in ("config.snapshot.yaml", "dataset.snapshot.jsonl", "events.jsonl", "results.json"):
        files[name] = {"sha256": sha256_bytes((run_dir / name).read_bytes())}
    write_json(run_dir / "metadata.json", {
        "schema_version": "1.1", "run_id": run_id, "status": status,
        "started_at": started_at, "finished_at": utc_now(), "synthetic": synthetic_run,
        "purpose": results["purpose"], "package_version": __version__,
        "source_sha256": _source_digest(), "python_version": sys.version,
        "platform": platform.platform(), "os_release": _os_release(),
        "git_commit": _git_commit(loaded.root), "dependencies": _versions(),
        "evaluator": {"version": EVALUATOR_VERSION, "types": ["contains", "answer_line"], "case_sensitive": False,
                      "case_score_scale": [0, 1], "dimension_score_scale": [0, 100]},
        "seed": loaded.config.seed,
        "config_path": str(loaded.path.relative_to(loaded.root)),
        "input_config_sha256": sha256_bytes(loaded.raw), "dataset_sources": dataset.sources,
        "sandbox_root": str(sandbox_root), "env_file_variables_loaded": env_names,
        "artifacts": files, "event_count": writer.sequence,
        "limitations": ["rule scoring only (no LLM judge)", "not validated on openKylin"],
    })
    return run_dir, results
