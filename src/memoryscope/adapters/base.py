from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from memoryscope.models import Capability, Probe


class AgentAdapter(ABC):
    """Lifecycle boundary for isolated, observable memory experiments.

    Real adapters must demonstrate that reset_session clears model-visible history
    while preserving only the tested memory backend. reset_case clears both.
    ``sandbox`` is a fresh directory outside the project tree owned by this agent
    for the whole run; adapters must not read or write outside it.
    """

    synthetic: bool = True
    capabilities: frozenset[Capability] = frozenset()
    required_environment: tuple[str, ...] = ()

    @staticmethod
    def paired_isolation_support() -> dict[str, Any]:
        """Fail closed: env vars, a new thread ID or prompts are not isolation.

        Support requires an audited inventory of every answer-bearing surface.
        Real/command adapters do not inherit a claim from their CLI sandbox.
        """
        return {"status": "unsupported", "reason": "Complete paired state isolation has not been demonstrated."}

    def isolate_paired_session(self, session_id: str, *, memory_enabled: bool) -> dict[str, Any]:
        raise NotImplementedError("paired isolation is unsupported")

    def describe(self) -> dict[str, Any]:
        return {"class": type(self).__name__, "synthetic": self.synthetic,
                "capabilities": sorted(capability.value for capability in self.capabilities)}

    def memory_text(self) -> str | None:
        """Stored long-term memory as text, or None when it cannot be inspected."""
        return None

    def read_workspace_file(self, relative: str) -> str | None:
        """Content of a sandbox workspace file, or None if missing/unsupported."""
        return None

    @abstractmethod
    def start(self, run_id: str, agent_id: str, sandbox: Path) -> None: ...

    @abstractmethod
    def reset_case(self, case_id: str) -> None: ...

    @abstractmethod
    def reset_session(self, session_id: str) -> None: ...

    @abstractmethod
    def send_message(self, role: str, content: str) -> str: ...

    @abstractmethod
    def execute_task(self, probe: Probe) -> str: ...

    @abstractmethod
    def collect_evidence(self) -> dict[str, Any]: ...

    @abstractmethod
    def shutdown(self) -> None: ...
