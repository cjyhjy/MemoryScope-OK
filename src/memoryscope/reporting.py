"""Offline reports rebuilt from a saved ``results.json``; agents are never called.

Writes ``report/report.json``, ``report.csv``, ``report.md`` and ``radar.png``
inside the run directory. Missing dimensions stay null and are drawn as gaps,
never as 0 or 100.
"""

import csv
import json
from pathlib import Path
from typing import Any

from memoryscope.models import Category

LABELS = {
    "retention": "Retention", "retrieval": "Retrieval", "dynamic_update": "Update",
    "disambiguation": "Disambiguation", "boundary": "Boundary", "reuse": "Reuse",
}
LABELS_ZH = {
    "retention": "长期保持", "retrieval": "记忆调用", "dynamic_update": "动态更新",
    "disambiguation": "相近区分", "boundary": "边界识别", "reuse": "任务复用",
}
COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2"]


def load_results(run_dir: Path) -> dict[str, Any]:
    result = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    if result.get("schema_version") != "1.1":
        raise ValueError("unsupported result schema_version")
    return result


def _fmt(value: float | None) -> str:
    return "null" if value is None else f"{value:.1f}"


def _safe_cell(value: Any) -> Any:
    """Stop spreadsheet apps from executing agent text as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": result["run_id"], "status": result["status"], "synthetic": result["synthetic"],
        "agents": [{"agent_id": agent["agent_id"], "synthetic": agent["synthetic"],
                    "describe": agent.get("describe", {}), "status": agent["status"],
                    "dimensions": agent["dimensions"], "overall_score": agent["overall_score"]}
                   for agent in result["agent_results"]],
    }


def write_csv(result: dict[str, Any], path: Path) -> None:
    fields = ["agent_id", "synthetic", "case_id", "category", "case_status", "check_id", "check_kind",
              "check_status", "explanation", "response", "evaluation_event", "error"]
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for agent in result["agent_results"]:
            for case in agent["cases"]:
                base = {"agent_id": agent["agent_id"], "synthetic": agent["synthetic"], "case_id": case["case_id"],
                        "category": case["category"], "case_status": case["status"],
                        "error": (case.get("error") or {}).get("message", "")}
                checks = case.get("probes") or [{}]
                for check in checks:
                    evaluation = check.get("evaluation") or {}
                    row = dict(base, check_id=check.get("probe_id", ""), check_kind=check.get("kind", ""),
                               check_status=check.get("status", ""), explanation=evaluation.get("explanation", ""),
                               response=check.get("response", ""), evaluation_event=check.get("evaluation_event", ""))
                    writer.writerow({key: _safe_cell(value) for key, value in row.items()})


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = [f"# MemoryScope-OK 评测报告", "", f"- Run ID：`{result['run_id']}`",
             f"- 运行状态：{result['status']}",
             f"- 性质：{'**synthetic 管线验证，不是真实 Agent 成绩**' if result['synthetic'] else '真实 Agent 实测'}",
             f"- 用例数：{result['dataset_case_count']}", "",
             "维度分 = 100 × 通过 / (通过 + 失败)。unknown、error、unsupported 不计入分母，单独列出并降低覆盖率；"
             "任一维度缺失时不计算六维总分。", "", "## 六维得分", ""]
    agents = result["agent_results"]
    lines.append("| 维度 | " + " | ".join(agent["agent_id"] for agent in agents) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in agents) + " |")
    for category in Category:
        cells = []
        for agent in agents:
            item = agent["dimensions"][category.value]
            cells.append(f"{_fmt(item['score'])}（{item['pass']}/{item['scorable']}，覆盖 {_fmt(item['scorable_coverage'])}%）")
        lines.append(f"| {LABELS_ZH[category.value]} `{category.value}` | " + " | ".join(cells) + " |")
    lines.append("| **六维总分** | " + " | ".join(_fmt(agent["overall_score"]) for agent in agents) + " |")
    lines += ["", "## 状态分布", "", "| Agent | pass | fail | unknown | error | unsupported |", "| --- | --- | --- | --- | --- | --- |"]
    for agent in agents:
        counts = {status: sum(item[status] for item in agent["dimensions"].values())
                  for status in ("pass", "fail", "unknown", "error", "unsupported")}
        lines.append(f"| {agent['agent_id']} | " + " | ".join(str(counts[s]) for s in counts) + " |")
    lines += ["", "## Agent 信息", ""]
    for agent in agents:
        describe = agent.get("describe") or {}
        lines.append(f"- **{agent['agent_id']}**：" + "；".join(f"{key}={value}" for key, value in describe.items()
                                                              if key in ("agent", "version", "model", "memory_mechanism", "capabilities")))
    lines += ["", "## 未通过的检查（含评分理由）", ""]
    for agent in agents:
        for case in agent["cases"]:
            if case["status"] == "pass":
                continue
            reasons = [f"{check['probe_id']}: {check['status']} — {(check.get('evaluation') or {}).get('explanation', '')}"
                       for check in case.get("probes", [])]
            if case.get("error"):
                reasons.append("error — " + case["error"].get("message", "")[:200])
            if case.get("missing_capabilities"):
                reasons.append("unsupported — 缺少能力：" + ", ".join(case["missing_capabilities"]))
            lines.append(f"- `{agent['agent_id']}` / `{case['case_id']}`（{case['status']}）：" + "；".join(reasons))
    lines += ["", "原始证据见同一运行目录的 `events.jsonl`；每条检查的 `evaluation_event` 指向其事件序号。", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_radar(result: dict[str, Any], path: Path) -> None:
    import math

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [category.value for category in Category]
    angles = [2 * math.pi * index / len(names) for index in range(len(names))]
    figure, axis = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    axis.set_theta_offset(math.pi / 2)
    axis.set_theta_direction(-1)
    axis.set_ylim(0, 100)
    axis.set_yticks([20, 40, 60, 80, 100])
    axis.set_xticks(angles)
    axis.set_xticklabels([LABELS[name] for name in names])
    for index, agent in enumerate(result["agent_results"]):
        color = COLORS[index % len(COLORS)]
        scores = [agent["dimensions"][name]["score"] for name in names]
        label = f"{agent['agent_id']}{' (synthetic)' if agent['synthetic'] else ''}"
        if all(score is not None for score in scores):
            axis.plot(angles + angles[:1], scores + scores[:1], color=color, linewidth=2, label=label)
            axis.fill(angles + angles[:1], scores + scores[:1], color=color, alpha=0.12)
        else:
            # Only connect adjacent measured dimensions; missing ones stay gaps.
            for start in range(len(names)):
                end = (start + 1) % len(names)
                if scores[start] is not None and scores[end] is not None:
                    axis.plot([angles[start], angles[end] if end else 2 * math.pi], [scores[start], scores[end]],
                              color=color, linewidth=2, linestyle="--")
            axis.plot([], [], color=color, linestyle="--", label=label + " (incomplete)")
        measured = [(angle, score) for angle, score in zip(angles, scores) if score is not None]
        axis.scatter([a for a, _ in measured], [s for _, s in measured], color=color, zorder=3)
    axis.legend(loc="upper right", bbox_to_anchor=(1.25, 1.12))
    title = "MemoryScope-OK" + (" — SYNTHETIC pipeline check" if result["synthetic"] else "")
    axis.set_title(f"{title}\nrun {result['run_id']}", pad=28, fontsize=10)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def build_report(run_dir: Path) -> Path:
    result = load_results(run_dir)
    out = run_dir / "report"
    out.mkdir(exist_ok=False)
    (out / "report.json").write_text(json.dumps(summary(result), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                     encoding="utf-8")
    write_csv(result, out / "report.csv")
    write_markdown(result, out / "report.md")
    write_radar(result, out / "radar.png")
    return out
