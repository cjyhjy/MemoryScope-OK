"""Strict, versioned inputs. Unsupported protocol/scoring modes are rejected.

Schema 1.1 expresses a case as an ordered ``steps`` list (messages, session
switches and graded probes). Schema 1.0 cases are converted explicitly by
``upgrade_case`` and keep ``source_schema_version`` for traceability.
"""

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Category(str, Enum):
    RETENTION = "retention"
    RETRIEVAL = "retrieval"
    DYNAMIC_UPDATE = "dynamic_update"
    DISAMBIGUATION = "disambiguation"
    BOUNDARY = "boundary"
    REUSE = "reuse"


class Capability(str, Enum):
    """What a case needs from an adapter; missing capabilities yield ``unsupported``."""

    CROSS_SESSION = "cross_session"
    WORKSPACE_FILES = "workspace_files"
    MEMORY_INSPECTION = "memory_inspection"


NonBlank = Annotated[str, Field(min_length=1)]
Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]


class Message(StrictModel):
    role: Literal["user", "assistant"] = "user"
    content: NonBlank


class Probe(StrictModel):
    """The only probe view an adapter ever receives: no answers, no rules."""

    type: Literal["question"] = "question"
    content: NonBlank


class Expected(StrictModel):
    include: list[NonBlank] = Field(default_factory=list)
    exclude: list[NonBlank] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_terms(self) -> "Expected":
        if not self.include and not self.exclude:
            raise ValueError("expected needs at least one include or exclude term")
        required = [term.casefold() for term in self.include]
        forbidden = [term.casefold() for term in self.exclude]
        if len(set(required)) != len(required) or len(set(forbidden)) != len(forbidden):
            raise ValueError("expected terms must be unique (case-insensitive)")
        if set(required) & set(forbidden):
            raise ValueError("a term cannot be both required and forbidden")
        if any(excluded in included for included in required for excluded in forbidden):
            raise ValueError("a required term cannot contain a forbidden term")
        return self


class Evaluation(StrictModel):
    """``contains`` checks the whole response; ``answer_line`` checks only the
    text after the last ``答案:``/``Answer:`` line, so explanations that mention
    rejected options cannot trigger forbidden terms."""

    type: Literal["contains", "answer_line"] = "contains"


class Protocol(StrictModel):
    mode: Literal["cross_session"] = "cross_session"


class CaseMetadata(StrictModel):
    difficulty: Literal["easy", "medium", "hard"]
    subcategory: NonBlank | None = None
    tags: list[NonBlank] = Field(default_factory=list)
    requires: list[Capability] = Field(default_factory=list)
    review_status: Literal["draft", "reviewed"] = "draft"


class MessageStep(StrictModel):
    type: Literal["message"]
    role: Literal["user", "assistant"] = "user"
    content: NonBlank


class NewSessionStep(StrictModel):
    type: Literal["new_session"]


class ProbeStep(StrictModel):
    type: Literal["probe"]
    id: Identifier
    content: NonBlank
    expected: Expected
    evaluation: Evaluation = Field(default_factory=Evaluation)

    def public(self) -> Probe:
        return Probe(content=self.content)


class CheckMemoryStep(StrictModel):
    """Inspect the agent's stored long-term memory (not its answer)."""

    type: Literal["check_memory"]
    id: Identifier
    expected: Expected


SafeRelativePath = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.\-/]+$")]


class CheckFileStep(StrictModel):
    """Verify a file the agent was asked to create inside its sandbox workspace."""

    type: Literal["check_file"]
    id: Identifier
    path: SafeRelativePath
    expected: Expected

    @field_validator("path")
    @classmethod
    def stays_in_workspace(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("check_file path must be relative and stay inside the workspace")
        return value


Step = Annotated[Union[MessageStep, NewSessionStep, ProbeStep, CheckMemoryStep, CheckFileStep],
                 Field(discriminator="type")]
GradedStep = (ProbeStep, CheckMemoryStep, CheckFileStep)


class BenchmarkCase(StrictModel):
    schema_version: Literal["1.1"]
    id: Identifier
    category: Category
    description: NonBlank
    steps: list[Step] = Field(min_length=2)
    protocol: Protocol = Field(default_factory=Protocol)
    metadata: CaseMetadata
    source_schema_version: Literal["1.0", "1.1"] = "1.1"

    @model_validator(mode="after")
    def check_steps(self) -> "BenchmarkCase":
        probes = [step for step in self.steps if isinstance(step, ProbeStep)]
        if not probes:
            raise ValueError("a case needs at least one probe step")
        graded = [step for step in self.steps if isinstance(step, GradedStep)]
        if len({step.id for step in graded}) != len(graded):
            raise ValueError("probe/check IDs must be unique within a case")
        if not isinstance(self.steps[0], MessageStep):
            raise ValueError("the first step must be a message that writes information")
        first_probe = self.steps.index(probes[0])
        if not any(isinstance(step, NewSessionStep) for step in self.steps[:first_probe]):
            raise ValueError("cross_session cases need a new_session before the first probe")
        if isinstance(self.steps[-1], NewSessionStep):
            raise ValueError("a case cannot end with new_session")
        return self

    @property
    def probes(self) -> list[ProbeStep]:
        return [step for step in self.steps if isinstance(step, ProbeStep)]

    @property
    def required_capabilities(self) -> set[Capability]:
        required = {Capability.CROSS_SESSION, *self.metadata.requires}
        if any(isinstance(step, CheckMemoryStep) for step in self.steps):
            required.add(Capability.MEMORY_INSPECTION)
        if any(isinstance(step, CheckFileStep) for step in self.steps):
            required.add(Capability.WORKSPACE_FILES)
        return required


def upgrade_case(data: Any) -> Any:
    """Convert a schema 1.0 object (fixed setup/updates/distractors/probe) to 1.1.

    Other versions are passed through unchanged so validation reports them.
    """
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        return data
    legacy = LegacyCase.model_validate(data)
    steps: list[dict[str, Any]] = [
        {"type": "message", **message.model_dump()}
        for stage in (legacy.setup, legacy.updates, legacy.distractors) for message in stage
    ]
    steps.append({"type": "new_session"})
    steps.append({"type": "probe", "id": "probe", "content": legacy.probe.content,
                  "expected": legacy.expected.model_dump(), "evaluation": legacy.evaluation.model_dump()})
    return {
        "schema_version": "1.1", "id": legacy.id, "category": legacy.category.value,
        "description": legacy.description, "steps": steps,
        "protocol": legacy.protocol.model_dump(), "metadata": legacy.metadata.model_dump(mode="json"),
        "source_schema_version": "1.0",
    }


class LegacyMetadata(StrictModel):
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[NonBlank] = Field(default_factory=list)


class LegacyEvaluation(StrictModel):
    type: Literal["contains"] = "contains"


class LegacyCase(StrictModel):
    schema_version: Literal["1.0"]
    id: Identifier
    category: Category
    description: NonBlank
    setup: list[Message] = Field(min_length=1)
    updates: list[Message] = Field(default_factory=list)
    distractors: list[Message] = Field(default_factory=list)
    probe: Probe
    expected: Expected
    evaluation: LegacyEvaluation
    protocol: Protocol
    metadata: LegacyMetadata


class AgentConfig(StrictModel):
    id: Identifier
    type: Literal["demo", "codex", "dsh"]
    model: NonBlank | None = None
    timeout_seconds: int = Field(default=300, ge=10, le=3600)


class RunConfig(StrictModel):
    schema_version: Literal["1.0"]
    dataset: NonBlank
    output_dir: NonBlank = "../runs"
    agents: list[AgentConfig] = Field(min_length=1)
    seed: int = Field(default=0, strict=True, ge=0, le=2**32 - 1)

    @field_validator("dataset", "output_dir")
    @classmethod
    def relative_paths(cls, value: str) -> str:
        from pathlib import Path, PureWindowsPath

        if Path(value).is_absolute() or PureWindowsPath(value).is_absolute():
            raise ValueError("paths must be relative to the configuration file")
        if "\\" in value:
            raise ValueError("use forward slashes in configuration paths")
        return value

    @model_validator(mode="after")
    def unique_agents(self) -> "RunConfig":
        ids = [agent.id for agent in self.agents]
        if len(set(ids)) != len(ids):
            raise ValueError("agent IDs must be unique")
        return self
