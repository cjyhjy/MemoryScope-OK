"""Adapters receive public conversation inputs, never benchmark answers."""

from memoryscope.adapters.codex import CodexAgent
from memoryscope.adapters.demo import DemoAgent
from memoryscope.adapters.dsh import DshAgent

ADAPTERS = {"demo": DemoAgent, "codex": CodexAgent, "dsh": DshAgent}
