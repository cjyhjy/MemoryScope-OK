import json

import pytest
from typer.testing import CliRunner

from memoryscope.adapters import ADAPTERS
from memoryscope.adapters.demo import DemoAgent
from memoryscope.cli import app
from memoryscope.reporting import build_report
from memoryscope.runner import run_benchmark


def invoke(*args):
    result = CliRunner().invoke(app, list(args))
    return result, json.loads(result.stdout)


def test_catalog_and_config_check_are_offline_and_do_not_create_outputs(project, monkeypatch):
    class MustNotStart(DemoAgent):
        def __init__(self, *args):
            raise AssertionError("offline inspection must not create agents")

    monkeypatch.setitem(ADAPTERS, "demo", MustNotStart)
    result, catalog = invoke("list-agents", "--json")
    assert result.exit_code == 0 and catalog["schema_version"] == "1.0"
    assert catalog["data"]["agents"][0]["synthetic"] is True
    result, config = invoke("check-config", str(project / "configs/demo.yaml"), "--json")
    assert result.exit_code == 0 and config["ok"]
    assert config["data"]["dataset_info"]["case_count"] == 1
    assert config["data"]["output_dir"] == str(project / "runs")
    assert not (project / "runs").exists()


@pytest.mark.parametrize("command", ["validate", "check-config", "run", "report", "rescore"])
def test_json_rejections_are_parseable_and_have_nonzero_exit(project, command):
    result, message = invoke(command, str(project / "missing"), "--json")
    assert result.exit_code == 2
    assert message["command"] == command and message["ok"] is False
    assert message["error"]["type"] and message["error"]["message"]
    assert not (project / "runs").exists()


def test_json_run_locates_all_artifacts_and_preserves_missing_dimensions(project):
    result, message = invoke("run", str(project / "configs/demo.yaml"), "--json")
    assert result.exit_code == 0 and message["ok"]
    data = message["data"]
    from pathlib import Path
    assert all(Path(data[key]).is_file() for key in ("metadata_path", "events_path", "results_path"))
    assert data["synthetic"] is True and data["agents"][0]["overall_score"] is None
    assert data["agents"][0]["dimensions"]["retrieval"]["score"] is None


def test_jsonl_lifecycle_is_safe_and_final_result_is_ready(project):
    result = CliRunner().invoke(app, ["run", str(project / "configs/demo.yaml"), "--jsonl"])
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.exit_code == 0
    progress = [line["data"] for line in lines if line["type"] == "progress"]
    assert progress[0]["event"] == "run_started" and progress[0]["planned_cases"] == 1
    assert progress[-1]["completed_cases"] == 1
    assert progress[-1]["event"] == "run_finished"
    allowed = {"event", "sequence", "timestamp", "run_id", "run_dir", "agent_id", "case_id",
               "completed_cases", "planned_cases", "status", "synthetic"}
    assert all(set(event) <= allowed for event in progress)
    assert lines[-1]["type"] == "result" and lines[-1]["ok"]
    from pathlib import Path
    assert Path(lines[-1]["data"]["metadata_path"]).is_file()


def test_progress_is_available_before_completion_and_observer_cannot_change_score(project):
    observed = []
    before_results = []

    def display(event):
        observed.append(event)
        if event["event"] == "run_started":
            from pathlib import Path
            before_results.append(((Path(event["run_dir"]) / "events.jsonl").is_file()
                                   and not (Path(event["run_dir"]) / "results.json").exists()))
            raise RuntimeError("UI disconnected")

    run_dir, result = run_benchmark(project / "configs/demo.yaml", progress=display)
    assert len(observed) == 1 and result["status"] == "completed"
    assert before_results == [True]
    assert result["agent_results"][0]["cases"][0]["status"] == "pass"
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert any(event["event"] == "progress_observer_error" for event in events)
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))


def test_json_failure_retains_artifacts_and_progress_counts_every_planned_case(project, monkeypatch):
    class Broken(DemoAgent):
        def start(self, *args):
            raise RuntimeError("unavailable")

    monkeypatch.setitem(ADAPTERS, "demo", Broken)
    result = CliRunner().invoke(app, ["run", str(project / "configs/demo.yaml"), "--jsonl"])
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.exit_code == 1 and not lines[-1]["ok"]
    assert lines[-1]["data"]["status"] == "failed"
    finished = [line["data"] for line in lines if line.get("type") == "progress"
                and line["data"]["event"] == "case_finished"]
    assert finished[0]["completed_cases"] == 1 and finished[0]["status"] == "error"


def test_machine_modes_are_exclusive(project):
    result, message = invoke("run", str(project / "configs/demo.yaml"), "--json", "--jsonl")
    assert result.exit_code == 2 and not message["ok"]
    assert not (project / "runs").exists()


def test_interrupt_reports_incomplete_evidence_and_exit_130(project, monkeypatch):
    class Interrupted(DemoAgent):
        def execute_task(self, probe):
            raise KeyboardInterrupt()

    monkeypatch.setitem(ADAPTERS, "demo", Interrupted)
    result = CliRunner().invoke(app, ["run", str(project / "configs/demo.yaml"), "--jsonl"])
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.exit_code == 130 and not lines[-1]["ok"]
    assert lines[-1]["data"]["status"] == "interrupted"
    from pathlib import Path
    run_dir = Path(lines[-1]["data"]["run_dir"])
    assert (run_dir / "events.jsonl").is_file()
    assert not (run_dir / "metadata.json").exists()
    assert not (run_dir / "results.json").exists()


def test_completed_run_with_failed_check_is_not_an_execution_error(project, case_data):
    probe = next(step for step in case_data["steps"] if step["type"] == "probe")
    probe["expected"] = {"include": ["impossible-grading-answer"], "exclude": []}
    (project / "datasets/golden/retention.jsonl").write_text(json.dumps(case_data))
    result, message = invoke("run", str(project / "configs/demo.yaml"), "--json")
    assert result.exit_code == 0 and message["ok"]
    assert message["data"]["agents"][0]["dimensions"]["retention"]["fail"] == 1


def test_report_failure_does_not_publish_partial_outputs_and_retry_works(project, monkeypatch):
    import memoryscope.reporting as reporting
    run_dir, _ = run_benchmark(project / "configs/demo.yaml")

    def disk_failure(*args):
        raise OSError("disk full")

    with monkeypatch.context() as patch:
        patch.setattr(reporting, "write_radar", disk_failure)
        result, message = invoke("report", str(run_dir), "--json")
        assert result.exit_code == 2 and not message["ok"]
    assert not (run_dir / "report").exists()
    assert not list(run_dir.glob(".report-*"))
    result, message = invoke("report", str(run_dir), "--json")
    assert result.exit_code == 0 and message["ok"]


def test_reuse_is_readonly_and_rejects_changed_details_even_with_same_summary(project):
    run_dir, _ = run_benchmark(project / "configs/demo.yaml")
    report = build_report(run_dir)
    before = {path.name: path.read_bytes() for path in report.iterdir()}
    assert build_report(run_dir, reuse=True) == report
    data = json.loads((run_dir / "results.json").read_text())
    data["agent_results"][0]["cases"][0]["probes"][0]["response"] = "changed recorded response"
    (run_dir / "results.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="differs"):
        build_report(run_dir, reuse=True)
    assert before == {path.name: path.read_bytes() for path in report.iterdir()}


def test_report_publication_does_not_remove_another_publishers_lock(project):
    run_dir, _ = run_benchmark(project / "configs/demo.yaml")
    lock = run_dir / ".report.lock"
    lock.write_text("another publisher")
    with pytest.raises(FileExistsError):
        build_report(run_dir)
    assert lock.read_text() == "another publisher"
    assert not (run_dir / "report").exists()
    assert not list(run_dir.glob(".report-*"))


def test_rescore_is_self_contained_and_can_be_reported_and_rescored_again(project, monkeypatch):
    run_dir, _ = run_benchmark(project / "configs/demo.yaml")
    before = {path.name: path.read_bytes() for path in run_dir.iterdir() if path.is_file()}

    class MustNotStart(DemoAgent):
        def __init__(self, *args):
            raise AssertionError("offline operation must not create agents")

    monkeypatch.setitem(ADAPTERS, "demo", MustNotStart)
    result, message = invoke("rescore", str(run_dir), "--json")
    assert result.exit_code == 0 and message["ok"]
    from pathlib import Path
    revised = Path(message["data"]["run_dir"])
    assert all((revised / name).is_file() for name in before)
    assert (revised / "events.jsonl").read_bytes() == before["events.jsonl"]
    assert before == {path.name: path.read_bytes() for path in run_dir.iterdir() if path.is_file()}
    assert invoke("report", str(revised), "--json")[0].exit_code == 0
    assert invoke("rescore", str(revised), "--json")[0].exit_code == 0


def test_rescore_rejects_evidence_from_a_different_run_without_partial_revision(project):
    run_dir, _ = run_benchmark(project / "configs/demo.yaml")
    events = (run_dir / "events.jsonl").read_text().splitlines()
    first = json.loads(events[0]); first["run_id"] = "unrelated-run"
    events[0] = json.dumps(first)
    (run_dir / "events.jsonl").write_text("\n".join(events) + "\n")
    result, message = invoke("rescore", str(run_dir), "--json")
    assert result.exit_code == 2 and not message["ok"]
    assert not list(run_dir.glob("rescore-*"))
    assert not list(run_dir.glob(".rescore-*"))


@pytest.mark.parametrize("contents", ["[]", '{"schema_version":"9.0"}', '{"schema_version":"1.1","x":NaN}'])
def test_report_rejects_non_object_unknown_and_nonfinite_results(project, contents):
    run_dir = project / "bad-run"; run_dir.mkdir()
    (run_dir / "results.json").write_text(contents)
    result, message = invoke("report", str(run_dir), "--json")
    assert result.exit_code == 2 and not message["ok"]
    assert not (run_dir / "report").exists()
