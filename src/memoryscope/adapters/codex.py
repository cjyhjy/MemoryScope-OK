"""Codex CLI driven through ``codex exec --json`` with a DeepSeek model.

The per-case ``CODEX_HOME`` holds a generated ``config.toml`` that points Codex at
DeepSeek's Responses API with ``env_key = "DEEPSEEK_API_KEY"``; ``~/.codex`` is
never touched. See ``cli.py`` for the shared isolation and memory model.
"""

import json
import os
import shutil
from typing import Any

from memoryscope.adapters.cli import API_KEY_ENV, CallResult, CliMemoryAgent

BASE_URL_ENV = "MEMORYSCOPE_DEEPSEEK_BASE_URL"
CODEX_BIN_ENV = "MEMORYSCOPE_CODEX_BIN"
DEFAULT_MODEL = "deepseek-flash"  # DeepSeek-V4.1-Flash; deepseek-v4-flash is retired
DEFAULT_BASE_URL = "https://api.deepseek.com"


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class CodexAgent(CliMemoryAgent):
    name = "codex-cli"
    home_env = "CODEX_HOME"

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.model = self.model or DEFAULT_MODEL
        self.base_url = os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)

    def describe(self):
        return {**super().describe(), "provider_base_url": self.base_url}

    def locate_binary(self):
        return os.environ.get(CODEX_BIN_ENV) or shutil.which("codex")

    def prepare_home(self) -> None:
        (self.home / "config.toml").write_text("\n".join([
            f"model = {_toml_string(self.model)}",
            'model_provider = "memoryscope_deepseek"',
            'approval_policy = "never"',
            'sandbox_mode = "workspace-write"',
            "",
            "[model_providers.memoryscope_deepseek]",
            'name = "DeepSeek (MemoryScope-OK)"',
            f"base_url = {_toml_string(self.base_url)}",
            f"env_key = {_toml_string(API_KEY_ENV)}",
            'wire_api = "responses"',
            "",
        ]), encoding="utf-8")

    def build_command(self, prompt):
        if self.thread_id:
            return [self.binary, "exec", "resume", "--json", "--skip-git-repo-check", self.thread_id, prompt], None
        return [self.binary, "exec", "--json", "--skip-git-repo-check", "-C", str(self.workspace), prompt], None

    def parse_output(self, stdout: str) -> CallResult:
        result = CallResult()
        completed = False
        transient: list[Any] = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            kind = event.get("type")
            if kind == "thread.started":
                result.thread_id = event.get("thread_id")
            elif kind == "item.completed":
                item = event.get("item") or {}
                if item.get("type") == "agent_message":
                    result.messages.append(item.get("text", ""))
                elif item.get("type") in ("command_execution", "file_change", "mcp_tool_call"):
                    result.tool_events.append({key: item.get(key) for key in ("type", "command", "changes", "exit_code", "status")})
            elif kind == "turn.completed":
                completed = True
                result.usage = event.get("usage")
            elif kind == "error" and str(event.get("message") or "").startswith("Reconnecting..."):
                # Codex retries dropped streams itself; only fatal if the turn never completes.
                transient.append(event.get("message"))
                result.tool_events.append({"type": "transient_error", "message": event.get("message")})
            elif kind in ("turn.failed", "error"):
                result.errors.append(event.get("error") or event.get("message"))
        if transient and not completed:
            result.errors.extend(transient)
        return result
