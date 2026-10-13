"""Shared driver for real agents that run as one-shot CLI processes.

Isolation model, identical for every CLI agent so results are comparable:

* Each case gets ``<sandbox>/<case_id>/home`` (the agent's private config/state
  home, e.g. ``CODEX_HOME`` or ``DSH_HOME``) and ``<sandbox>/<case_id>/workspace``.
  The sandbox is a temp directory outside the project, so the user's normal
  configuration (``~/.codex``, ``~/.dsh``) is never read or written.
* A new session is a new agent thread with no prior conversation; within a
  session later messages resume the same thread.
* Declared long-term memory: the user-global ``AGENTS.md`` in the case home tells
  the agent that ``MEMORY.md`` in its workspace is its only cross-session memory.
  The file is captured after every step as storage evidence.
* API keys are read by the agent from the environment only; they are never
  written to config files, events or reports.
"""

import hashlib
import os
import subprocess
from abc import abstractmethod
from pathlib import Path
from typing import Any

from memoryscope.adapters.base import AgentAdapter
from memoryscope.models import AgentConfig, Capability, Probe

API_KEY_ENV = "DEEPSEEK_API_KEY"
MEMORY_FILE = "MEMORY.md"
MAX_SNAPSHOT_CHARS = 8000

MEMORY_POLICY = f"""# 长期记忆约定

你是同一位用户的长期助手，用户会在多个彼此独立的会话中与你交流。
当前工作目录中的 `{MEMORY_FILE}` 是你唯一的跨会话长期记忆：新会话看不到以前的对话。

- 每次会话开始处理用户请求前，先读取 `{MEMORY_FILE}`（不存在则视为空）。
- 由你判断哪些信息值得长期记住，并写入或更新 `{MEMORY_FILE}`。
- 回答用户问题时直接给出结论。
"""


class CallResult:
    def __init__(self) -> None:
        self.thread_id: str | None = None
        self.messages: list[str] = []
        self.tool_events: list[dict[str, Any]] = []
        self.usage: Any = None
        self.errors: list[Any] = []


class CliMemoryAgent(AgentAdapter):
    synthetic = False
    capabilities = frozenset({Capability.CROSS_SESSION, Capability.WORKSPACE_FILES, Capability.MEMORY_INSPECTION})
    name = "cli-agent"
    home_env = ""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.model = config.model if config and config.model else None
        self.timeout = config.timeout_seconds if config else 300
        self.binary: str | None = None
        self.sandbox: Path | None = None
        self.case_dir: Path | None = None
        self.case_id = ""
        self.session_id = ""
        self.thread_id: str | None = None
        self.version: str | None = None
        self.last_call: dict[str, Any] = {}
        self.calls = 0

    # --- agent specific -------------------------------------------------
    @abstractmethod
    def locate_binary(self) -> str | None: ...

    @abstractmethod
    def prepare_home(self) -> None:
        """Write the agent's private config into ``self.home`` (never a secret)."""

    @abstractmethod
    def build_command(self, prompt: str) -> tuple[list[str], str | None]:
        """Return argv and optional stdin for one turn in the current thread."""

    @abstractmethod
    def parse_output(self, stdout: str) -> CallResult: ...

    # --- shared lifecycle ----------------------------------------------
    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "agent": self.name, "binary": self.binary, "version": self.version,
                "model": self.model, "api_key_env": API_KEY_ENV,
                "memory_mechanism": f"workspace {MEMORY_FILE} declared via per-case {self.home_env}/AGENTS.md",
                "session_mechanism": "new agent thread per session; resume the thread within a session"}

    def start(self, run_id: str, agent_id: str, sandbox: Path) -> None:
        self.binary = self.locate_binary()
        if not self.binary:
            raise RuntimeError(f"{self.name} executable not found")
        if not os.environ.get(API_KEY_ENV):
            raise RuntimeError(f"environment variable {API_KEY_ENV} is not set")
        result = subprocess.run([self.binary, "--version"], capture_output=True, text=True, timeout=120,
                                env=self._env(sandbox / ".version-home"))
        self.version = (result.stdout or result.stderr).strip() or None
        self.sandbox = sandbox

    @property
    def home(self) -> Path:
        assert self.case_dir is not None
        return self.case_dir / "home"

    @property
    def workspace(self) -> Path:
        assert self.case_dir is not None
        return self.case_dir / "workspace"

    def _env(self, home: Path) -> dict[str, str]:
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        return dict(os.environ, **{self.home_env: str(home)})

    def reset_case(self, case_id: str) -> None:
        if self.sandbox is None:
            raise RuntimeError("adapter has not started")
        self.case_id = case_id
        self.case_dir = self.sandbox / case_id
        if self.case_dir.exists():
            raise RuntimeError(f"case namespace already used: {case_id}")
        self.home.mkdir(parents=True, mode=0o700)
        self.workspace.mkdir(mode=0o700)
        (self.home / "AGENTS.md").write_text(MEMORY_POLICY, encoding="utf-8")
        self.prepare_home()
        self.thread_id = None
        self.session_id = ""

    def reset_session(self, session_id: str) -> None:
        if self.case_dir is None:
            raise RuntimeError("reset_case must precede reset_session")
        self.session_id = session_id
        self.thread_id = None

    def _turn(self, prompt: str) -> str:
        if not self.session_id:
            raise RuntimeError("reset_session must precede messages")
        command, stdin = self.build_command(prompt)
        try:
            completed = subprocess.run(command, cwd=self.workspace, env=self._env(self.home), input=stdin,
                                       capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired as error:
            self.last_call = {"timeout_seconds": self.timeout, "thread_id": self.thread_id}
            raise RuntimeError(f"{self.name} timed out after {self.timeout}s") from error
        self.calls += 1
        parsed = self.parse_output(completed.stdout)
        self.thread_id = parsed.thread_id or self.thread_id
        self.last_call = {"exit_code": completed.returncode, "thread_id": self.thread_id,
                          "tool_events": parsed.tool_events, "usage": parsed.usage, "errors": parsed.errors,
                          "stderr_tail": completed.stderr[-2000:]}
        if completed.returncode != 0 or parsed.errors or not parsed.messages:
            raise RuntimeError(f"{self.name} failed (exit {completed.returncode}): {parsed.errors or completed.stderr[-500:]}")
        return parsed.messages[-1]

    def send_message(self, role: str, content: str) -> str:
        if role != "user":
            raise ValueError(f"{self.name} adapter only replays user messages")
        return self._turn(content)

    def execute_task(self, probe: Probe) -> str:
        return self._turn(probe.content)

    def _memory_snapshot(self) -> dict[str, Any]:
        if self.case_dir is None:
            return {"exists": False}
        path = self.workspace / MEMORY_FILE
        if not path.is_file():
            return {"exists": False}
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        return {"exists": True, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                "content": text[:MAX_SNAPSHOT_CHARS], "truncated": len(text) > MAX_SNAPSHOT_CHARS}

    def collect_evidence(self) -> dict[str, Any]:
        return {"synthetic": False, "case_id": self.case_id, "session_id": self.session_id,
                "thread_id": self.thread_id, "calls": self.calls, "last_call": self.last_call,
                "memory_file": self._memory_snapshot(),
                "workspace_files": sorted(p.name for p in self.workspace.iterdir()) if self.case_dir else []}

    def shutdown(self) -> None:
        self.thread_id = None
