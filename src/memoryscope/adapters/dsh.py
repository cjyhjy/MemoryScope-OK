"""DeepSeek Harness (dsh) driven through ``dsh --profile headless --json``.

The per-case ``DSH_HOME`` keeps dsh's profiles, sessions and the user-global
``AGENTS.md``; ``~/.dsh`` and the desktop app's login are never used, so the
key must come from ``DEEPSEEK_API_KEY``. Prompts go through stdin (``-``).
The model is pinned with a ``--patch`` overlay on dsh's ``agent-default-model``
entry, and ``start`` confirms the effective model via ``--dump-config``.
See ``cli.py`` for the shared isolation and memory model.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from memoryscope.adapters.cli import CallResult, CliMemoryAgent

DSH_BIN_ENV = "MEMORYSCOPE_DSH_BIN"
MACOS_APP_BIN = "/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh"
QUIET_EVENTS = {"session", "status", "final"}
DEFAULT_MODEL = "deepseek-flash"
PROVIDER = "deepseek-official"
MODEL_PATCH = "memoryscope-model.patch.yml"
_MODEL_ENTRY = re.compile(r"^- id: agent-default-model\n(?:(?!- ).*\n)*?\s+model: *['\"]?([^'\"\n]+)", re.MULTILINE)


def effective_model(dump: str) -> str | None:
    """Read the model of the ``agent-default-model`` entry from ``dsh --dump-config`` output."""
    match = _MODEL_ENTRY.search(dump)
    return match.group(1).strip() if match else None


class DshAgent(CliMemoryAgent):
    name = "deepseek-harness"
    home_env = "DSH_HOME"

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.model = self.model or DEFAULT_MODEL
        self.effective_model: str | None = None

    def describe(self):
        return {**super().describe(), "provider": PROVIDER, "effective_model": self.effective_model,
                "model_pin": f"--patch {MODEL_PATCH} on agent-default-model"}

    def write_patch(self, home: Path) -> Path:
        path = home / MODEL_PATCH
        path.write_text("- id: agent-default-model\n  config:\n"
                        f"    provider: {json.dumps(PROVIDER)}\n    model: {json.dumps(self.model)}\n", encoding="utf-8")
        return path

    def start(self, run_id, agent_id, sandbox) -> None:
        super().start(run_id, agent_id, sandbox)
        home = sandbox / ".version-home"
        patch = self.write_patch(home)
        dump = subprocess.run([self.binary, "--profile", "headless", "--patch", str(patch), "--dump-config"],
                              capture_output=True, text=True, timeout=120, env=self._env(home))
        self.effective_model = effective_model(dump.stdout)
        if self.effective_model != self.model:
            raise RuntimeError(f"dsh model pin failed: wanted {self.model}, dump-config shows {self.effective_model}")

    def locate_binary(self):
        configured = os.environ.get(DSH_BIN_ENV) or shutil.which("dsh")
        if configured:
            return configured
        return MACOS_APP_BIN if Path(MACOS_APP_BIN).is_file() else None

    def prepare_home(self) -> None:
        """dsh creates its headless profile on first use; only the model patch is written (no secret)."""
        self.write_patch(self.home)

    def build_command(self, prompt):
        command = [self.binary, "--profile", "headless", "--patch", str(self.home / MODEL_PATCH), "--json"]
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
