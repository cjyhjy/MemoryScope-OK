"""Offline causal-control regressions. No real adapter or API is invoked."""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from memoryscope.adapters import ADAPTERS
from memoryscope.adapters.paired_demo import PairedDemoAgent
from memoryscope.cli import app
from memoryscope.io import InputError, sha256_bytes
from memoryscope.models import Probe
from memoryscope.paired import run_paired
from memoryscope.runner import run_benchmark

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def paired_project(project):
    (project / "datasets/paired").mkdir()
    (project / "datasets/paired/dynamic-update-hard-001.jsonl").write_bytes(
        (ROOT / "datasets/paired/dynamic-update-hard-001.jsonl").read_bytes())
    config = project / "configs/paired.yaml"
    config.write_bytes((ROOT / "configs/paired-demo.yaml").read_bytes())
    return config


def events(path):
    return [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]


def test_actual_paired_closed_loop_and_separate_storage_failure(paired_project):
    path, result = run_paired(paired_project)
    pair = result["pairs"][0]
    assert result["executed_real_agents"] == 0 and result["synthetic"] is True
    assert result["overall_score"] is None and pair["review_status"] == "draft"
    on, off = (pair["arms"][arm] for arm in ("memory_on", "memory_off"))
    assert on["calls"] == off["calls"] == 7
    assert on["answers"][0]["answer_correct"]["status"] == "pass"
    assert on["answers"][0]["forbidden_value_not_used"]["status"] == "pass"
    assert on["storage_checks"][0]["specified_store_absence"]["status"] == "fail"
    assert on["storage_checks"][0]["specified_store_deletion"]["status"] == "fail"
    assert on["storage_checks"][0]["evaluation"]["status"] == "fail"
    assert off["answers"][0]["answer_correct"]["status"] == "fail"
    assert off["storage_checks"][0]["specified_store_absence"]["status"] == "pass"
    assert off["storage_checks"][0]["specified_store_deletion"]["status"] == "unknown"
    assert off["storage_checks"][0]["evaluation"]["status"] == "fail"  # new value also gone
    assert not any(check["global_deletion_proven"] for arm in (on, off) for check in arm["storage_checks"])
    assert pair["comparison"]["public_score_delta_on_minus_off"] == 1.0
    assert pair["comparison"]["scorable_pairs"] == 1
    assert pair["comparison"]["storage_checks_in_public_metric"] is False
    recorded = events(path)
    assert [e["sequence"] for e in recorded] == list(range(1, len(recorded) + 1))
    for arm in ("memory_on", "memory_off"):
        audits = [e["payload"]["audit"] for e in recorded if e["event"] == "paired_isolation" and e["payload"]["arm"] == arm]
        assert len(audits) == 4
        assert all(a["after"]["context"] == [] and a["after"]["sandbox_files"] == [] for a in audits)
        if arm == "memory_off":
            assert all(a["after"]["memory"] == [] for a in audits)
        else:
            assert audits[-1]["after"]["memory"]
    # Actual message/probe inputs, not just configuration equality.
    def inputs(arm):
        return [(e["event"], e["payload"].get("message", e["payload"].get("probe"))) for e in recorded
                if e["payload"].get("arm") == arm and e["event"] in ("message_started", "probe_started")]
    assert inputs("memory_on") == inputs("memory_off")
    probe = next(e["payload"]["probe"] for e in recorded if e["event"] == "probe_started")
    assert set(probe) == {"type", "content"} and not any(t in probe["content"] for t in ("517", "571", "632", "804"))
    metadata = json.loads((path / "metadata.json").read_text())
    assert metadata["temporary_sandboxes_removed"] is True
    for name, item in metadata["artifacts"].items():
        assert sha256_bytes((path / name).read_bytes()) == item["sha256"]
    original = (path / "results.json").read_bytes()
    second, _ = run_paired(paired_project)
    assert second != path and (path / "results.json").read_bytes() == original


@pytest.mark.parametrize("memory_enabled", [True, False])
def test_all_answer_carrying_surfaces_removed(tmp_path, memory_enabled):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    agent = PairedDemoAgent()
    agent.start("run", "agent", sandbox)
    agent.reset_case("case")
    agent.reset_session("s1")
    agent.send_message("user", "记住：青岚项目的合成标记是 SENTINEL-9817。")
    for name in ("MEMORY.md", "workspace/answer.txt", "home/.hidden", "cache/answer", "session.db", ".other"):
        path = sandbox / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SENTINEL-9817")
    outside = tmp_path / "outside-answer"
    outside.write_text("HOST-SENTINEL")
    (sandbox / "home/link").symlink_to(outside)
    audit = agent.isolate_paired_session("s2", memory_enabled=memory_enabled)
    assert len(audit["before"]["sandbox_files"]) >= 7
    assert audit["before"]["context"] and audit["before"]["memory"]
    assert audit["after"]["sandbox_files"] == [] and audit["after"]["context"] == []
    assert bool(audit["after"]["memory"]) is memory_enabled
    assert outside.read_text() == "HOST-SENTINEL"  # link not followed or deleted
    answer = agent.execute_task(Probe(content="青岚项目的合成标记是什么？"))
    assert ("SENTINEL-9817" in answer) is memory_enabled
    agent.reset_case("other-case")
    agent.reset_session("s1")
    assert "SENTINEL-9817" not in agent.execute_task(Probe(content="青岚项目的合成标记是什么？"))
    agent.shutdown()


@pytest.mark.parametrize("agent_type", ["codex", "dsh", "command"])
def test_unproven_real_and_command_agents_never_start(paired_project, monkeypatch, agent_type):
    data = yaml.safe_load(paired_project.read_text())
    config = {"id": "blocked", "type": agent_type}
    if agent_type == "command":
        config["command"] = ["must-not-execute", "{prompt}"]
    data["agents"] = [config]
    paired_project.write_text(yaml.safe_dump(data))
    def forbidden(*args, **kwargs):
        pytest.fail("real adapter must not be constructed or invoked")
    monkeypatch.setitem(ADAPTERS, agent_type, forbidden)
    (paired_project.parents[1] / ".env").write_text("invalid dotenv must not be loaded")
    monkeypatch.setenv("MEMORYSCOPE_AGENT_HOME", "/must-not-be-trusted")
    path, result = run_paired(paired_project)
    pair = result["pairs"][0]
    assert pair["status"] == "unsupported" and pair["arms"] == {}
    assert pair["comparison"]["public_score_delta_on_minus_off"] is None
    assert not any(e["event"] in ("message_started", "probe_started") for e in events(path))


@pytest.mark.parametrize("failure", ["start", "execute_task", "shutdown"])
def test_errors_saved_without_public_gain(paired_project, monkeypatch, failure):
    def broken(*args, **kwargs):
        raise RuntimeError("intentional paired fixture failure")
    monkeypatch.setattr(PairedDemoAgent, failure, broken)
    path, result = run_paired(paired_project)
    assert result["status"] == "failed" and path.joinpath("metadata.json").exists()
    pair = result["pairs"][0]
    assert pair["status"] == "error" and pair["comparison"]["public_score_delta_on_minus_off"] is None


@pytest.mark.parametrize("corrupt", ["claim_only", "context_leak", "memory_leak", "file_leak", "missing_surface"])
def test_missing_or_false_isolation_evidence_stops_probe(paired_project, monkeypatch, corrupt):
    original = PairedDemoAgent.isolate_paired_session
    def bad(self, session_id, *, memory_enabled):
        audit = original(self, session_id, memory_enabled=memory_enabled)
        if session_id == "s2":
            if corrupt == "claim_only":
                return {"status": "verified"}
            if corrupt == "context_leak":
                audit["after"]["context"] = [{"content": "leaked"}]
            if corrupt == "memory_leak" and not memory_enabled:
                audit["after"]["memory"] = ["leaked"]
            if corrupt == "file_leak":
                audit["after"]["sandbox_files"] = [{"path": "home/session.db"}]
            if corrupt == "missing_surface":
                audit["after"]["surfaces"].pop("session_database")
        return audit
    monkeypatch.setattr(PairedDemoAgent, "isolate_paired_session", bad)
    _, result = run_paired(paired_project)
    pair = result["pairs"][0]
    assert pair["status"] == "unknown" and not pair["comparison"]["comparable"]
    assert pair["comparison"]["public_score_delta_on_minus_off"] is None
    assert pair["arms"]["memory_off"]["answers"] == []


def test_explicit_protocol_budget_and_no_implicit_retained_files(paired_project):
    data = yaml.safe_load(paired_project.read_text())
    with pytest.raises(ValueError, match="requires run-paired"):
        run_benchmark(paired_project)
    for patch, message in (({"max_calls_per_arm": 1}, "budget"),
                           ({"retained_workspace_files": ["answer.txt"]}, "file reuse is unsupported")):
        updated = {**data, "paired": {**data["paired"], **patch}}
        paired_project.write_text(yaml.safe_dump(updated))
        with pytest.raises(InputError, match=message):
            run_paired(paired_project)
    data.pop("paired")
    paired_project.write_text(yaml.safe_dump(data))
    with pytest.raises(InputError, match="explicit paired"):
        run_paired(paired_project)
    assert not (paired_project.parents[1] / "runs").exists()


def test_grader_only_terms_never_reach_fixture(paired_project, monkeypatch):
    dataset = paired_project.parents[1] / "datasets/paired/dynamic-update-hard-001.jsonl"
    case = json.loads(dataset.read_text())
    next(step for step in case["steps"] if step["type"] == "probe")["expected"] = {"include": ["GRADER-ONLY-9413"]}
    dataset.write_text(json.dumps(case))
    execute = PairedDemoAgent.execute_task
    def observed(self, probe):
        assert set(probe.model_dump()) == {"type", "content"}
        assert "GRADER-ONLY-9413" not in str(self.context) + str(self.memory) + probe.content
        assert list(self.sandbox.iterdir()) == []
        return execute(self, probe)
    monkeypatch.setattr(PairedDemoAgent, "execute_task", observed)
    _, result = run_paired(paired_project)
    pair = result["pairs"][0]
    assert all(arm["answers"][0]["answer_correct"]["status"] == "fail" for arm in pair["arms"].values())
    assert pair["comparison"]["public_score_delta_on_minus_off"] == 0.0


def test_unknown_answer_has_zero_pair_coverage_not_fabricated_gain(paired_project, monkeypatch):
    monkeypatch.setattr(PairedDemoAgent, "execute_task", lambda *args: "No required answer line")
    _, result = run_paired(paired_project)
    compare = result["pairs"][0]["comparison"]
    assert compare["comparable"] and compare["public_pair_coverage"] == 0.0
    assert compare["scorable_pairs"] == 0 and compare["public_score_delta_on_minus_off"] is None


@pytest.mark.parametrize("extra", [{"model": "cannot-be-honored"}, {}])
def test_unsupported_model_and_workspace_capability(paired_project, extra):
    data = yaml.safe_load(paired_project.read_text())
    if extra:
        data["agents"][0].update(extra)
        paired_project.write_text(yaml.safe_dump(data))
    else:
        dataset = paired_project.parents[1] / "datasets/paired/dynamic-update-hard-001.jsonl"
        case = json.loads(dataset.read_text())
        case["steps"].append({"type": "check_file", "id": "file", "path": "answer.txt", "expected": {"include": ["571"]}})
        dataset.write_text(json.dumps(case))
    _, result = run_paired(paired_project)
    assert result["pairs"][0]["status"] == "unsupported"
    assert result["pairs"][0]["arms"] == {}


def test_cli_machine_contract_and_legacy_result_rejection(paired_project):
    cli = CliRunner()
    output = cli.invoke(app, ["run-paired", str(paired_project), "--json"])
    assert output.exit_code == 0, output.output
    envelope = json.loads(output.output)
    assert envelope["ok"] and envelope["data"]["pairs"][0]["comparison"]["comparable"]
    path = envelope["data"]["run_dir"]
    for command in ("report", "rescore", "view"):
        rejected = cli.invoke(app, [command, path, "--json"])
        assert rejected.exit_code == 2 and not json.loads(rejected.output)["ok"]


def test_historical_explicit_deletion_failure_is_not_rewritten():
    source = ROOT / "docs/results/openkylin-48x2/results.json"
    data = json.loads(source.read_text())
    codex = next(a for a in data["agent_results"] if a["agent_id"] == "codex")
    case = next(c for c in codex["cases"] if c["case_id"] == "dynamic_update-007")
    assert case["status"] == "fail"
    answer = next(p for p in case["probes"] if p["kind"] == "probe")
    stored = next(p for p in case["probes"] if p["kind"] == "check_memory")
    assert answer["status"] == "pass" and "571" in answer["response"]
    assert stored["status"] == "fail" and "517" in stored["evaluation"]["scored_text"]
