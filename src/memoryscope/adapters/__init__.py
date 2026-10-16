"""Adapters receive public conversation inputs, never benchmark answers."""

from memoryscope.adapters.codex import CodexAgent
from memoryscope.adapters.command import CommandAgent
from memoryscope.adapters.demo import DemoAgent
from memoryscope.adapters.dsh import DshAgent

ADAPTERS = {"demo": DemoAgent, "codex": CodexAgent, "dsh": DshAgent, "command": CommandAgent}


def adapter_catalog() -> list[dict]:
    """Describe registered types without constructing agents or invoking tools."""
    return [{"id": name, "name": getattr(adapter, "name", adapter.__name__),
             "synthetic": adapter.synthetic,
             "required_environment": list(adapter.required_environment),
             "capabilities": sorted(item.value for item in adapter.capabilities)}
            for name, adapter in ADAPTERS.items()]
