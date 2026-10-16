"""Self-contained HTML view of a saved run: radar, scores, per-check reasons.

Built offline from ``results.json`` and ``metadata.json``; agents are never
called and nothing is fetched from the network, so the page opens in any
browser on the openKylin desktop. The file is derived data: rebuilding it
replaces the previous ``view.html`` atomically and never touches ``report/``.
"""

import html
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

from memoryscope.models import Category
from memoryscope.reporting import COLORS, LABELS_ZH, load_results

STATUSES = ("pass", "fail", "unknown", "error", "unsupported")


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def radar_svg(result: dict[str, Any], size: int = 420) -> str:
    """Radar as inline SVG; a missing dimension is a gap, never 0 or 100."""
    names = [category.value for category in Category]
    cx = cy = size / 2
    radius = size / 2 - 70

    def point(index: int, score: float) -> tuple[float, float]:
        angle = -math.pi / 2 + 2 * math.pi * index / len(names)
        return cx + radius * score / 100 * math.cos(angle), cy + radius * score / 100 * math.sin(angle)

    parts = [f'<svg class="radar" viewBox="0 0 {size} {size}" role="img" aria-label="六维雷达图">']
    for level in (20, 40, 60, 80, 100):
        ring = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, level) for i in range(len(names))))
        parts.append(f'<polygon class="grid" points="{ring}"/>')
    for index, name in enumerate(names):
        x, y = point(index, 100)
        parts.append(f'<line class="grid" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>')
        lx, ly = point(index, 118)
        anchor = "middle" if abs(lx - cx) < 5 else ("start" if lx > cx else "end")
        parts.append(f'<text class="axis" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{_e(LABELS_ZH[name])}</text>')
    parts.append(f'<text class="tick" x="{cx + 4}" y="{cy - radius - 4:.1f}">100</text>')
    for agent_index, agent in enumerate(result["agent_results"]):
        color = COLORS[agent_index % len(COLORS)]
        scores = [agent["dimensions"][name]["score"] for name in names]
        dash = "" if all(score is not None for score in scores) else ' stroke-dasharray="6 4"'
        if not dash:
            shape = " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, s) for i, s in enumerate(scores)))
            parts.append(f'<polygon points="{shape}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="2"/>')
        else:
            for start in range(len(names)):
                end = (start + 1) % len(names)
                if scores[start] is not None and scores[end] is not None:
                    (x1, y1), (x2, y2) = point(start, scores[start]), point(end, scores[end])
                    parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                                 f'stroke="{color}" stroke-width="2"{dash}/>')
        for index, score in enumerate(scores):
            if score is not None:
                x, y = point(index, score)
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}">'
                             f'<title>{_e(agent["agent_id"])} · {_e(LABELS_ZH[names[index]])}: {score:.1f}</title></circle>')
    parts.append("</svg>")
    return "".join(parts)


def _legend(result: dict[str, Any]) -> str:
    items = []
    for index, agent in enumerate(result["agent_results"]):
        describe = agent.get("describe") or {}
        tag = "（synthetic，不是真实 Agent）" if agent["synthetic"] else ""
        items.append(f'<li><span class="swatch" style="background:{COLORS[index % len(COLORS)]}"></span>'
                     f'<b>{_e(agent["agent_id"])}</b>{_e(tag)} '
                     f'<span class="muted">{_e(describe.get("version", ""))} · {_e(describe.get("model", ""))}</span></li>')
    return '<ul class="legend">' + "".join(items) + "</ul>"


def _score_table(result: dict[str, Any]) -> str:
    agents = result["agent_results"]
    head = "".join(f"<th>{_e(agent['agent_id'])}</th>" for agent in agents)
    rows = []
    for category in Category:
        cells = []
        for agent in agents:
            item = agent["dimensions"][category.value]
            cls = "" if item["score"] in (None, 100.0) else ' class="warn"'
            cells.append(f"<td{cls}><b>{_fmt(item['score'])}</b> <span class='muted'>"
                         f"{item['pass']}/{item['scorable']}</span></td>")
        rows.append(f"<tr><th>{_e(LABELS_ZH[category.value])} <code>{category.value}</code></th>{''.join(cells)}</tr>")
    overall = "".join(f"<td><b>{_fmt(agent['overall_score'])}</b></td>" for agent in agents)
    rows.append(f'<tr class="total"><th>六维总分</th>{overall}</tr>')
    counts = []
    for agent in agents:
        total = {s: sum(item[s] for item in agent["dimensions"].values()) for s in STATUSES}
        counts.append("<td>" + " ".join(f'<span class="st {s}">{s} {total[s]}</span>' for s in STATUSES if total[s])
                      + "</td>")
    rows.append(f"<tr><th>状态分布</th>{''.join(counts)}</tr>")
    return f'<table class="scores"><thead><tr><th>维度</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _cases(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for agent in result["agent_results"]:
        for case in agent["cases"]:
            checks = []
            for probe in case.get("probes") or []:
                evaluation = probe.get("evaluation") or {}
                checks.append({
                    "id": probe.get("probe_id"), "kind": probe.get("kind"), "status": probe.get("status"),
                    "session": probe.get("session_id"), "event": probe.get("evaluation_event"),
                    "explanation": evaluation.get("explanation"), "scope": evaluation.get("scope"),
                    "required": evaluation.get("required_terms") or [], "forbidden": evaluation.get("forbidden_terms") or [],
                    "missing": evaluation.get("missing_terms") or [], "hits": evaluation.get("forbidden_hits") or [],
                    "scored": (evaluation.get("scored_text") or "")[:1500], "response": (probe.get("response") or "")[:3000],
                })
            evidence = case.get("evidence") or {}
            rows.append({
                "agent": agent["agent_id"], "case": case["case_id"], "category": case["category"],
                "status": case["status"], "seconds": case.get("duration_seconds"),
                "events": [evidence.get("first_sequence"), evidence.get("last_sequence")],
                "error": (case.get("error") or {}).get("message", "")[:500],
                "missing_capabilities": case.get("missing_capabilities") or [], "checks": checks,
            })
    return rows


def _environment(run_dir: Path) -> str:
    try:
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return '<p class="muted">metadata.json 不可读，环境信息缺失。</p>'
    osr = metadata.get("os_release") or {}
    evaluator = metadata.get("evaluator") or {}
    items = [
        ("系统", osr.get("PRETTY_NAME") or metadata.get("platform")), ("平台", metadata.get("platform")),
        ("Python", metadata.get("python_version") or metadata.get("python")),
        ("MemoryScope-OK", metadata.get("package_version")), ("评分器", evaluator.get("version")),
        ("开始", metadata.get("started_at")), ("结束", metadata.get("finished_at")),
        ("事件数", metadata.get("event_count")),
        ("results.json SHA-256", ((metadata.get("artifacts") or {}).get("results.json") or {}).get("sha256")),
    ]
    return "<dl>" + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in items if v not in (None, "")) + "</dl>"


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1d1d1f;--muted:#6b6b70;--line:#dcdcdc;--grid:#c9c9cc;--warn:#fff4e5;
--pass:#0f7b45;--fail:#c4321c;--other:#8a6d00}
@media (prefers-color-scheme:dark){:root{--bg:#18181a;--card:#222225;--fg:#ececec;--muted:#a0a0a6;--line:#38383c;
--grid:#4a4a50;--warn:#3a2c14;--pass:#4cc38a;--fail:#ff7a66;--other:#e0c35c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 "Noto Sans CJK SC","Source Han Sans SC","PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}
h2{font-size:18px;margin:28px 0 10px}.muted{color:var(--muted)}code{font-size:12px;color:var(--muted)}
.banner{background:var(--fail);color:#fff;padding:10px 14px;border-radius:8px;font-weight:600;margin:12px 0}
.grid2{display:grid;grid-template-columns:minmax(300px,440px) 1fr;gap:20px;align-items:start}
@media (max-width:820px){.grid2{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.radar{width:100%;height:auto}.radar .grid{fill:none;stroke:var(--grid);stroke-width:1}
.radar .axis{fill:var(--fg);font-size:14px}.radar .tick{fill:var(--muted);font-size:10px}
.legend{list-style:none;padding:0;margin:8px 0 0}.legend li{margin:4px 0}
.swatch{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);
vertical-align:top}.scores td{white-space:nowrap}.scores .warn{background:var(--warn)}.total th,.total td{font-size:16px}
.st{display:inline-block;padding:0 7px;border-radius:10px;font-size:12px;border:1px solid currentColor;margin:1px 2px}
.st.pass{color:var(--pass)}.st.fail{color:var(--fail)}.st.unknown,.st.error,.st.unsupported{color:var(--other)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:0;font-size:13px}dt{color:var(--muted)}
dd{margin:0;word-break:break-all}.filters{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0 12px}
select{font:inherit;padding:4px 8px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px}
details{border-bottom:1px solid var(--line);padding:6px 0}summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}summary .id{font-family:monospace;margin:0 8px}
.check{margin:8px 0 8px 18px;padding:8px 12px;border-left:3px solid var(--line);font-size:14px}
.check.fail{border-color:var(--fail)}.check.pass{border-color:var(--pass)}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:8px;border-radius:6px;margin:4px 0;font-size:13px}
.terms span{font-family:monospace;padding:0 4px;border-radius:4px;background:var(--bg);margin-right:4px}
"""

SCRIPT = """
const rows=JSON.parse(document.getElementById('case-data').textContent);
const list=document.getElementById('cases');const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const zh=JSON.parse(document.getElementById('labels').textContent);
function terms(label,xs){return xs.length?`<div class="terms">${label}：${xs.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}
function render(){const a=fa.value,s=fs.value,c=fc.value;let n=0;
list.innerHTML=rows.filter(r=>(!a||r.agent===a)&&(!s||r.status===s)&&(!c||r.category===c)).map(r=>{n++;
const checks=r.checks.map(k=>`<div class="check ${esc(k.status)}"><b>${esc(k.id)}</b> <code>${esc(k.kind)} · ${esc(k.scope)} · 会话 ${esc(k.session)} · 事件 #${esc(k.event)}</code> <span class="st ${esc(k.status)}">${esc(k.status)}</span>
<div>评分理由：${esc(k.explanation)}</div>${terms('必须包含',k.required)}${terms('禁止出现',k.forbidden)}${terms('缺失',k.missing)}${terms('命中禁止项',k.hits)}
${k.kind==='probe'?`<div class="muted">Agent 回答</div><pre>${esc(k.response)}</pre>`:''}${k.scored&&k.kind!=='probe'?`<div class="muted">被检查的内容</div><pre>${esc(k.scored)}</pre>`:''}</div>`).join('');
const extra=(r.error?`<div class="check fail">error：${esc(r.error)}</div>`:'')+(r.missing_capabilities.length?`<div class="check">unsupported：缺少能力 ${esc(r.missing_capabilities.join(', '))}</div>`:'');
return `<details${r.status!=='pass'?' open':''}><summary><span class="st ${esc(r.status)}">${esc(r.status)}</span><span class="id">${esc(r.case)}</span>${esc(zh[r.category]||r.category)} · <b>${esc(r.agent)}</b> <span class="muted">${r.seconds!=null?r.seconds.toFixed(1)+' 秒 · ':''}events #${esc(r.events[0])}–#${esc(r.events[1])}</span></summary>${checks}${extra}</details>`}).join('');
count.textContent=n+' 条';}
const fa=document.getElementById('fa'),fs=document.getElementById('fs'),fc=document.getElementById('fc'),count=document.getElementById('count');
[fa,fs,fc].forEach(x=>x.addEventListener('change',render));render();
"""


def build_html(result: dict[str, Any], run_dir: Path) -> str:
    agents = [agent["agent_id"] for agent in result["agent_results"]]
    cases = _cases(result)
    data = json.dumps(cases, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    labels = json.dumps(LABELS_ZH, ensure_ascii=False).replace("<", "\\u003c")
    synthetic = ('<div class="banner">SYNTHETIC 管线验证：不是真实 Agent 成绩，不能计入两款真实智能体验收。</div>'
                 if result["synthetic"] else "")
    options = lambda values, label: f'<option value="">{label}</option>' + "".join(
        f'<option value="{_e(v)}">{_e(LABELS_ZH.get(v, v))}</option>' for v in values)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemoryScope-OK 评测结果</title><style>{CSS}</style></head><body><main>
<h1>MemoryScope-OK 智能体长期记忆评测</h1>
<div class="muted">Run <code>{_e(result['run_id'])}</code> · 状态 {_e(result['status'])} · {result['dataset_case_count']} 条用例 × {len(agents)} 个 Agent · {'synthetic' if result['synthetic'] else '真实 Agent 实测'}</div>
{synthetic}
<div class="grid2" style="margin-top:16px">
<div class="card">{radar_svg(result)}{_legend(result)}</div>
<div class="card"><h2 style="margin-top:0">六维得分</h2>{_score_table(result)}
<p class="muted" style="font-size:13px">维度分 = 100 × pass / (pass + fail)；unknown、error、unsupported 不进分母、单列并降低覆盖率；任一维度缺失时总分为空。全部为确定性规则评分，未使用 LLM Judge。</p></div>
</div>
<h2>运行环境与可追溯信息</h2><div class="card">{_environment(run_dir)}</div>
<h2>逐条结果与评分理由 <span id="count" class="muted" style="font-size:14px"></span></h2>
<div class="filters"><select id="fa">{options(agents, '全部 Agent')}</select>
<select id="fs">{options(STATUSES, '全部状态')}</select>
<select id="fc">{options([c.value for c in Category], '全部维度')}</select></div>
<div class="card" id="cases"></div>
<p class="muted" style="font-size:13px">原始证据：同目录 <code>events.jsonl</code>，事件序号与上面 #编号对应；本页由 <code>memoryscope view</code> 离线生成，不调用 Agent、不联网。</p>
</main>
<script type="application/json" id="case-data">{data}</script>
<script type="application/json" id="labels">{labels}</script>
<script>{SCRIPT}</script></body></html>
"""


def build_view(run_dir: Path) -> Path:
    result = load_results(run_dir)
    content = build_html(result, run_dir)
    target = run_dir / "view.html"
    handle, temp = tempfile.mkstemp(prefix=".view-", suffix=".html", dir=run_dir)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return target
