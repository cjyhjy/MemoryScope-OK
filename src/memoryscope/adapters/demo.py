"""A synthetic toy fixture, NOT a real AI agent or competition result.

Long-term memory is a list of user statements containing persistence cues.
A probe is answered with the stored statement sharing the most character
bigrams with it (latest wins ties). It never sees expected answers; it exists
only to exercise lifecycle, isolation and scoring paths.
"""

from pathlib import Path
from typing import Any

from memoryscope.adapters.base import AgentAdapter
from memoryscope.models import Capability, Probe

PERSISTENCE_CUES = ("以后", "记住", "默认", "统一", "从现在起", "改成", "改为")


def _bigrams(text: str) -> set[str]:
    compact = "".join(text.split()).casefold()
    return {compact[index:index + 2] for index in range(len(compact) - 1)}


class DemoAgent(AgentAdapter):
    synthetic = True
    capabilities = frozenset({Capability.CROSS_SESSION, Capability.MEMORY_INSPECTION})

    def __init__(self, config: object = None) -> None:
        self.memory: list[str] = []
        self.context: list[dict[str, str]] = []
        self.run_id = ""
        self.agent_id = ""
        self.case_id = ""
        self.session_id = ""
        self.active = False
        self.last_cleared_messages = 0

    def start(self, run_id: str, agent_id: str, sandbox: Path | None = None) -> None:
        if self.active:
            raise RuntimeError("adapter is already active")
        self.run_id, self.agent_id = run_id, agent_id
        self.memory.clear()
        self.context.clear()
        self.active = True

    def _require_active(self) -> None:
        if not self.active:
            raise RuntimeError("adapter has not started")

    def reset_case(self, case_id: str) -> None:
        self._require_active()
        self.case_id = case_id
        self.session_id = ""
        self.last_cleared_messages = len(self.context)
        self.memory.clear()
        self.context.clear()

    def reset_session(self, session_id: str) -> None:
        self._require_active()
        if not self.case_id:
            raise RuntimeError("reset_case must precede reset_session")
        self.session_id = session_id
        self.last_cleared_messages = len(self.context)
        self.context.clear()

    def send_message(self, role: str, content: str) -> str:
        self._require_active()
        if not self.session_id:
            raise RuntimeError("reset_session must precede messages")
        self.context.append({"role": role, "content": content})
        if role == "user" and any(cue in content for cue in PERSISTENCE_CUES):
            self.memory.append(content)
        return "已接收（synthetic demo）。"

    def execute_task(self, probe: Probe) -> str:
        self._require_active()
        if not self.session_id:
            raise RuntimeError("reset_session must precede the probe")
        self.context.append({"role": "user", "content": probe.content})
        wanted = _bigrams(probe.content)
        best, best_overlap = None, 0
        for item in self.memory:
            overlap = len(wanted & _bigrams(item))
            if overlap >= best_overlap and overlap > 0:
                best, best_overlap = item, overlap
        response = f"根据记忆：{best}\n答案：{best}" if best else "没有相关记忆。\n答案：不知道"
        self.context.append({"role": "assistant", "content": response})
        return response

    def collect_evidence(self) -> dict[str, Any]:
        return {
            "synthetic": True,
            "namespace": f"{self.run_id}/{self.agent_id}/{self.case_id}",
            "session_id": self.session_id,
            "short_term_messages": len(self.context),
            "long_term_items": len(self.memory),
            "long_term_snapshot": list(self.memory),
            "last_cleared_messages": self.last_cleared_messages,
            "active": self.active,
        }

    def shutdown(self) -> None:
        self.memory.clear()
        self.context.clear()
        self.active = False
