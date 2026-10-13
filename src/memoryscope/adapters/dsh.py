"""DeepSeek Harness (dsh) driven through ``dsh --profile headless --json``.

The per-case ``DSH_HOME`` keeps dsh's profiles, sessions and the user-global
``AGENTS.md``; ``~/.dsh`` and the desktop app's login are never used, so the
key must come from ``DEEPSEEK_API_KEY``. Prompts go through stdin (``-``).
See ``cli.py`` for the shared isolation and memory model.
"""

import json
import os
import shutil
from pathlib import Path

from memoryscope.adapters.cli import CallResult, CliMemoryAgent

DSH_BIN_ENV = "MEMORYSCOPE_DSH_BIN"
MACOS_APP_BIN = "/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh"
QUIET_EVENTS = {"session", "status", "final"}


class DshAgent(CliMemoryAgent):
    name = "deepseek-harness"
    home_env = "DSH_HOME"

    def locate_binary(self):
        configured = os.environ.get(DSH_BIN_ENV) or shutil.which("dsh")
        if configured:
            return configured
        return MACOS_APP_BIN if Path(MACOS_APP_BIN).is_file() else None

    def prepare_home(self) -> None:
        """dsh creates its headless profile on first use; nothing secret is written."""

    def build_command(self, prompt):
        command = [self.binary, "--profile", "headless", "--json"]
        if self.thread_id:
            command += ["--session-id", self.thread_id]
        return command + ["-"], prompt

    def parse_output(self, stdout: str) -> CallResult:
        result = CallResult()
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            kind = event.get("type")
            if kind == "session":
                result.thread_id = event.get("sessionId")
            elif kind == "final":
                if event.get("text"):
                    result.messages.append(event["text"])
            elif kind == "status":
                reason = event.get("reason") or {}
                if reason.get("kind") == "error":
                    result.errors.append(reason.get("error"))
                if event.get("usage"):
                    result.usage = event["usage"]
            elif kind not in QUIET_EVENTS:
                result.tool_events.append({key: event.get(key) for key in list(event)[:6]})
        return result
