import hashlib
import json

import pytest
from typer.testing import CliRunner

from memoryscope.adapters import ADAPTERS
from memoryscope.adapters.demo import DemoAgent
from memoryscope.cli import app
from memoryscope.evaluator import evaluate_contains
from memoryscope.io import InputError
from memoryscope.models import Category, Expected, Probe
from memoryscope.runner import run_benchmark


def read_events(run_dir):
    return [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_lifecycle_preserves_long_term_only_between_sessions():
    agent = DemoAgent()
    agent.start("run-a", "agent-a")
    agent.reset_case("one")
    agent.reset_session("learn")
    agent.send_message("user", "以后我的 Python 项目都使用 uv 管理依赖。")
    agent.reset_session("probe")
    evidence = agent.collect_evidence()
    assert evidence["short_term_messages"] == 0
    assert evidence["long_term_items"] == 1
    assert evidence["last_cleared_messages"] == 1
    probe = Probe(content="我的 Python 项目用什么工具管理依赖？")
    assert "uv" in agent.execute_task(probe)
    agent.reset_case("two")
    agent.reset_session("probe")
    assert "uv" not in agent.execute_task(probe)
    assert agent.collect_evidence()["long_term_items"] == 0
    agent.shutdown()
    assert agent.collect_evidence()["active"] is False
    with pytest.raises(RuntimeError, match="not started"):
        agent.execute_task(probe)


def test_rule_checks_required_and_forbidden_terms():
    expected = Expected(include=["uv", "Python"], exclude=["pip"])
    assert evaluate_contains("PYTHON 使用 UV。", expected)["score"] == 1.0
    missing = evaluate_contains("Python", expected)
    assert missing["score"] == 0.0 and missing["missing_terms"] == ["uv"]
    wrong = evaluate_contains("Python uv pip", expected)
    assert wrong["score"] == 0.0 and wrong["forbidden_hits"] == ["pip"]


def test_real_execution_artifacts_and_session_evidence(project, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    run_dir, result = run_benchmark(project / "configs/demo.yaml")
    assert run_dir.parent == project / "runs"
    assert result["status"] == "completed" and result["synthetic"] is True
    agent = result["agent_results"][0]
    assert agent["cases"][0]["score"] == 1.0 and agent["cases"][0]["status"] == "pass"
    assert "5734" in agent["cases"][0]["probes"][0]["response"]
    assert agent["dimension_scores"]["retention"] == 100.0
    assert agent["dimensions"]["retention"]["scorable_coverage"] == 100.0
    assert agent["dimension_scores"]["retrieval"] is None
    assert agent["overall_score"] is None
    events = read_events(run_dir)
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    cleared = next(event for event in events if event["event"] == "session_reset" and event["session_id"] == "s2")
    assert cleared["payload"]["evidence"]["short_term_messages"] == 0
    assert cleared["payload"]["evidence"]["last_cleared_messages"] == 3
    assert cleared["payload"]["evidence"]["long_term_items"] == 1
    probe = next(event for event in events if event["event"] == "probe")
    assert probe["payload"]["response"] == agent["cases"][0]["probes"][0]["response"]
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["synthetic"] is True
    assert metadata["event_count"] == len(events)
    for name, info in metadata["artifacts"].items():
        assert hashlib.sha256((run_dir / name).read_bytes()).hexdigest() == info["sha256"]
    second_dir, second = run_benchmark(project / "configs/demo.yaml")
    assert second_dir != run_dir
    assert second["agent_results"][0]["cases"][0]["probes"] == agent["cases"][0]["probes"]


def test_expected_never_reaches_adapter_and_failed_rule_is_truthful(project, case_data, monkeypatch):
    next(step for step in case_data["steps"] if step["type"] == "probe")["expected"] = {"include": ["secret-grading-answer"], "exclude": []}
    (project / "datasets/golden/retention.jsonl").write_text(json.dumps(case_data), encoding="utf-8")

    class ObservedDemo(DemoAgent):
        def execute_task(self, probe):
            assert set(probe.model_dump()) == {"type", "content"}
            assert "secret-grading-answer" not in str(self.context) + str(self.memory) + probe.content
            return "答案：5734"

    monkeypatch.setitem(ADAPTERS, "demo", ObservedDemo)
    _, result = run_benchmark(project / "configs/demo.yaml")
    case = result["agent_results"][0]["cases"][0]
    assert case["status"] == "fail" and case["score"] == 0.0
    assert case["probes"][0]["evaluation"]["missing_terms"] == ["secret-grading-answer"]


def test_case_and_agent_memory_are_isolated(project, case_data):
    second_case = dict(case_data, id="retention-002", steps=[{"type": "message", "content": "今天整理书桌。"}] + case_data["steps"][1:])
    source = project / "datasets/golden/retention.jsonl"
    source.write_text(json.dumps(case_data) + "\n" + json.dumps(second_case), encoding="utf-8")
    config = project / "configs/demo.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("seed: 0", "  - id: demo-b\n    type: demo\nseed: 0"), encoding="utf-8")
    run_dir, result = run_benchmark(config)
    for agent in result["agent_results"]:
        assert [case["score"] for case in agent["cases"]] == [1.0, 0.0]
        assert agent["dimension_scores"]["retention"] == 50.0
    namespaces = [case["namespace"] for agent in result["agent_results"] for case in agent["cases"]]
    assert len(set(namespaces)) == 4
    for event in read_events(run_dir):
        if event["event"] == "case_reset":
            assert event["payload"]["evidence"]["short_term_messages"] == 0
            assert event["payload"]["evidence"]["long_term_items"] == 0


@pytest.mark.parametrize("failure", ["start", "execute_task", "shutdown"])
def test_adapter_failures_are_recorded_and_shutdown_attempted(project, monkeypatch, failure):
    shutdown_calls = []

    class BrokenDemo(DemoAgent):
        def start(self, *args):
            if failure == "start":
                raise RuntimeError("intentional startup failure")
            return super().start(*args)

        def execute_task(self, probe):
            if failure == "execute_task":
                raise RuntimeError("intentional execution failure")
            return super().execute_task(probe)

        def shutdown(self):
            shutdown_calls.append(True)
            if failure == "shutdown":
                raise RuntimeError("intentional shutdown failure")
            return super().shutdown()

    monkeypatch.setitem(ADAPTERS, "demo", BrokenDemo)
    run_dir, result = run_benchmark(project / "configs/demo.yaml")
    assert result["status"] == "failed"
    assert len(shutdown_calls) == 1
    assert json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))["status"] == "failed"
    events = read_events(run_dir)
    assert any("error" in event["event"] for event in events)
    if failure != "shutdown":
        assert result["agent_results"][0]["cases"][0]["score"] is None
        assert result["agent_results"][0]["dimension_scores"]["retention"] is None
    if failure == "execute_task":
        assert any(event["event"] == "probe_started" for event in events)


def test_other_categories_run_and_missing_capability_is_unsupported(project, case_data):
    boundary = dict(case_data, id="boundary-x", category="boundary")
    files = dict(case_data, id="reuse-x", category="reuse",
                 metadata=dict(case_data["metadata"], requires=["workspace_files"]))
    (project / "datasets/golden/retention.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in (case_data, boundary, files)), encoding="utf-8")
    run_dir, result = run_benchmark(project / "configs/demo.yaml")
    agent = result["agent_results"][0]
    statuses = {case["case_id"]: case["status"] for case in agent["cases"]}
    assert statuses == {"retention-001": "pass", "boundary-x": "pass", "reuse-x": "unsupported"}
    assert agent["dimensions"]["reuse"] == {"planned": 1, "pass": 0, "fail": 0, "unknown": 0, "error": 0,
                                            "unsupported": 1, "scorable": 0, "score": None, "scorable_coverage": 0.0}
    assert agent["dimension_scores"]["retrieval"] is None and agent["overall_score"] is None
    assert result["status"] == "completed"
    assert any(event["event"] == "case_unsupported" for event in read_events(run_dir))


def test_answer_line_ignores_explanations_and_unknown_without_line():
    from memoryscope.evaluator import evaluate
    from memoryscope.models import Evaluation
    expected = Expected(include=["uv"], exclude=["pip", "poetry"])
    line = Evaluation(type="answer_line")
    assert evaluate("不要再用 pip 或 poetry。\n答案：uv", expected, line)["status"] == "pass"
    assert evaluate("答案：pip", expected, line)["status"] == "fail"
    missing = evaluate("用 uv。", expected, line)
    assert missing["status"] == "unknown" and missing["score"] is None


@pytest.mark.parametrize("response, passed", [
    ("用 uv 管理依赖。", True), ("使用uv管理", True), ("UV", True),
    ("用 uvicorn 启动。", False), ("先装 pipx 再装 uv", True), ("pip install uv", False),
])
def test_ascii_terms_match_on_token_boundaries(response, passed):
    assert evaluate_contains(response, Expected(include=["uv"], exclude=["pip"]))["passed"] is passed


def test_mixed_dimension_aggregation_and_overall():
    from memoryscope.runner import dimension_summary, overall_score
    cases = [{"category": c.value, "status": "pass"} for c in Category]
    cases += [{"category": "retention", "status": s} for s in ("fail", "unknown", "error")]
    summary = dimension_summary(cases)
    assert summary["retention"]["score"] == 50.0
    assert summary["retention"]["scorable_coverage"] == 50.0
    assert overall_score(summary) == pytest.approx((50.0 + 500.0) / 6)


def test_cli_help_validation_list_run_and_report(project):
    runner = CliRunner()
    for arguments in (["--help"], ["--version"], ["validate", str(project / "datasets")], ["list-agents"]):
        assert runner.invoke(app, arguments).exit_code == 0
    listed = runner.invoke(app, ["list-agents"])
    assert "synthetic=true" in listed.stdout
    ran = runner.invoke(app, ["run", str(project / "configs/demo.yaml")])
    assert ran.exit_code == 0, ran.output
    assert "SYNTHETIC" in ran.stdout
    run_dir = next((project / "runs").iterdir())
    report = runner.invoke(app, ["report", str(run_dir)])
    assert report.exit_code == 0, report.output
    assert json.loads(report.stdout)["synthetic"] is True


def test_cli_failure_exit_codes(project, monkeypatch):
    runner = CliRunner()
    assert runner.invoke(app, ["validate", str(project / "missing.jsonl")]).exit_code == 2

    class BrokenDemo(DemoAgent):
        def execute_task(self, probe):
            raise RuntimeError("intentional failure")

    monkeypatch.setitem(ADAPTERS, "demo", BrokenDemo)
    result = runner.invoke(app, ["run", str(project / "configs/demo.yaml")])
    assert result.exit_code == 1
    assert "failed" in result.stdout
