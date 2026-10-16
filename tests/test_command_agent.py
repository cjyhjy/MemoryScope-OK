import json
import sys
from pathlib import Path

import pytest
import yaml

from memoryscope.models import AgentConfig
from memoryscope.runner import run_benchmark

FAKE = r'''
import pathlib, sys
prompt = sys.argv[-1]
memory = pathlib.Path("MEMORY.md")
log = pathlib.Path(sys.argv[1])
log.write_text(log.read_text() + repr(prompt) + "\n" if log.exists() else repr(prompt) + "\n")
if "答案" in prompt:
    text = memory.read_text(encoding="utf-8") if memory.exists() else ""
    print("答案：" + ("5734" if "5734" in text else "不知道"))
else:
    memory.write_text((memory.read_text(encoding="utf-8") if memory.exists() else "") + prompt.split("用户：")[-1] + "\n",
                      encoding="utf-8")
    print("好的")
'''


def test_command_config_requires_prompt_placeholder():
    with pytest.raises(ValueError):
        AgentConfig.model_validate({"id": "x", "type": "command", "command": ["tool", "--ask"]})
    with pytest.raises(ValueError):
        AgentConfig.model_validate({"id": "x", "type": "codex", "command": ["tool", "{prompt}"]})
    assert AgentConfig.model_validate({"id": "x", "type": "command", "command": ["tool", "{prompt}"]}).command


def test_declared_command_agent_runs_isolated_with_memory_policy(project, tmp_path):
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "prompts.log"
    config = {"schema_version": "1.0", "dataset": "../datasets/golden", "output_dir": "../runs",
              "agents": [{"id": "fake", "type": "command", "name": "Fake CLI",
                          "command": [sys.executable, str(script), str(log), "{prompt}"]}]}
    (project / "configs/custom.yaml").write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
    run_dir, results = run_benchmark(project / "configs/custom.yaml")
    agent = results["agent_results"][0]
    assert results["status"] == "completed" and agent["synthetic"] is False
    assert agent["describe"]["agent"] == "Fake CLI" and "api_key_env" not in agent["describe"]
    case = agent["cases"][0]
    assert case["status"] == "pass", json.dumps(case, ensure_ascii=False)[:800]
    prompts = log.read_text(encoding="utf-8").splitlines()
    assert prompts and all("MEMORY.md" in line for line in prompts)
    events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "session_reset" in events and str(project) not in json.dumps(case.get("probes"))


def test_missing_command_is_an_agent_error_not_a_crash(project):
    config = {"schema_version": "1.0", "dataset": "../datasets/golden", "output_dir": "../runs",
              "agents": [{"id": "ghost", "type": "command", "command": ["no-such-agent-xyz", "{prompt}"]}]}
    (project / "configs/ghost.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    _, results = run_benchmark(project / "configs/ghost.yaml")
    agent = results["agent_results"][0]
    assert agent["status"] != "completed" and "no-such-agent-xyz" in json.dumps(agent["errors"])
