"""GUI acceptance cases from docs/CLI_GUI_HANDOFF.md section 6.

The data layer is tested without Qt; the window tests run offscreen and are skipped when PySide6 is absent.
"""

import json
import os
import shutil
import time
from pathlib import Path

import pytest
import yaml

from memoryscope.adapters import ADAPTERS
from memoryscope.adapters.demo import DemoAgent
from memoryscope.reporting import build_report
from memoryscope.runner import run_benchmark
from memoryscope_gui.model import (
    EventTail, RunLoadError, discover_runs, load_run, parse_cli_line, read_events, status_label,
    write_request_config,
)


@pytest.fixture
def demo_run(project):
    run_dir, _ = run_benchmark(project / "configs/demo.yaml")
    return run_dir


def test_valid_synthetic_run_with_missing_dimensions(demo_run):
    view = load_run(demo_run)
    assert view.any_synthetic and not view.warnings
    agent = view.agents[0]
    assert agent["overall_score"] is None and agent["dimensions"]["retrieval"]["score"] is None
    assert [row["status"] for row in view.case_rows()] == ["pass"]
    assert ("性质", "含 synthetic（不是真实 Agent 成绩）") in view.environment()
    assert view.radar_png is None
    build_report(demo_run)
    assert load_run(demo_run).radar_png is not None


def test_failed_case_in_completed_run_and_agent_error(project, case_data, monkeypatch):
    class Wrong(DemoAgent):
        def execute_task(self, probe):
            return "答案：完全无关"

    monkeypatch.setitem(ADAPTERS, "demo", Wrong)
    view = load_run(run_benchmark(project / "configs/demo.yaml")[0])
    assert view.results["status"] == "completed" and view.case_rows()[0]["status"] == "fail"

    class Broken(DemoAgent):
        def execute_task(self, probe):
            raise RuntimeError("agent exploded")

    monkeypatch.setitem(ADAPTERS, "demo", Broken)
    view = load_run(run_benchmark(project / "configs/demo.yaml")[0])
    row = view.case_rows()[0]
    assert row["status"] == "error" and "agent exploded" in json.dumps(row["case"], ensure_ascii=False)


@pytest.mark.parametrize("content, message", [
    ("{not json", "损坏"), ("[]", "不是对象"), ('{"schema_version": "2.0", "agent_results": []}', "不支持"),
    ('{"schema_version": "1.1"}', "agent_results"), ('{"schema_version": "1.1", "x": NaN}', "损坏"),
])
def test_corrupt_or_unsupported_results_are_rejected(tmp_path, content, message):
    (tmp_path / "results.json").write_text(content, encoding="utf-8")
    with pytest.raises(RunLoadError, match=message):
        load_run(tmp_path)


def test_interrupted_run_without_results_is_reported(tmp_path):
    (tmp_path / "events.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(RunLoadError, match="中断"):
        load_run(tmp_path)


def test_event_tail_keeps_half_lines_and_survives_garbage(tmp_path):
    path = tmp_path / "events.jsonl"
    tail = EventTail(path)
    assert tail.read() == []
    path.write_bytes(b'{"sequence": 1, "event": "a"}\n{"sequence": 2, "ev')
    assert [e["sequence"] for e in tail.read()] == [1]
    with path.open("ab") as stream:
        stream.write(b'ent": "b"}\nnot json\n')
    events = tail.read()
    assert events[0]["sequence"] == 2 and events[1]["event"] == "unparseable_line"
    assert [e["sequence"] for e in read_events(tmp_path, 2, 2)] == [2]


def test_unknown_status_is_never_shown_as_pass():
    assert status_label("pass").startswith("pass") and status_label("weird") == "未知状态：weird"


def test_request_config_is_exclusive_and_checked_by_core(project):
    request = write_request_config(project, project / "datasets/golden", [{"id": "demo", "type": "demo"}])
    config = yaml.safe_load(request.config_path.read_text(encoding="utf-8"))
    assert config["output_dir"] == f"../../runs/gui/{request.request_id}"
    assert request.config_path.parent == project / "configs/gui"
    from memoryscope.io import load_config
    assert load_config(request.config_path).output_dir == request.output_parent
    with pytest.raises(ValueError):
        write_request_config(project, project.parent, [{"id": "demo", "type": "demo"}])
    with pytest.raises(ValueError):
        write_request_config(project, project / "datasets/golden", [])


def test_cli_lines_and_run_discovery(project, demo_run):
    assert parse_cli_line('{"schema_version": "1.0", "type": "progress"}')["type"] == "progress"
    assert parse_cli_line('{"schema_version": "9"}') is None and parse_cli_line("Run completed") is None
    (demo_run / ".rescore-staging").mkdir()
    (demo_run / ".rescore-staging" / "results.json").write_text("{}", encoding="utf-8")
    assert discover_runs(project) == [demo_run]


# ---------- Qt window, offscreen ----------

QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="GUI extra not installed")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def wait_until(qapp, condition, seconds=60):
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("timed out")
        qapp.processEvents()
        time.sleep(0.02)


def test_window_shows_saved_run_and_rejects_broken_one(qapp, project, demo_run, tmp_path, monkeypatch):
    from memoryscope_gui.app import MainWindow

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    window = MainWindow(project)
    assert window.results.run_list.count() == 1
    window.results.run_list.setCurrentRow(0)
    assert "SYNTHETIC" in window.results.banner.text()
    assert window.results.cases.rowCount() == 1
    assert window.results.scores.item(6, 1).text() == "未测/不可评分"
    window.results.cases.selectRow(0)
    assert "评分理由" in window.results.detail.toHtml()
    assert "未检测到 DEEPSEEK_API_KEY" in window.runner.key_label.text()
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "results.json").write_text('{"schema_version": "9.0"}', encoding="utf-8")
    assert window.results.load(broken) is False and "不支持" in window.results.banner.text()
    window.close()


def test_window_runs_synthetic_evaluation_through_cli_and_shows_it(qapp, project):
    from memoryscope_gui.app import MainWindow

    shutil.copytree(Path(__file__).resolve().parents[1] / "datasets/smoke", project / "datasets/smoke")
    window = MainWindow(project)
    page = window.runner
    page.dataset.setCurrentIndex(page.dataset.findText("datasets/smoke"))
    for agent_id, (enabled, *_rest) in page.agent_rows.items():
        enabled.setChecked(agent_id == "demo")
    page._start()
    wait_until(qapp, lambda: window.results.view is not None and window.tabs.currentWidget() is window.results, 120)
    run_dir = window.results.view.run_dir
    assert run_dir.parent.parent == project / "runs/gui" and (run_dir / "report/radar.png").is_file()
    assert page.progress.value() == page.progress.maximum() >= 1
    assert "报告已生成" in page.phase.text() and not window.running
    window.close()


def test_custom_agents_are_listed_and_written_to_request(qapp, project):
    from memoryscope_gui.app import MainWindow

    (project / "configs/custom-agents.yaml").write_text(
        'schema_version: "1.0"\nagents:\n  - id: mine\n    type: command\n    name: Mine\n'
        '    command: ["mine", "{prompt}"]\n    timeout_seconds: 120\n', encoding="utf-8")
    window = MainWindow(project)
    page = window.runner
    assert "mine" in page.agent_rows and "command" not in page.agent_rows
    for agent_id, row in page.agent_rows.items():
        row[0].setChecked(agent_id == "mine")
    request = page._new_request()
    agents = yaml.safe_load(request.config_path.read_text(encoding="utf-8"))["agents"]
    assert agents == [{"id": "mine", "type": "command", "timeout_seconds": 120, "command": ["mine", "{prompt}"],
                       "name": "Mine"}]
    (project / "configs/custom-agents.yaml").write_text("agents:\n  - id: bad\n    type: command\n", encoding="utf-8")
    window.runner.populate()
    assert "custom-agents.yaml 无效" in page.key_label.text()
    window.close()
