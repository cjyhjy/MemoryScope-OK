"""Generic real agent declared in the run configuration as a command line.

    agents:
      - id: my-agent
        type: command
        name: My Agent
        command: ["my-agent", "--print", "{prompt}"]   # argv, no shell; {prompt} is the user message
        timeout_seconds: 300

Each turn runs the command once in the case workspace and takes stdout as the answer. The agent gets the
same isolation and declared memory as codex/dsh (see ``cli.py``): a private per-case home in
``MEMORYSCOPE_AGENT_HOME`` and ``MEMORY.md`` in the workspace as its only cross-session memory. Because a
generic command has no thread to resume and no system-instruction channel, the memory policy is prepended
to every prompt and context within a session also travels only through ``MEMORY.md``. Credentials come from
the environment the user already has; nothing is written into the configuration.
"""

import shutil
from typing import Any

from memoryscope.adapters.cli import MEMORY_POLICY, CallResult, CliMemoryAgent


class CommandAgent(CliMemoryAgent):
    name = "command"
    home_env = "MEMORYSCOPE_AGENT_HOME"
    required_environment = ()

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.template = list(config.command) if config and config.command else []
        self.name = (config.name if config and config.name else None) or (
            self.template[0] if self.template else "command")

    def describe(self) -> dict[str, Any]:
        info = {**super().describe(), "command_template": self.template,
                "session_mechanism": "one process per turn; context across turns only via MEMORY.md"}
        info.pop("api_key_env", None)
        return info

    def locate_binary(self) -> str | None:
        return shutil.which(self.template[0]) if self.template else None

    def start(self, run_id, agent_id, sandbox) -> None:
        # No API key requirement and no --version contract for arbitrary commands.
        self.binary = self.locate_binary()
        if not self.binary:
            raise RuntimeError(f"command not found: {self.template[0] if self.template else '(empty)'}")
        self.sandbox = sandbox

    def prepare_home(self) -> None:
        pass

    def build_command(self, prompt: str):
        text = f"{MEMORY_POLICY}\n---\n用户：{prompt}"
        return [self.binary] + [part.replace("{prompt}", text) for part in self.template[1:]], None

    def parse_output(self, stdout: str) -> CallResult:
        result = CallResult()
        if stdout.strip():
            result.messages.append(stdout.strip())
        return result
