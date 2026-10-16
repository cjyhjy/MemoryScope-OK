"""Qt-free data layer of the GUI: read saved runs, follow events, write request configs, parse CLI output.

Everything here treats run files, agent text and CLI output as data. Nothing calls an agent or the network;
the GUI starts evaluations only through the ``memoryscope`` CLI (see docs/CLI_GUI_HANDOFF.md).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DIMENSIONS = ("retention", "retrieval", "dynamic_update", "disambiguation", "boundary", "reuse")
LABELS_ZH = {
    "retention": "长期保持", "retrieval": "记忆调用", "dynamic_update": "动态更新",
    "disambiguation": "相近区分", "boundary": "边界识别", "reuse": "任务复用",
}
STATUSES = ("pass", "fail", "unknown", "error", "unsupported")
STATUS_ZH = {"pass": "通过", "fail": "失败", "unknown": "无法判定", "error": "执行错误", "unsupported": "不支持"}
RESULTS_MAJOR = "1"
CLI_SCHEMA = "1.0"


class RunLoadError(ValueError):
    """The selected directory is not a readable run of a supported schema."""


def status_label(status: Any) -> str:
    """Unknown status values are shown verbatim, never assumed to be a pass."""
    if status in STATUS_ZH:
        return f"{status}（{STATUS_ZH[status]}）"
    return f"未知状态：{status}"


def fmt_score(value: Any) -> str:
    return "未测/不可评分" if value is None else f"{float(value):.1f}"


def _read_json(path: Path) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


@dataclass
class RunView:
    run_dir: Path
    results: dict[str, Any]
    metadata: dict[str, Any] | None
    warnings: list[str] = field(default_factory=list)

    @property
    def run_id(self) -> str:
        return str(self.results.get("run_id", self.run_dir.name))

    @property
    def agents(self) -> list[dict[str, Any]]:
        return self.results.get("agent_results") or []

    @property
    def any_synthetic(self) -> bool:
        # Per-agent flags win; a mixed run's top-level flag cannot speak for every agent.
        return bool(self.results.get("synthetic")) or any(agent.get("synthetic") for agent in self.agents)

    @property
    def radar_png(self) -> Path | None:
        path = self.run_dir / "report" / "radar.png"
        return path if path.is_file() and not path.is_symlink() else None

    @property
    def is_rescore(self) -> bool:
        return "rescored_from" in self.results

    def environment(self) -> list[tuple[str, str]]:
        meta = self.metadata or {}
        osr = meta.get("os_release") or {}
        evaluator = meta.get("evaluator") or {}
        artifacts = meta.get("artifacts") or {}
        rows = [
            ("Run ID", self.run_id), ("运行状态", self.results.get("status")),
            ("性质", "含 synthetic（不是真实 Agent 成绩）" if self.any_synthetic else "真实 Agent 实测"),
            ("用例数", self.results.get("dataset_case_count")),
            ("系统", osr.get("PRETTY_NAME")), ("平台", meta.get("platform")),
            ("Python", (meta.get("python_version") or "").split(" ")[0] or None),
            ("MemoryScope-OK", meta.get("package_version")),
            ("评分器", evaluator.get("version") or self.results.get("evaluator_version")),
            ("开始", meta.get("started_at")), ("结束", meta.get("finished_at")), ("事件数", meta.get("event_count")),
            ("数据快照 SHA-256", (artifacts.get("dataset.snapshot.jsonl") or {}).get("sha256")),
            ("results.json SHA-256", (artifacts.get("results.json") or {}).get("sha256")),
            ("重评来源", self.results.get("rescored_from")),
        ]
        for agent in self.agents:
            describe = agent.get("describe") or {}
            rows.append((f"Agent {agent.get('agent_id')}",
                         " · ".join(str(describe[k]) for k in ("agent", "version", "model") if describe.get(k))
                         + (" · synthetic" if agent.get("synthetic") else "")))
        return [(key, str(value)) for key, value in rows if value not in (None, "")]

    def case_rows(self) -> list[dict[str, Any]]:
        rows = []
        for agent in self.agents:
            for case in agent.get("cases") or []:
                rows.append({"agent_id": agent.get("agent_id"), "synthetic": bool(agent.get("synthetic")),
                             "case_id": case.get("case_id"), "category": case.get("category"),
                             "status": case.get("status"), "duration": case.get("duration_seconds"), "case": case})
        return rows


def load_run(run_dir: Path) -> RunView:
    run_dir = Path(run_dir)
    path = run_dir / "results.json"
    if not path.is_file():
        raise RunLoadError(f"没有 results.json：{run_dir}（运行可能被中断或尚未完成）")
    try:
        results = _read_json(path)
    except (OSError, ValueError) as error:
        raise RunLoadError(f"results.json 损坏：{error}") from error
    if not isinstance(results, dict):
        raise RunLoadError("results.json 顶层不是对象")
    version = str(results.get("schema_version", ""))
    if version.split(".")[0] != RESULTS_MAJOR:
        raise RunLoadError(f"不支持的 results schema_version：{version or '缺失'}")
    if not isinstance(results.get("agent_results"), list):
        raise RunLoadError("results.json 缺少 agent_results")
    warnings = []
    metadata = None
    if (run_dir / "metadata.json").is_file():
        try:
            metadata = _read_json(run_dir / "metadata.json")
        except (OSError, ValueError) as error:
            warnings.append(f"metadata.json 不可读：{error}")
    else:
        warnings.append("缺少 metadata.json：运行可能未正常结束，环境信息不完整")
    if version != "1.1":
        warnings.append(f"results schema {version} 与当前 1.1 不同，部分字段可能缺失")
    return RunView(run_dir, results, metadata, warnings)


def discover_runs(project: Path) -> list[Path]:
    """Run directories under ``runs/`` (including GUI request folders and rescore revisions), newest first."""
    base = project / "runs"
    if not base.is_dir():
        return []
    found = {path.parent for path in base.rglob("results.json")
             if not path.is_symlink() and not any(part.startswith(".") or part == "report"
                                                  for part in path.relative_to(base).parts[:-1])}
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


class EventTail:
    """Incrementally read ``events.jsonl``; a trailing half line is kept for the next read."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.pending = b""

    def read(self) -> list[dict[str, Any]]:
        try:
            with self.path.open("rb") as stream:
                stream.seek(self.offset)
                chunk = stream.read()
        except FileNotFoundError:
            return []
        self.offset += len(chunk)
        data = self.pending + chunk
        lines = data.split(b"\n")
        self.pending = lines.pop()
        events = []
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                events.append({"event": "unparseable_line", "raw": line[:500].decode("utf-8", "replace")})
                continue
            if isinstance(item, dict):
                events.append(item)
        return events


def read_events(run_dir: Path, first: int | None = None, last: int | None = None, limit: int = 400) -> list[dict]:
    events = [item for item in EventTail(run_dir / "events.jsonl").read() if isinstance(item.get("sequence"), int)]
    if first is not None:
        events = [item for item in events if item["sequence"] >= first]
    if last is not None:
        events = [item for item in events if item["sequence"] <= last]
    return events[:limit]


@dataclass(frozen=True)
class GuiRequest:
    request_id: str
    config_path: Path
    output_parent: Path


def write_request_config(project: Path, dataset: Path, agents: list[dict[str, Any]], seed: int = 0) -> GuiRequest:
    """Create ``configs/gui/<uuid>.yaml`` exclusively, with a dedicated ``runs/gui/<uuid>/`` output parent."""
    project = project.resolve()
    dataset = dataset.resolve()
    if not dataset.is_relative_to(project):
        raise ValueError("数据集必须位于项目目录内")
    if not agents:
        raise ValueError("至少选择一个 Agent")
    request_id = str(uuid.uuid4())
    config_dir = project / "configs" / "gui"
    config_dir.mkdir(parents=True, exist_ok=True)
    output_parent = project / "runs" / "gui" / request_id
    config = {
        "schema_version": "1.0",
        "dataset": os.path.relpath(dataset, config_dir).replace(os.sep, "/"),
        "output_dir": os.path.relpath(output_parent, config_dir).replace(os.sep, "/"),
        "agents": agents, "seed": seed,
    }
    path = config_dir / f"{request_id}.yaml"
    with path.open("x", encoding="utf-8") as stream:
        yaml.safe_dump(config, stream, allow_unicode=True, sort_keys=False)
    return GuiRequest(request_id, path, output_parent)


def cli_command(*args: str) -> list[str]:
    """Argument list for the CLI in this interpreter's environment; never a shell string."""
    return [sys.executable, "-m", "memoryscope", *args]


def parse_cli_line(line: str) -> dict[str, Any] | None:
    """One stdout line of ``--json``/``--jsonl``; anything else (or an unknown schema) yields None."""
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        item = json.loads(line)
    except ValueError:
        return None
    if not isinstance(item, dict) or item.get("schema_version") != CLI_SCHEMA:
        return None
    return item


def find_project(start: Path | None = None) -> Path | None:
    """Nearest directory with pyproject.toml and datasets/, from ``start`` (default cwd) upwards."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "datasets").is_dir():
            return candidate
    return None


CUSTOM_AGENTS = Path("configs") / "custom-agents.yaml"


def load_custom_agents(project: Path) -> tuple[list[dict[str, Any]], str | None]:
    """User-declared agents from ``configs/custom-agents.yaml`` (``agents:`` list), validated by the core model."""
    from memoryscope.models import AgentConfig

    path = project / CUSTOM_AGENTS
    if not path.is_file():
        return [], None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = data.get("agents") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError("缺少 agents 列表")
        agents = [AgentConfig.model_validate(item).model_dump(exclude_none=True) for item in items]
    except (OSError, ValueError, TypeError, yaml.YAMLError) as error:
        return [], f"{CUSTOM_AGENTS} 无效：{error}"
    return agents, None
