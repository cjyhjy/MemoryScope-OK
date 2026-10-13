"""Codex adapter checked against a fake `codex` executable; no network or API key is used."""

import json
import sys

import pytest

from memoryscope.adapters.codex import CodexAgent
from memoryscope.models import AgentConfig, Probe
from memoryscope.runner import run_benchmark

FAKE_CODEX = r'''
import json, os, pathlib, sys, uuid
args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.0-fake"); sys.exit(0)
home = pathlib.Path(os.environ["CODEX_HOME"])
assert (home / "config.toml").is_file() and (home / "AGENTS.md").is_file()
assert "sk-test-secret" not in (home / "config.toml").read_text()
log = home / "calls.jsonl"
with log.open("a") as stream:
    stream.write(json.dumps(args) + "\n")
prompt = args[-1]
thread = args[args.index("resume") + 3] if "resume" in args else str(uuid.uuid4())
memory = pathlib.Path.cwd() / "MEMORY.md"
if "记住" in prompt:
    with memory.open("a") as stream:
        stream.write(prompt + "\n")
    reply = "好的，已记录。"
elif "FAIL" in prompt:
    print(json.dumps({"type": "turn.failed", "error": {"message": "boom"}})); sys.exit(1)
else:
    saved = memory.read_text() if memory.exists() else ""
    reply = "答案：5734" if "5734" in saved else "答案：不知道"
print(json.dumps({"type": "thread.started", "thread_id": thread}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": reply}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}))
'''


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    script = tmp_path / "fake_codex.py"
    script.write_text(FAKE_CODEX, encoding="utf-8")
    launcher = tmp_path / "codex"
    launcher.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n", encoding="utf-8")
    launcher.chmod(0o755)
    monkeypatch.setenv("MEMORYSCOPE_CODEX_BIN", str(launcher))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    fake_home = tmp_path / "user-home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    return fake_home


def test_sessions_are_new_threads_and_memory_file_is_evidence(fake_codex, tmp_path):
    agent = CodexAgent(AgentConfig(id="codex", type="codex"))
    agent.start("run", "codex", tmp_path / "sandbox")
    agent.reset_case("c1")
    agent.reset_session("s1")
    agent.send_message("user", "记住：端口用 5734。")
    first_thread = agent.thread_id
    agent.send_message("user", "今天天气不错。")
    assert agent.thread_id == first_thread
    agent.reset_session("s2")
    assert agent.thread_id is None
    assert agent.execute_task(Probe(content="端口是多少？")) == "答案：5734"
    assert agent.thread_id != first_thread
    evidence = agent.collect_evidence()
    assert evidence["memory_file"]["exists"] and "5734" in evidence["memory_file"]["content"]
    calls = [json.loads(line) for line in (agent.home / "calls.jsonl").read_text().splitlines()]
    assert ["resume" in call for call in calls] == [False, True, False]
    agent.reset_case("c2")
    agent.reset_session("s1")
    assert agent.execute_task(Probe(content="端口是多少？")) == "答案：不知道"
    assert not (fake_codex / ".codex").exists()


def test_failures_and_missing_key_are_errors(fake_codex, tmp_path, monkeypatch):
    agent = CodexAgent()
    agent.start("run", "codex", tmp_path / "sandbox")
    agent.reset_case("c1")
    agent.reset_session("s1")
    with pytest.raises(RuntimeError, match="codex-cli failed"):
        agent.send_message("user", "FAIL")
    with pytest.raises(ValueError):
        agent.send_message("assistant", "hi")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        CodexAgent().start("run", "codex", tmp_path / "other")


def test_full_run_with_codex_adapter_is_not_synthetic(fake_codex, project):
    config = project / "configs/demo.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("type: demo", "type: codex"), encoding="utf-8")
    run_dir, result = run_benchmark(config)
    agent = result["agent_results"][0]
    assert result["synthetic"] is False and agent["synthetic"] is False
    assert agent["cases"][0]["status"] == "pass"
    assert agent["describe"]["model"] == "deepseek-flash"
    text = (run_dir / "events.jsonl").read_text(encoding="utf-8") + (run_dir / "metadata.json").read_text(encoding="utf-8")
    assert "sk-test-secret" not in text


def _jsonl(*events):
    return "\n".join(json.dumps(event) for event in events)


def test_reconnect_notice_is_transient_when_turn_completes():
    agent = CodexAgent(AgentConfig(id="codex", type="codex"))
    parsed = agent.parse_output(_jsonl(
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "error", "message": "Reconnecting... 1/5 (stream disconnected before completion)"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "答案：5734"}},
        {"type": "turn.completed", "usage": {}},
    ))
    assert parsed.errors == []
    assert parsed.messages == ["答案：5734"]
    assert parsed.tool_events[0]["type"] == "transient_error"


def test_reconnect_notice_without_completed_turn_is_an_error():
    agent = CodexAgent(AgentConfig(id="codex", type="codex"))
    parsed = agent.parse_output(_jsonl(
        {"type": "thread.started", "thread_id": "t1"},
        {"type": "error", "message": "Reconnecting... waiting for network"},
    ))
    assert parsed.errors == ["Reconnecting... waiting for network"]


def test_other_error_events_stay_fatal():
    agent = CodexAgent(AgentConfig(id="codex", type="codex"))
    parsed = agent.parse_output(_jsonl(
        {"type": "error", "message": "unexpected status 401"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "x"}},
        {"type": "turn.completed", "usage": {}},
    ))
    assert parsed.errors == ["unexpected status 401"]
