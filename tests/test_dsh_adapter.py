"""dsh adapter checked against a fake `dsh` executable; no network or API key is used."""

import json
import sys

from memoryscope.adapters.dsh import DshAgent
from memoryscope.models import Probe

FAKE_DSH = r'''
import json, os, pathlib, sys, uuid
args = sys.argv[1:]
if args == ["--version"]:
    print("0.0-fake"); sys.exit(0)
home = pathlib.Path(os.environ["DSH_HOME"])
assert args[:3] == ["--profile", "headless", "--patch"]
patch = pathlib.Path(args[3]).read_text()
if args[4:] == ["--dump-config"]:
    print("- id: agent\n  name: x\n" + patch.replace("- id: agent-default-model\n", "- id: agent-default-model\n  name: y\n")
          + "- id: jobs\n  name: z\n")
    sys.exit(0)
assert (home / "AGENTS.md").is_file()
assert args[4] == "--json" and args[-1] == "-"
prompt = sys.stdin.read()
session = args[args.index("--session-id") + 1] if "--session-id" in args else "session-" + str(uuid.uuid4())
with (home / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps({"resumed": "--session-id" in args}) + "\n")
memory = pathlib.Path.cwd() / "MEMORY.md"
if "记住" in prompt:
    memory.write_text(prompt)
    reply = "好的。"
else:
    reply = "答案：5734" if memory.exists() and "5734" in memory.read_text() else "答案：不知道"
print(json.dumps({"type": "session", "sessionId": session, "cwd": os.getcwd()}))
print(json.dumps({"type": "tool_call", "name": "fs_write"}))
print(json.dumps({"type": "status", "phase": "turn_end", "reason": {"kind": "completed"}}))
print(json.dumps({"type": "final", "text": reply}))
'''


def test_dsh_sessions_memory_and_isolated_home(tmp_path, monkeypatch):
    script = tmp_path / "fake_dsh.py"
    script.write_text(FAKE_DSH, encoding="utf-8")
    launcher = tmp_path / "dsh"
    launcher.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n", encoding="utf-8")
    launcher.chmod(0o755)
    monkeypatch.setenv("MEMORYSCOPE_DSH_BIN", str(launcher))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    agent = DshAgent()
    agent.start("run", "dsh", tmp_path / "sandbox")
    agent.reset_case("c1")
    agent.reset_session("s1")
    agent.send_message("user", "记住：端口用 5734。")
    agent.send_message("user", "无关的话。")
    agent.reset_session("s2")
    assert agent.execute_task(Probe(content="端口？")) == "答案：5734"
    calls = [json.loads(line)["resumed"] for line in (agent.home / "calls.jsonl").read_text().splitlines()]
    assert calls == [False, True, False]
    evidence = agent.collect_evidence()
    assert evidence["memory_file"]["exists"]
    assert evidence["last_call"]["tool_events"] == [{"type": "tool_call", "name": "fs_write"}]


def test_dsh_model_pin_is_verified(tmp_path, monkeypatch):
    from memoryscope.adapters.dsh import effective_model
    from memoryscope.models import AgentConfig

    dump = ("- id: agent\n  name: a\n- id: agent-default-model\n  name: '@x/model'\n  config:\n"
            "    provider: deepseek-official\n    model: deepseek-v4-pro\n- id: jobs\n  name: j\n    model: other\n")
    assert effective_model(dump) == "deepseek-v4-pro"
    assert effective_model("- id: agent\n  name: a\n") is None

    script = tmp_path / "fake_dsh.py"
    script.write_text(FAKE_DSH, encoding="utf-8")
    launcher = tmp_path / "dsh"
    launcher.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n", encoding="utf-8")
    launcher.chmod(0o755)
    monkeypatch.setenv("MEMORYSCOPE_DSH_BIN", str(launcher))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-secret")
    agent = DshAgent(AgentConfig(id="dsh", type="dsh", model="deepseek-v4-pro"))
    agent.start("run", "dsh", tmp_path / "sandbox")
    assert agent.describe()["effective_model"] == "deepseek-v4-pro"
    agent.reset_case("c1")
    assert 'model: "deepseek-v4-pro"' in (agent.home / "memoryscope-model.patch.yml").read_text()
