"""MemoryScope-OK desktop GUI (PySide6).

Two pages over the same core as the CLI:
- 评测结果: browse saved runs, radar, six-dimension table, per-check reasons, evidence events, report/rescore.
- 新建评测: config form -> ``configs/gui/<uuid>.yaml`` -> ``memoryscope run --jsonl`` in a QProcess,
  live progress, then ``report --json --reuse`` and the result page.

The GUI never scores anything itself, never reads or shows the API key value, and never starts a run on
page load. Agent text is shown as escaped data.
"""

from __future__ import annotations

import html
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QProcess, QProcessEnvironment, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from memoryscope_gui.model import (
    DIMENSIONS, LABELS_ZH, STATUSES, EventTail, RunLoadError, RunView, cli_command, discover_runs,
    find_project, fmt_score, load_run, parse_cli_line, read_events, status_label, write_request_config,
)

COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2"]
STATUS_COLORS = {"pass": "#0f7b45", "fail": "#c4321c"}
DEFAULT_MODELS = {"codex": "deepseek-flash", "dsh": "deepseek-flash"}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def api_key_present(project: Path) -> bool:
    """Only whether a non-empty DEEPSEEK_API_KEY exists; the value is never read into the UI."""
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return True
    try:
        for line in (project / ".env").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "DEEPSEEK_API_KEY" and value.strip().strip("'\""):
                return True
    except OSError:
        pass
    return False


class RadarWidget(QWidget):
    """Six-axis radar; a missing dimension stays a gap (dashed neighbours), never 0 or 100."""

    def __init__(self) -> None:
        super().__init__()
        self.agents: list[dict[str, Any]] = []
        self.setMinimumSize(340, 340)

    def set_agents(self, agents: list[dict[str, Any]]) -> None:
        self.agents = agents
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        fg = palette.windowText().color()
        grid = QColor(fg)
        grid.setAlpha(60)
        legend_h = 22 * max(1, len(self.agents))
        side = min(self.width(), self.height() - legend_h)
        cx, cy = self.width() / 2, (self.height() - legend_h) / 2
        radius = max(40.0, side / 2 - 48)

        def point(index: int, score: float) -> QPointF:
            angle = -math.pi / 2 + 2 * math.pi * index / len(DIMENSIONS)
            return QPointF(cx + radius * score / 100 * math.cos(angle), cy + radius * score / 100 * math.sin(angle))

        painter.setPen(QPen(grid, 1))
        for level in (20, 40, 60, 80, 100):
            painter.drawPolygon(QPolygonF([point(i, level) for i in range(len(DIMENSIONS))]))
        for index, name in enumerate(DIMENSIONS):
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(cx, cy), point(index, 100))
            label = point(index, 122)
            painter.setPen(fg)
            painter.drawText(int(label.x() - 50), int(label.y() - 10), 100, 20, Qt.AlignCenter, LABELS_ZH[name])
        for agent_index, agent in enumerate(self.agents):
            color = QColor(COLORS[agent_index % len(COLORS)])
            dims = agent.get("dimensions") or {}
            scores = [(dims.get(name) or {}).get("score") for name in DIMENSIONS]
            fill = QColor(color)
            fill.setAlpha(30)
            if all(score is not None for score in scores):
                painter.setPen(QPen(color, 2))
                painter.setBrush(QBrush(fill))
                painter.drawPolygon(QPolygonF([point(i, s) for i, s in enumerate(scores)]))
                painter.setBrush(Qt.NoBrush)
            else:
                painter.setPen(QPen(color, 2, Qt.DashLine))
                for start in range(len(DIMENSIONS)):
                    end = (start + 1) % len(DIMENSIONS)
                    if scores[start] is not None and scores[end] is not None:
                        painter.drawLine(point(start, scores[start]), point(end, scores[end]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            for index, score in enumerate(scores):
                if score is not None:
                    painter.drawEllipse(point(index, score), 3.5, 3.5)
            painter.setBrush(Qt.NoBrush)
            y = self.height() - legend_h + agent_index * 22 + 4
            painter.fillRect(12, y + 3, 12, 12, color)
            painter.setPen(fg)
            incomplete = "" if all(s is not None for s in scores) else "（维度不全，虚线）"
            synthetic = "（synthetic，不计成绩）" if agent.get("synthetic") else ""
            painter.drawText(30, y + 14, f"{agent.get('agent_id')}  总分 {fmt_score(agent.get('overall_score'))}"
                                         f"{synthetic}{incomplete}")
        painter.end()


class EventsDialog(QDialog):
    def __init__(self, parent: QWidget, run_dir: Path, first: int | None, last: int | None, focus: int | None):
        super().__init__(parent)
        self.setWindowTitle(f"证据事件 #{first}–#{last}")
        self.resize(900, 600)
        text = QPlainTextEdit(readOnly=True)
        text.setFont(QFont("monospace"))
        lines = []
        for item in read_events(run_dir, first, last):
            mark = ">> " if item.get("sequence") == focus else "   "
            payload = json.dumps(item.get("payload"), ensure_ascii=False)
            if len(payload) > 1200:
                payload = payload[:1200] + " …"
            lines.append(f"{mark}#{item.get('sequence')} {item.get('timestamp', '')} {item.get('event')} "
                         f"agent={item.get('agent_id')} case={item.get('case_id')} session={item.get('session_id')}\n"
                         f"      {payload}")
        text.setPlainText("\n".join(lines) or "没有找到该范围的事件（events.jsonl 缺失或该用例没有证据）。")
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(buttons)


class ResultsPage(QWidget):
    status_message = Signal(str)

    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window = window
        self.view: RunView | None = None
        self.rows: list[dict[str, Any]] = []
        self.process: QProcess | None = None

        self.run_list = QListWidget()
        self.run_list.itemSelectionChanged.connect(self._selected_run)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        other = QPushButton("打开其他运行目录…")
        other.clicked.connect(self._choose_dir)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("已保存的运行（runs/）"))
        left_layout.addWidget(self.run_list)
        buttons = QHBoxLayout()
        buttons.addWidget(refresh)
        buttons.addWidget(other)
        left_layout.addLayout(buttons)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        self.title = QLabel("选择左侧的运行查看结果")
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title_font = self.title.font()
        title_font.setPointSize(title_font.pointSize() + 3)
        title_font.setBold(True)
        self.title.setFont(title_font)
        self.radar = RadarWidget()
        self.scores = QTableWidget()
        self.scores.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.scores.verticalHeader().setVisible(False)
        note = QLabel("维度分 = 100 × pass / (pass + fail)；unknown、error、unsupported 不进分母、单列并降低覆盖率；"
                      "任一维度缺失时总分为空。全部为确定性规则评分。")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        score_box = QWidget()
        score_layout = QVBoxLayout(score_box)
        score_layout.setContentsMargins(0, 0, 0, 0)
        score_layout.addWidget(self.scores)
        score_layout.addWidget(note)
        top = QSplitter(Qt.Horizontal)
        top.addWidget(self.radar)
        top.addWidget(score_box)
        top.setSizes([420, 560])

        self.f_agent, self.f_status, self.f_dim = QComboBox(), QComboBox(), QComboBox()
        for combo in (self.f_agent, self.f_status, self.f_dim):
            combo.setMinimumWidth(130)
            combo.currentIndexChanged.connect(self._fill_cases)
        self.count = QLabel()
        filters = QHBoxLayout()
        for label, combo in (("Agent", self.f_agent), ("状态", self.f_status), ("维度", self.f_dim)):
            filters.addWidget(QLabel(label))
            filters.addWidget(combo)
        filters.addWidget(self.count)
        filters.addStretch()
        self.cases = QTableWidget(0, 5)
        self.cases.setHorizontalHeaderLabels(["状态", "用例", "维度", "Agent", "耗时(秒)"])
        self.cases.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cases.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cases.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cases.verticalHeader().setVisible(False)
        self.cases.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cases.itemSelectionChanged.connect(self._show_case)
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(self._anchor)
        case_split = QSplitter(Qt.Horizontal)
        case_split.addWidget(self.cases)
        case_split.addWidget(self.detail)
        case_split.setSizes([560, 640])
        case_tab = QWidget()
        case_layout = QVBoxLayout(case_tab)
        case_layout.addLayout(filters)
        case_layout.addWidget(case_split, 1)

        self.env = QTableWidget(0, 2)
        self.env.setHorizontalHeaderLabels(["项目", "值"])
        self.env.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.env.verticalHeader().setVisible(False)
        self.env.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        self.report_btn = QPushButton("生成 / 校验报告（report --reuse）")
        self.report_btn.clicked.connect(self._report)
        self.radar_btn = QPushButton("打开 radar.png")
        self.radar_btn.clicked.connect(lambda: self._open(self.view.radar_png if self.view else None))
        self.folder_btn = QPushButton("打开运行目录")
        self.folder_btn.clicked.connect(lambda: self._open(self.view.run_dir if self.view else None))
        self.rescore_btn = QPushButton("离线重评（rescore，不调用 Agent）")
        self.rescore_btn.clicked.connect(self._rescore)
        self.tool_log = QPlainTextEdit(readOnly=True)
        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        row = QHBoxLayout()
        for button in (self.report_btn, self.radar_btn, self.folder_btn, self.rescore_btn):
            row.addWidget(button)
            button.setEnabled(False)
        row.addStretch()
        files_layout.addLayout(row)
        files_layout.addWidget(self.tool_log)

        self.tabs = QTabWidget()
        self.tabs.addTab(case_tab, "逐条结果与评分理由")
        self.tabs.addTab(self.env, "运行环境与可追溯信息")
        self.tabs.addTab(files_tab, "报告与重评")

        right = QSplitter(Qt.Vertical)
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(self.title)
        header_layout.addWidget(self.banner)
        header_layout.addWidget(top)
        right.addWidget(header)
        right.addWidget(self.tabs)
        right.setSizes([420, 520])

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([280, 1000])
        layout = QVBoxLayout(self)
        layout.addWidget(split)

    # ----- run list -----
    def refresh(self, select: Path | None = None) -> None:
        project = self.window.project
        self.run_list.blockSignals(True)
        self.run_list.clear()
        for run_dir in discover_runs(project) if project else []:
            item = QListWidgetItem(str(run_dir.relative_to(project / "runs")))
            item.setData(Qt.UserRole, str(run_dir))
            item.setToolTip(str(run_dir))
            self.run_list.addItem(item)
        self.run_list.blockSignals(False)
        if select:
            for index in range(self.run_list.count()):
                if Path(self.run_list.item(index).data(Qt.UserRole)) == select:
                    self.run_list.setCurrentRow(index)
                    return
            self.load(select)

    def _selected_run(self) -> None:
        items = self.run_list.selectedItems()
        if items:
            self.load(Path(items[0].data(Qt.UserRole)))

    def _choose_dir(self) -> None:
        start = str(self.window.project / "runs") if self.window.project else ""
        chosen = QFileDialog.getExistingDirectory(self, "选择运行目录（包含 results.json）", start)
        if chosen:
            self.load(Path(chosen))

    # ----- one run -----
    def load(self, run_dir: Path) -> bool:
        try:
            view = load_run(run_dir)
        except RunLoadError as error:
            self.view = None
            self.title.setText(f"无法显示：{run_dir.name}")
            self._banner(str(error), "#c4321c")
            self.radar.set_agents([])
            self.scores.clear()
            self.scores.setRowCount(0)
            self.cases.setRowCount(0)
            self.detail.clear()
            self.env.setRowCount(0)
            for button in (self.report_btn, self.radar_btn, self.rescore_btn):
                button.setEnabled(False)
            self.folder_btn.setEnabled(run_dir.is_dir())
            return False
        self.view = view
        kind = "（重评修订）" if view.is_rescore else ""
        self.title.setText(f"Run {view.run_id}{kind} · {view.results.get('status')} · "
                           f"{view.results.get('dataset_case_count')} 条用例 × {len(view.agents)} 个 Agent")
        notes = list(view.warnings)
        if view.any_synthetic:
            notes.insert(0, "SYNTHETIC 管线验证：不是真实 Agent 成绩，不能计入两款真实智能体验收。")
        failed_agents = [str(a.get("agent_id")) for a in view.agents if a.get("status") != "completed"]
        if failed_agents:
            notes.append("Agent 执行未完成：" + "、".join(failed_agents) + "（见错误详情）")
        self._banner("\n".join(notes), "#c4321c" if view.any_synthetic or failed_agents else "#8a6d00")
        self.radar.set_agents(view.agents)
        self._fill_scores()
        self._fill_env()
        self.rows = view.case_rows()
        self._reset_filters()
        self._fill_cases()
        self.report_btn.setEnabled(True)
        self.radar_btn.setEnabled(view.radar_png is not None)
        self.folder_btn.setEnabled(True)
        self.rescore_btn.setEnabled((view.run_dir / "events.jsonl").is_file()
                                    and (view.run_dir / "dataset.snapshot.jsonl").is_file())
        self.status_message.emit(f"已载入 {view.run_dir}")
        return True

    def _banner(self, text: str, color: str) -> None:
        self.banner.setText(text)
        self.banner.setStyleSheet(f"background:{color}; color:white; padding:6px; border-radius:4px; font-weight:600")
        self.banner.setVisible(bool(text))

    def _fill_scores(self) -> None:
        agents = self.view.agents
        self.scores.clear()
        self.scores.setColumnCount(1 + len(agents))
        self.scores.setHorizontalHeaderLabels(["维度"] + [str(a.get("agent_id")) for a in agents])
        self.scores.setRowCount(len(DIMENSIONS) + 2)
        for row, name in enumerate(DIMENSIONS):
            self.scores.setItem(row, 0, QTableWidgetItem(f"{LABELS_ZH[name]}  {name}"))
            for col, agent in enumerate(agents, start=1):
                item = (agent.get("dimensions") or {}).get(name) or {}
                coverage = item.get("scorable_coverage")
                text = (f"{fmt_score(item.get('score'))}   {item.get('pass', 0)}/{item.get('scorable', 0)}"
                        f"   覆盖 {'—' if coverage is None else f'{coverage:.0f}%'}")
                cell = QTableWidgetItem(text)
                if item.get("score") is not None and item.get("score") < 100:
                    cell.setForeground(QColor(STATUS_COLORS["fail"]))
                self.scores.setItem(row, col, cell)
        total_row = len(DIMENSIONS)
        bold = QFont()
        bold.setBold(True)
        head = QTableWidgetItem("六维总分")
        head.setFont(bold)
        self.scores.setItem(total_row, 0, head)
        self.scores.setItem(total_row + 1, 0, QTableWidgetItem("状态分布"))
        for col, agent in enumerate(agents, start=1):
            cell = QTableWidgetItem(fmt_score(agent.get("overall_score")))
            cell.setFont(bold)
            self.scores.setItem(total_row, col, cell)
            dims = (agent.get("dimensions") or {}).values()
            counts = {s: sum(int(d.get(s, 0) or 0) for d in dims) for s in STATUSES}
            self.scores.setItem(total_row + 1, col, QTableWidgetItem(
                "  ".join(f"{s} {n}" for s, n in counts.items() if n) or "无"))
        self.scores.resizeColumnsToContents()
        self.scores.horizontalHeader().setStretchLastSection(True)

    def _fill_env(self) -> None:
        rows = self.view.environment()
        self.env.setRowCount(len(rows))
        for index, (key, value) in enumerate(rows):
            self.env.setItem(index, 0, QTableWidgetItem(key))
            self.env.setItem(index, 1, QTableWidgetItem(value))
        self.env.resizeColumnToContents(0)

    def _reset_filters(self) -> None:
        def fill(combo: QComboBox, everything: str, values: list[tuple[str, str]]) -> None:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(everything, "")
            for label, value in values:
                combo.addItem(label, value)
            combo.blockSignals(False)

        fill(self.f_agent, "全部", [(str(a.get("agent_id")), str(a.get("agent_id"))) for a in self.view.agents])
        seen = sorted({str(r["status"]) for r in self.rows}, key=lambda s: (STATUSES + (s,)).index(s))
        fill(self.f_status, "全部", [(status_label(s), s) for s in seen])
        fill(self.f_dim, "全部", [(LABELS_ZH[d], d) for d in DIMENSIONS])

    def _fill_cases(self) -> None:
        agent, status, dim = self.f_agent.currentData(), self.f_status.currentData(), self.f_dim.currentData()
        shown = [r for r in self.rows if (not agent or r["agent_id"] == agent) and (not status or str(r["status"]) == status)
                 and (not dim or r["category"] == dim)]
        self.cases.setRowCount(len(shown))
        for index, row in enumerate(shown):
            status_item = QTableWidgetItem(status_label(row["status"]))
            status_item.setForeground(QColor(STATUS_COLORS.get(row["status"], "#8a6d00")))
            status_item.setData(Qt.UserRole, row)
            self.cases.setItem(index, 0, status_item)
            self.cases.setItem(index, 1, QTableWidgetItem(str(row["case_id"])))
            self.cases.setItem(index, 2, QTableWidgetItem(LABELS_ZH.get(row["category"], str(row["category"]))))
            self.cases.setItem(index, 3, QTableWidgetItem(str(row["agent_id"]) + (" (synthetic)" if row["synthetic"] else "")))
            duration = row["duration"]
            self.cases.setItem(index, 4, QTableWidgetItem("" if duration is None else f"{duration:.1f}"))
        self.cases.resizeColumnToContents(0)
        self.count.setText(f"{len(shown)} 条")
        self.detail.setHtml("<p style='color:gray'>选择一条用例查看评分理由与证据。</p>")
        if shown and self.f_status.currentData() and len(shown) <= 3:
            self.cases.selectRow(0)

    def _show_case(self) -> None:
        items = self.cases.selectedItems()
        if not items:
            return
        row = self.cases.item(items[0].row(), 0).data(Qt.UserRole)
        case = row["case"]
        evidence = case.get("evidence") or {}
        first, last = evidence.get("first_sequence"), evidence.get("last_sequence")
        parts = [f"<h3>{esc(row['case_id'])} · {esc(LABELS_ZH.get(row['category'], row['category']))} · "
                 f"{esc(row['agent_id'])}</h3><p><b>{esc(status_label(row['status']))}</b>"]
        if first is not None:
            parts.append(f" · 证据 events #{esc(first)}–#{esc(last)} "
                         f"<a href='events:{esc(first)}:{esc(last)}:'>查看证据事件</a>")
        parts.append("</p>")
        if case.get("error"):
            parts.append(f"<p style='color:#c4321c'><b>执行错误：</b>{esc((case['error'] or {}).get('message'))}</p>")
        if case.get("missing_capabilities"):
            parts.append(f"<p><b>不支持：</b>缺少能力 {esc(', '.join(case['missing_capabilities']))}</p>")
        for probe in case.get("probes") or []:
            evaluation = probe.get("evaluation") or {}
            color = STATUS_COLORS.get(probe.get("status"), "#8a6d00")
            parts.append(f"<hr><p><b>{esc(probe.get('probe_id'))}</b> "
                         f"<span style='color:gray'>{esc(probe.get('kind'))} · {esc(evaluation.get('scope'))} · "
                         f"会话 {esc(probe.get('session_id'))}</span> "
                         f"<b style='color:{color}'>{esc(status_label(probe.get('status')))}</b>")
            if probe.get("evaluation_event") is not None:
                seq = probe["evaluation_event"]
                parts.append(f" · <a href='events:{esc(first if first is not None else seq)}:"
                             f"{esc(last if last is not None else seq)}:{esc(seq)}'>评分事件 #{esc(seq)}</a>")
            parts.append(f"</p><p><b>评分理由：</b>{esc(evaluation.get('explanation') or '（无）')}</p>")
            for label, key in (("必须包含", "required_terms"), ("禁止出现", "forbidden_terms"),
                               ("缺失", "missing_terms"), ("命中禁止项", "forbidden_hits")):
                if evaluation.get(key):
                    parts.append(f"<p>{label}：<code>{esc('　'.join(map(str, evaluation[key])))}</code></p>")
            if probe.get("kind") == "probe" and probe.get("response") is not None:
                parts.append(f"<p style='color:gray'>Agent 回答</p><pre>{esc(str(probe['response'])[:4000])}</pre>")
            elif evaluation.get("scored_text"):
                parts.append(f"<p style='color:gray'>被检查的内容</p><pre>{esc(str(evaluation['scored_text'])[:4000])}</pre>")
        if not case.get("probes") and not case.get("error"):
            parts.append("<p style='color:gray'>该用例没有检查记录。</p>")
        self.detail.setHtml("".join(parts))

    def _anchor(self, url: QUrl) -> None:
        text = url.toString()
        if not text.startswith("events:") or not self.view:
            return
        _, first, last, focus = (text.split(":") + ["", "", ""])[:4]
        as_int = lambda value: int(value) if value.lstrip("-").isdigit() else None  # noqa: E731
        EventsDialog(self, self.view.run_dir, as_int(first), as_int(last), as_int(focus)).exec()

    # ----- tools via the CLI -----
    def _open(self, path: Path | None) -> None:
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _cli(self, args: list[str], done) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "请稍候", "上一个命令还在执行。")
            return
        process = QProcess(self)
        process.setWorkingDirectory(str(self.window.project or Path.cwd()))
        command = cli_command(*args)
        process.setProgram(command[0])
        process.setArguments(command[1:])
        self.tool_log.appendPlainText("$ memoryscope " + " ".join(args))

        def finished(code: int, _status) -> None:
            out = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
            err = bytes(process.readAllStandardError()).decode("utf-8", "replace")
            message = next((m for m in map(parse_cli_line, out.splitlines()) if m), None)
            if err.strip():
                self.tool_log.appendPlainText(err.strip()[-2000:])
            done(code, message)

        process.finished.connect(finished)
        self.process = process
        process.start()

    def _report(self) -> None:
        if not self.view:
            return
        run_dir = self.view.run_dir

        def done(code: int, message: dict | None) -> None:
            if code == 0 and message and message.get("ok"):
                self.tool_log.appendPlainText(f"报告就绪：{message['data'].get('report_dir')}")
                self.load(run_dir)
            else:
                error = (message or {}).get("error") or {}
                self.tool_log.appendPlainText(f"报告失败（退出码 {code}）：{error.get('message', '见上方输出')}；"
                                              "原始结果仍可查看。")

        self._cli(["report", str(run_dir), "--json", "--reuse"], done)

    def _rescore(self) -> None:
        if not self.view:
            return

        def done(code: int, message: dict | None) -> None:
            if code == 0 and message and message.get("ok"):
                data = message["data"]
                changes = data.get("status_changes") or []
                self.tool_log.appendPlainText(f"重评完成：{data.get('run_dir')}；{len(changes)} 项状态变化")
                for change in changes:
                    self.tool_log.appendPlainText(f"  {change.get('agent_id')}/{change.get('case_id')}/"
                                                  f"{change.get('check_id')}: {change.get('old')} -> {change.get('new')}")
                self.refresh(select=Path(data["run_dir"]))
            else:
                error = (message or {}).get("error") or {}
                self.tool_log.appendPlainText(f"重评失败（退出码 {code}）：{error.get('message', '见上方输出')}")

        self._cli(["rescore", str(self.view.run_dir), "--json"], done)


class RunPage(QWidget):
    run_ready = Signal(Path)

    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self.window = window
        self.process: QProcess | None = None
        self.request = None
        self.run_dir: Path | None = None
        self.final: dict[str, Any] | None = None
        self.stdout_buffer = b""
        self.tail: EventTail | None = None
        self.agent_rows: dict[str, tuple[QCheckBox, QLineEdit, QSpinBox, bool]] = {}

        self.dataset = QComboBox()
        browse = QPushButton("选择…")
        browse.clicked.connect(self._browse_dataset)
        dataset_row = QHBoxLayout()
        dataset_row.addWidget(self.dataset, 1)
        dataset_row.addWidget(browse)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2**31 - 1)
        self.seed.setMaximumWidth(160)
        form = QFormLayout()
        form.addRow("数据集", dataset_row)
        form.addRow("随机种子", self.seed)

        self.agent_box = QGroupBox("被测 Agent")
        self.agent_grid = QGridLayout(self.agent_box)
        self.key_label = QLabel()
        self.key_label.setWordWrap(True)

        self.check_btn = QPushButton("预检配置（不调用 API）")
        self.check_btn.clicked.connect(self._check)
        self.start_btn = QPushButton("开始评测")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        buttons = QHBoxLayout()
        for button in (self.check_btn, self.start_btn, self.stop_btn):
            buttons.addWidget(button)
        buttons.addStretch()

        self.phase = QLabel("尚未开始。打开本页不会启动任何评测。")
        self.phase.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setFormat("等待开始")
        self.progress.setValue(0)
        self.progress.setMaximum(1)
        self.counts = QLabel()
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(5000)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.agent_box)
        layout.addWidget(self.key_label)
        layout.addLayout(buttons)
        layout.addWidget(self.phase)
        layout.addWidget(self.progress)
        layout.addWidget(self.counts)
        layout.addWidget(self.log, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._poll_events)

    def populate(self) -> None:
        from memoryscope.adapters import adapter_catalog

        project = self.window.project
        self.dataset.clear()
        if project:
            for path in sorted((project / "datasets").iterdir()):
                if path.is_dir() and any(path.glob("*.jsonl")):
                    self.dataset.addItem(str(path.relative_to(project)), str(path))
            golden = self.dataset.findText("datasets/golden")
            if golden >= 0:
                self.dataset.setCurrentIndex(golden)
        while self.agent_grid.count():
            widget = self.agent_grid.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        self.agent_rows.clear()
        for col, title in enumerate(["启用", "Adapter", "模型", "超时(秒)"]):
            self.agent_grid.addWidget(QLabel(f"<b>{title}</b>"), 0, col)
        for row, item in enumerate(adapter_catalog(), start=1):
            enabled = QCheckBox(item["id"])
            enabled.setChecked(not item["synthetic"])
            name = item["name"] + ("（synthetic，仅测框架，不计成绩）" if item["synthetic"] else "（真实 Agent，调用 API）")
            model = QLineEdit(DEFAULT_MODELS.get(item["id"], ""))
            model.setPlaceholderText("默认")
            model.setEnabled(not item["synthetic"])
            timeout = QSpinBox()
            timeout.setRange(10, 3600)
            timeout.setValue(300)
            self.agent_grid.addWidget(enabled, row, 0)
            self.agent_grid.addWidget(QLabel(name), row, 1)
            self.agent_grid.addWidget(model, row, 2)
            self.agent_grid.addWidget(timeout, row, 3)
            self.agent_rows[item["id"]] = (enabled, model, timeout, item["synthetic"])
        present = bool(project) and api_key_present(project)
        self.key_label.setText(
            ("已检测到 DEEPSEEK_API_KEY（来自环境变量或项目 .env；界面不显示其值）。" if present else
             "未检测到 DEEPSEEK_API_KEY：真实 Agent 会因缺少凭据报 error。请在项目 .env 中填写，界面不会读取或保存密钥。")
            + "真实 Agent 每条用例都会调用 DeepSeek API。")

    def _browse_dataset(self) -> None:
        start = str(self.window.project / "datasets") if self.window.project else ""
        chosen = QFileDialog.getExistingDirectory(self, "选择数据集目录（*.jsonl）", start)
        if chosen:
            self.dataset.addItem(chosen, chosen)
            self.dataset.setCurrentIndex(self.dataset.count() - 1)

    def _agents(self) -> list[dict[str, Any]]:
        agents = []
        for agent_id, (enabled, model, timeout, synthetic) in self.agent_rows.items():
            if enabled.isChecked():
                entry: dict[str, Any] = {"id": agent_id, "type": agent_id}
                if not synthetic:
                    if model.text().strip():
                        entry["model"] = model.text().strip()
                    entry["timeout_seconds"] = timeout.value()
                agents.append(entry)
        return agents

    def _new_request(self):
        project = self.window.project
        if not project:
            raise ValueError("没有项目目录")
        if not self.dataset.currentData():
            raise ValueError("没有可用的数据集")
        return write_request_config(project, Path(self.dataset.currentData()), self._agents(), self.seed.value())

    def _busy(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.NotRunning

    def _check(self) -> None:
        if self._busy():
            return
        try:
            request = self._new_request()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "配置无效", str(error))
            return
        self.log.appendPlainText(f"已生成请求配置 {request.config_path}")
        process = QProcess(self)
        command = cli_command("check-config", str(request.config_path), "--json")
        process.setWorkingDirectory(str(self.window.project))
        process.setProgram(command[0])
        process.setArguments(command[1:])

        def finished(code: int, _status) -> None:
            out = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
            message = next((m for m in map(parse_cli_line, out.splitlines()) if m), None)
            if code == 0 and message and message.get("ok"):
                info = message["data"]["dataset_info"]
                self.phase.setText(f"预检通过：{info['case_count']} 条用例，维度分布 {info['categories']}；未调用任何 Agent。")
            else:
                error = (message or {}).get("error") or {}
                err = bytes(process.readAllStandardError()).decode("utf-8", "replace")
                self.phase.setText(f"预检失败（退出码 {code}）：{error.get('message') or err.strip()[-500:]}")
            self.log.appendPlainText(self.phase.text())

        process.finished.connect(finished)
        self.process = process
        process.start()

    def _start(self) -> None:
        if self._busy():
            return
        agents = self._agents()
        if not agents:
            QMessageBox.warning(self, "配置无效", "至少选择一个 Agent。")
            return
        real = [a["id"] for a in agents if not self.agent_rows[a["id"]][3]]
        if real:
            answer = QMessageBox.question(
                self, "确认调用真实 Agent",
                f"将用真实 Agent（{', '.join(real)}）执行 {self.dataset.currentText()} 中的全部用例，"
                "每条用例都会调用 DeepSeek API 并产生费用。完整 48 条约需 1 小时。继续吗？")
            if answer != QMessageBox.Yes:
                return
        try:
            self.request = self._new_request()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "配置无效", str(error))
            return
        self.run_dir, self.final, self.stdout_buffer, self.tail = None, None, b"", None
        self.progress.setMaximum(1)
        self.progress.setValue(0)
        self.progress.setFormat("准备中")
        self.counts.clear()
        self.status_counts: dict[str, int] = {}
        self.log.appendPlainText(f"\n请求 {self.request.request_id}：配置 {self.request.config_path}")
        self.phase.setText("准备/校验中…（尚未得到运行目录）")
        process = QProcess(self)
        command = cli_command("run", str(self.request.config_path), "--jsonl")
        process.setWorkingDirectory(str(self.window.project))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.setProgram(command[0])
        process.setArguments(command[1:])
        process.readyReadStandardOutput.connect(self._stdout)
        process.readyReadStandardError.connect(
            lambda: self.log.appendPlainText(bytes(process.readAllStandardError()).decode("utf-8", "replace").rstrip()))
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self.process = process
        self.start_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.window.set_running(True)
        process.start()

    def _stdout(self) -> None:
        self.stdout_buffer += bytes(self.process.readAllStandardOutput())
        lines = self.stdout_buffer.split(b"\n")
        self.stdout_buffer = lines.pop()
        for raw in lines:
            self._handle_line(raw.decode("utf-8", "replace"))

    def _handle_line(self, line: str) -> None:
        message = parse_cli_line(line)
        if message is None:
            if line.strip():
                self.log.appendPlainText(line)
            return
        if message.get("type") == "progress":
            data = message.get("data") or {}
            event = data.get("event")
            if data.get("run_dir") and self.run_dir is None:
                self.run_dir = Path(data["run_dir"])
                self.tail = EventTail(self.run_dir / "events.jsonl")
                self.timer.start()
                self.log.appendPlainText(f"运行目录：{self.run_dir}")
            if data.get("planned_cases"):
                self.progress.setMaximum(int(data["planned_cases"]))
                self.progress.setFormat("%v / %m 个 case 完成")
            if data.get("completed_cases") is not None:
                self.progress.setValue(int(data["completed_cases"]))
            if event == "case_finished":
                status = str(data.get("status"))
                self.status_counts[status] = self.status_counts.get(status, 0) + 1
                self.counts.setText("  ".join(f"{status_label(k)} {v}" for k, v in self.status_counts.items()))
                self.log.appendPlainText(f"[{data.get('agent_id')}] {data.get('case_id')} → {status_label(status)}")
            elif event in ("run_started", "agent_started", "agent_finished", "run_finished", "progress_observer_error"):
                self.log.appendPlainText(f"{event} {data.get('agent_id') or ''}".rstrip())
            phase = f"执行中：{data.get('agent_id') or ''} {data.get('case_id') or ''}".strip()
            if data.get("synthetic"):
                phase += "（synthetic）"
            self.phase.setText(phase)
        elif message.get("type") == "result":
            self.final = message

    def _poll_events(self) -> None:
        if not self.tail:
            return
        for item in self.tail.read():
            if item.get("event") in ("case_error", "agent_error"):
                payload = json.dumps(item.get("payload"), ensure_ascii=False)[:300]
                self.log.appendPlainText(f"#{item.get('sequence')} {item.get('event')} {item.get('agent_id')} "
                                         f"{item.get('case_id') or ''} {payload}")

    def _stop(self) -> None:
        if not self._busy():
            return
        answer = QMessageBox.question(self, "停止评测", "停止后本次运行不会继续，已保存的证据保留但不完整。确定停止吗？")
        if answer == QMessageBox.Yes:
            self.log.appendPlainText("正在停止…")
            self.process.terminate()
            QTimer.singleShot(8000, lambda: self._busy() and self.process.kill())

    def _process_error(self, error) -> None:
        if error == QProcess.FailedToStart:
            self.phase.setText("无法启动 memoryscope 进程。")
            self._reset_buttons()

    def _reset_buttons(self) -> None:
        self.timer.stop()
        self.start_btn.setEnabled(True)
        self.check_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.window.set_running(False)

    def _finished(self, code: int, exit_status) -> None:
        if self.stdout_buffer:
            self._handle_line(self.stdout_buffer.decode("utf-8", "replace"))
            self.stdout_buffer = b""
        self._poll_events()
        self._reset_buttons()
        data = (self.final or {}).get("data") or {}
        run_dir = Path(data["run_dir"]) if data.get("run_dir") else self.run_dir
        crashed = exit_status == QProcess.CrashExit
        has_results = bool(run_dir and (run_dir / "results.json").is_file()
                           and (run_dir / "metadata.json").is_file())
        if self.final is None or crashed or code == 130:
            reason = "被中断" if code in (130, 143, 15) or crashed else f"异常退出（退出码 {code}）"
            self.phase.setText(f"评测{reason}，未完成。已保存的证据保留在 {run_dir or '（尚无运行目录）'}；可发起全新运行。")
            self.log.appendPlainText(self.phase.text())
            if run_dir and (run_dir / "results.json").is_file():
                self.run_ready.emit(run_dir)
            return
        if not has_results:
            error = (self.final.get("error") or {}).get("message", "")
            self.phase.setText(f"评测失败（退出码 {code}）：{error}")
            self.log.appendPlainText(self.phase.text())
            return
        verdict = "完成" if code == 0 else f"执行未全部完成（退出码 {code}，有 Agent 执行错误）"
        self.phase.setText(f"评测{verdict}：{run_dir}。正在生成报告…（completed 不代表全部 pass）")
        self.log.appendPlainText(self.phase.text())
        report = QProcess(self)
        command = cli_command("report", str(run_dir), "--json", "--reuse")
        report.setWorkingDirectory(str(self.window.project))
        report.setProgram(command[0])
        report.setArguments(command[1:])

        def report_done(report_code: int, _status) -> None:
            out = bytes(report.readAllStandardOutput()).decode("utf-8", "replace")
            message = next((m for m in map(parse_cli_line, out.splitlines()) if m), None)
            if report_code == 0 and message and message.get("ok"):
                self.phase.setText(f"评测{verdict}，报告已生成：{message['data'].get('report_dir')}")
            else:
                self.phase.setText(f"评测{verdict}；报告生成失败，原始结果仍可查看。")
            self.log.appendPlainText(self.phase.text())
            self.run_ready.emit(run_dir)

        report.finished.connect(report_done)
        report.start()


class MainWindow(QMainWindow):
    def __init__(self, project: Path | None) -> None:
        super().__init__()
        self.project = project
        self.running = False
        self.setWindowTitle("MemoryScope-OK 智能体长期记忆评测")
        self.resize(1360, 900)
        self.results = ResultsPage(self)
        self.runner = RunPage(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.results, "评测结果")
        self.tabs.addTab(self.runner, "新建评测")
        self.setCentralWidget(self.tabs)
        self.results.status_message.connect(self.statusBar().showMessage)
        self.runner.run_ready.connect(self._show_run)
        choose = QAction("选择项目目录…", self)
        choose.triggered.connect(self._choose_project)
        self.menuBar().addMenu("文件").addAction(choose)
        self.set_project(project)

    def set_project(self, project: Path | None) -> None:
        self.project = project
        self.statusBar().showMessage(f"项目目录：{project}" if project else "未找到项目目录，请从“文件”菜单选择")
        self.results.refresh()
        self.runner.populate()

    def _choose_project(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择项目目录（含 pyproject.toml 与 datasets/）")
        if chosen:
            project = find_project(Path(chosen))
            if project is None:
                QMessageBox.warning(self, "不是项目目录", "该目录及其上级都没有 pyproject.toml 和 datasets/。")
                return
            self.set_project(project)

    def set_running(self, running: bool) -> None:
        self.running = running
        self.tabs.setTabText(1, "新建评测（运行中）" if running else "新建评测")

    def _show_run(self, run_dir: Path) -> None:
        self.results.refresh(select=run_dir)
        self.tabs.setCurrentWidget(self.results)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.running:
            answer = QMessageBox.question(
                self, "评测仍在运行",
                "评测进程仍在运行。关闭窗口会停止它，本次运行将不完整（已保存的证据保留）。确定关闭吗？")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            process = self.runner.process
            if process is not None:
                process.terminate()
                process.waitForFinished(8000)
        event.accept()


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("MemoryScope-OK")
    explicit = Path(argv[1]) if len(argv) > 1 else None
    project = find_project(explicit) if explicit else (
        find_project() or find_project(Path(os.environ.get("MEMORYSCOPE_HOME", Path.home() / "memoryscope-ok"))))
    window = MainWindow(project)
    window.show()
    if explicit and explicit.is_dir() and (explicit / "results.json").is_file():
        window.results.load(explicit)
    sys.exit(app.exec())
