"""架构图纸渲染：单文件 SVG / HTML，零第三方依赖，面向不懂技术的人。

三种视角：
- render_svg   ：四栏清单式（组件 / 模块 / 能力 / 数据流），详尽但需滚动。
- render_map   ：地图式，系统 + 模块一屏纵览，点击模块钻取组件（单文件 HTML）。
- render_focus ：聚焦式，以被改节点为中心的同心环，红=被依赖 / 蓝=包含（单文件 SVG）。

四栏视图（render_svg）从左到右：组件 / 模块 / 能力 / 数据流。
- contains 用「容器框」表达（模块框圈住其组件；能力框列出实现组件）。
- depends 用箭头表达（数据流栏逐个画出「谁依赖谁」）。
- highlight 的节点用橙色高亮；图例说明颜色与箭头含义。
- 节点标签一律用中文能力名或文件名，不把能力码原文当主标签。
"""
from __future__ import annotations

import math

from xml.sax.saxutils import escape

from .graph import NODE_TYPES, short_code

_FONT = "font-family='PingFang SC,Microsoft YaHei,Noto Sans CJK SC,sans-serif'"
_INK = "#1b2430"
_MUTED = "#5c6b7a"
_BLUE_FILL, _BLUE_STROKE = "#eaf2fc", "#4b83c4"
_ORANGE_FILL, _ORANGE_STROKE = "#ffe6c2", "#e2681a"
_CONTAINER_FILL, _CONTAINER_STROKE = "#f3f7fb", "#9db9d4"
_GREEN, _RED, _YELLOW = "#2e7d32", "#c62828", "#ef6c00"
_BOX_H, _BOX_H_SUB, _GAP = 30, 46, 8
_COL_X = (30, 390, 750, 1110)
_COL_W = (330, 330, 330, 340)
_HEADERS = ("组件（文件）", "模块（目录）", "能力（中文名）", "系统 · 数据流")


def _esc(value: object) -> str:
    return escape(str(value if value is not None else ""), {'"': "&quot;", "'": "&apos;"})


def _short(value: object, limit: int) -> str:
    text = str(value if value is not None else "")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _wrap(width: int, height: int, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" {_FONT}>\n'
        '<defs><marker id="bp-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#5c6b7a"/></marker></defs>\n'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>\n'
        + "\n".join(body) + "\n</svg>\n"
    )


def _box(x: int, y: int, w: int, label: object, sub: object = "", *,
         highlighted: bool = False, fill: str | None = None,
         stroke: str | None = None, title: object | None = None) -> tuple[str, int]:
    """画一个节点框，返回 (svg 片段, 框高)。"""
    h = _BOX_H_SUB if sub else _BOX_H
    fill = fill or (_ORANGE_FILL if highlighted else _BLUE_FILL)
    stroke = stroke or (_ORANGE_STROKE if highlighted else _BLUE_STROKE)
    sw = 2.5 if highlighted else 1
    full = str(label if label is not None else "")
    tip = str(title if title is not None else full)
    parts = [
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}"/>',
        f'  <text x="{x + 10}" y="{y + 20}" font-size="14" font-weight="600" fill="{_INK}">'
        f'{_esc(_short(full, 34))}<title>{_esc(tip)}</title></text>',
    ]
    if sub:
        parts.append(
            f'  <text x="{x + 10}" y="{y + 37}" font-size="11" fill="{_MUTED}">'
            f'{_esc(_short(sub, 46))}</text>')
    if highlighted:
        parts.append(
            f'  <text x="{x + w - 10}" y="{y + 14}" font-size="10" text-anchor="end" '
            f'fill="{_ORANGE_STROKE}" font-weight="700">受影响</text>')
    return "\n".join(parts), h


def _parents_of(graph: dict) -> dict[str, str]:
    nodes = {n["id"]: n for n in graph.get("nodes", []) if isinstance(n, dict)}
    out: dict[str, str] = {}
    for e in graph.get("edges", []):
        if isinstance(e, dict) and e.get("kind") == "contains" and e.get("from") in nodes:
            child, parent = str(e.get("to")), str(e.get("from"))
            if child not in out or nodes[parent]["type"] == "module":
                out[child] = parent
    return out


def _children_of(graph: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for e in graph.get("edges", []):
        if isinstance(e, dict) and e.get("kind") == "contains":
            out.setdefault(str(e.get("from")), []).append(str(e.get("to")))
    for values in out.values():
        values.sort()
    return out


def _legend(y: int, extra: list[tuple[str, str]] | None = None) -> list[str]:
    swatches = [
        (_BLUE_FILL, _BLUE_STROKE, "普通节点（文件名 / 中文能力名）"),
        (_ORANGE_FILL, _ORANGE_STROKE, "受影响的上层节点（橙色）"),
        (_CONTAINER_FILL, _CONTAINER_STROKE, "容器框＝模块包含组件"),
    ]
    for color, label in (extra or []):
        swatches.append((color, color, label))
    parts = ['  <line x1="30" y1="%d" x2="1450" y2="%d" stroke="#dde4ec"/>' % (y - 10, y - 10)]
    x = 30
    for fill, stroke, text in swatches:
        parts.append(f'  <rect x="{x}" y="{y}" width="16" height="16" rx="3" fill="{fill}" '
                     f'stroke="{stroke}"/>')
        parts.append(f'  <text x="{x + 22}" y="{y + 13}" font-size="12" fill="{_MUTED}">'
                     f'{_esc(text)}</text>')
        x += 40 + len(text) * 12
    parts.append('  <text x="30" y="%d" font-size="12" fill="%s">'
                 '箭头 ＝ 数据流方向（左边依赖右边）；图上不直接展示能力码原文。'
                 '</text>' % (y + 34, _MUTED))
    return parts


def render_svg(graph: dict, highlight: list[str] | None = None) -> str:
    """把蓝图渲染为可被浏览器直接打开的单文件 SVG 字符串。"""
    nodes = {n["id"]: n for n in graph.get("nodes", [])
             if isinstance(n, dict) and isinstance(n.get("id"), str)}
    edges = [e for e in graph.get("edges", []) if isinstance(e, dict)]
    parents = _parents_of(graph)
    children = _children_of(graph)

    def label(node_id: str) -> str:
        return str(nodes.get(node_id, {}).get("label") or node_id)

    hl_ids = {str(x) for x in (highlight or [])}
    for nid, node in nodes.items():
        if node.get("label") in hl_ids:
            hl_ids.add(nid)

    by_type: dict[str, list[str]] = {t: [] for t in NODE_TYPES}
    for nid, node in nodes.items():
        by_type.setdefault(str(node.get("type")), []).append(nid)
    for values in by_type.values():
        values.sort()
    components, modules = by_type["component"], by_type["module"]
    caps, systems = by_type["capability"], by_type["system"]
    system_id = systems[0] if systems else "system:root"
    system_label = f"系统：{label(system_id)}" if systems else "系统：未命名"
    depends = sorted((e for e in edges if e.get("kind") == "depends"),
                     key=lambda e: (str(e.get("from")), str(e.get("to"))))

    body: list[str] = [
        '  <rect x="0" y="0" width="1480" height="60" fill="#123a5e"/>',
        f'  <text x="30" y="28" font-size="19" font-weight="700" fill="#fff">'
        f'{_esc(_short(system_label, 60))}</text>',
        f'  <text x="30" y="49" font-size="12" fill="#bcd6ef">'
        f'架构图纸 blueprint-graph/1 · 共 {len(components)} 组件 / '
        f'{len(modules)} 模块 / {len(caps)} 能力 / {len(depends)} 条数据流'
        f'（点击框悬停可见完整名称）</text>',
    ]
    for i, title in enumerate(_HEADERS):
        body.append(
            f'  <rect x="{_COL_X[i]}" y="72" width="{_COL_W[i]}" height="30" rx="5" fill="#dce8f5"/>'
            f'  <text x="{_COL_X[i] + 10}" y="92" font-size="13" font-weight="700" '
            f'fill="#123a5e">{_esc(title)}</text>')

    ys = [122, 122, 122, 122]

    # 栏 1：组件，按所属模块分组，用容器框表达 contains
    groups: dict[str, list[str]] = {}
    for cid in components:
        groups.setdefault(parents.get(cid, system_id), []).append(cid)
    for parent in sorted(groups):
        cids = sorted(groups[parent])
        y = ys[0]
        group_h = 26 + len(cids) * (_BOX_H + _GAP) + 4
        body.append(
            f'  <rect x="{_COL_X[0]}" y="{y}" width="{_COL_W[0]}" height="{group_h}" rx="8" '
            f'fill="{_CONTAINER_FILL}" stroke="{_CONTAINER_STROKE}" stroke-width="1" '
            f'stroke-dasharray="5 3"/>')
        body.append(
            f'  <text x="{_COL_X[0] + 10}" y="{y + 18}" font-size="12" font-weight="600" '
            f'fill="#3c5b78">{_esc(_short(label(parent), 30))} · {len(cids)} 个文件</text>')
        y += 24
        for cid in cids:
            frag, h = _box(_COL_X[0] + 12, y, _COL_W[0] - 24, label(cid), "",
                           highlighted=cid in hl_ids, title=nodes[cid].get("path") or cid)
            body.append(frag)
            y += h + _GAP
        ys[0] = y + 6

    # 栏 2：模块，副标题说明上级和包含的组件数
    for mid in modules:
        comp_count = sum(1 for c in children.get(mid, []) if c in set(components))
        parent = parents.get(mid)
        sub = f"上级：{label(parent) if parent else '—'} · 含 {comp_count} 组件"
        frag, h = _box(_COL_X[1], ys[1], _COL_W[1], label(mid), sub,
                       highlighted=mid in hl_ids, title=mid)
        body.append(frag)
        ys[1] += h + _GAP

    # 栏 3：能力，中文名为主标签，短码与实现组件为副标题
    for capid in caps:
        impls = [c for c in children.get(capid, []) if c in set(components)]
        meta = nodes[capid].get("meta") or {}
        sub = f"码：{short_code(meta.get('code', ''))} · 实现：{'、'.join(label(c) for c in impls[:3])}"
        frag, h = _box(_COL_X[2], ys[2], _COL_W[2], label(capid), sub,
                       highlighted=capid in hl_ids, title=nodes[capid].get("label") or capid)
        body.append(frag)
        ys[2] += h + _GAP

    # 栏 4：系统顶层 + 数据流箭头逐条列出
    frag, h = _box(_COL_X[3], ys[3], _COL_W[3], system_label,
                   f"含 {len(modules)} 模块 · {len(caps)} 能力 · {len(components)} 组件",
                   highlighted=system_id in hl_ids, title=system_label)
    body.append(frag)
    ys[3] += h + 14
    body.append(f'  <text x="{_COL_X[3]}" y="{ys[3]}" font-size="13" font-weight="700" '
                f'fill="#123a5e">数据流（依赖方向）</text>')
    ys[3] += 10
    if not depends:
        body.append(f'  <text x="{_COL_X[3]}" y="{ys[3] + 20}" font-size="12" '
                    f'fill="{_MUTED}">（未检出数据流）</text>')
        ys[3] += 30
    for e in depends:
        src, dst = str(e.get("from")), str(e.get("to"))
        active = src in hl_ids or dst in hl_ids
        row_y = ys[3]
        if active:
            body.append(f'  <rect x="{_COL_X[3]}" y="{row_y - 4}" width="{_COL_W[3]}" '
                        f'height="34" rx="4" fill="{_ORANGE_FILL}" opacity="0.55"/>')
        bx = _COL_X[3] + 4
        body.append(f'  <rect x="{bx}" y="{row_y}" width="140" height="26" rx="4" '
                    f'fill="#ffffff" stroke="#b9c9d9"/>'
                    f'  <text x="{bx + 6}" y="{row_y + 17}" font-size="11" fill="{_INK}">'
                    f'{_esc(_short(label(src), 18))}<title>{_esc(label(src))}</title></text>')
        body.append(f'  <line x1="{bx + 144}" y1="{row_y + 13}" x2="{bx + 178}" '
                    f'y2="{row_y + 13}" stroke="#5c6b7a" stroke-width="1.5" '
                    f'marker-end="url(#bp-arrow)"/>')
        body.append(f'  <rect x="{bx + 184}" y="{row_y}" width="140" height="26" rx="4" '
                    f'fill="#ffffff" stroke="#b9c9d9"/>'
                    f'  <text x="{bx + 190}" y="{row_y + 17}" font-size="11" fill="{_INK}">'
                    f'{_esc(_short(label(dst), 18))}<title>{_esc(label(dst))}</title></text>')
        ys[3] += 32

    content_bottom = max(ys)
    legend_y = content_bottom + 26
    body.extend(_legend(legend_y))
    height = legend_y + 60
    return _wrap(1480, height, body)


def _edge_text(graph: dict, edge: dict) -> str:
    nodes = {n["id"]: n for n in graph.get("nodes", []) if isinstance(n, dict)}
    def lab(key: str) -> str:
        nid = str(edge.get(key) or "")
        return str(nodes.get(nid, {}).get("label") or nid)
    return f"{lab('from')} → {lab('to')}（{edge.get('kind')}）"


def render_diff(before: dict, after: dict) -> str:
    """现状图 vs 规划图：绿色新增 / 红色删除 / 黄色修改，单文件 SVG。"""
    bn = {n["id"]: n for n in before.get("nodes", []) if isinstance(n, dict) and n.get("id")}
    an = {n["id"]: n for n in after.get("nodes", []) if isinstance(n, dict) and n.get("id")}
    added_n = sorted(set(an) - set(bn))
    removed_n = sorted(set(bn) - set(an))
    modified_n = sorted(
        nid for nid in set(bn) & set(an)
        if any(bn[nid].get(k) != an[nid].get(k) for k in ("type", "label", "path", "meta")))

    def edge_map(g: dict) -> dict[tuple[str, str, str], dict]:
        out: dict[tuple[str, str, str], dict] = {}
        for e in g.get("edges", []):
            if isinstance(e, dict):
                out[(str(e.get("from")), str(e.get("to")), str(e.get("kind")))] = e
        return out

    be, ae = edge_map(before), edge_map(after)
    added_e = sorted(set(ae) - set(be))
    removed_e = sorted(set(be) - set(ae))

    def node_line(nid: str, g: dict, n: dict) -> str:
        t = str(n.get("type") or "?")
        return f"[{t}] {n.get('label') or nid}"

    columns = [
        ("新增（规划图有、现状图无）", _GREEN, "#e8f5e9",
         [node_line(nid, after, an[nid]) for nid in added_n]
         + [_edge_text(after, ae[k]) for k in added_e]),
        ("删除（现状图有、规划图无）", _RED, "#ffebee",
         [node_line(nid, before, bn[nid]) for nid in removed_n]
         + [_edge_text(before, be[k]) for k in removed_e]),
        ("修改（同名节点属性变化）", _YELLOW, "#fff8e1",
         [f"{node_line(nid, after, an[nid])} → {node_line(nid, before, bn[nid])}"
          for nid in modified_n]),
    ]

    body = [
        '  <rect x="0" y="0" width="1480" height="60" fill="#123a5e"/>',
        '  <text x="30" y="28" font-size="19" font-weight="700" fill="#fff">现状图 vs 规划图</text>',
        f'  <text x="30" y="49" font-size="12" fill="#bcd6ef">'
        f'新增 {len(added_n) + len(added_e)} · 删除 {len(removed_n) + len(removed_e)} · '
        f'修改 {len(modified_n)}（规划图＝现状图 + 人确认修正文件）</text>',
    ]
    xs = (30, 510, 990)
    heights = [122, 122, 122]
    for i, (title, color, tint, rows) in enumerate(columns):
        x = xs[i]
        row_h = 30
        panel_h = 40 + (max(len(rows), 1) * (row_h + 6)) + 16
        body.append(f'  <rect x="{x}" y="72" width="460" height="{panel_h}" rx="8" '
                    f'fill="{tint}" stroke="{color}"/>')
        body.append(f'  <text x="{x + 12}" y="96" font-size="14" font-weight="700" '
                    f'fill="{color}">{_esc(title)}</text>')
        y = 112
        if not rows:
            body.append(f'  <text x="{x + 12}" y="{y + 6}" font-size="12" '
                        f'fill="{_MUTED}">（无）</text>')
        for row in rows:
            body.append(f'  <rect x="{x + 12}" y="{y}" width="436" height="{row_h}" rx="4" '
                        f'fill="#ffffff" opacity="0.9"/>'
                        f'  <text x="{x + 20}" y="{y + 20}" font-size="12" fill="{_INK}">'
                        f'{_esc(_short(row, 52))}<title>{_esc(row)}</title></text>')
            y += row_h + 6
        heights[i] = 72 + panel_h
    bottom = max(heights)
    body.extend(_legend(bottom + 26, [
        (_GREEN, "新增"), (_RED, "删除"), (_YELLOW, "修改"),
    ]))
    return _wrap(1480, bottom + 90, body)


# --------------------------------------------------------------------------- #
# 视角一：地图式（单文件 HTML，原生 JS 钻取，零第三方依赖）
# --------------------------------------------------------------------------- #
_MAP_CSS = """
*{box-sizing:border-box}
body{margin:0;padding:18px 22px 32px;font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;color:#1b2430;background:#f7fafd}
.hero{background:#123a5e;color:#fff;border-radius:10px;padding:14px 18px}
.hero h1{margin:0 0 4px;font-size:21px}
.hero .sub{margin:0;font-size:12px;color:#bcd6ef}
.bar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:12px 0}
.legend{display:flex;gap:14px;align-items:center;flex-wrap:wrap;font-size:12px;color:#5c6b7a}
.sw{display:inline-block;width:13px;height:13px;border-radius:3px;vertical-align:-2px;margin-right:4px}
button{font:inherit;font-size:12px;padding:5px 12px;border:1px solid #4b83c4;background:#fff;color:#123a5e;border-radius:6px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:10px}
.card{background:#fff;border:1px solid #d7e3ef;border-left:4px solid #4b83c4;border-radius:8px;padding:9px 11px;box-shadow:0 1px 2px rgba(20,50,80,.05)}
.card.focus-module{border:2px solid #e2681a;background:#fff7ed;box-shadow:0 0 0 3px #ffe6c2}
.card-head{cursor:pointer;user-select:none;font-weight:700;font-size:14px}
.caret{color:#4b83c4;font-size:12px;margin-right:5px}
.meta{font-size:11px;color:#5c6b7a;margin:4px 0 0 17px}
.badge-focus{margin-left:6px;font-size:10px;color:#fff;background:#e2681a;border-radius:8px;padding:1px 6px}
.components{margin:7px 0 0 2px;padding:6px 0 0 10px;border-top:1px dashed #d7e3ef}
.comp{font-size:12px;line-height:19px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.comp.focus-node{color:#e2681a;font-weight:700}
.cap{display:inline-block;font-size:10px;color:#2e7d32;background:#e8f5e9;border-radius:7px;padding:0 5px;margin-left:4px}
.empty{color:#5c6b7a;font-size:13px;padding:24px}
.foot{margin-top:14px;font-size:11px;color:#5c6b7a}
"""

_MAP_JS = """
function toggle(i){
  var el=document.getElementById('cmp-'+i), c=document.getElementById('caret-'+i);
  if(!el){return;}
  var open=(el.style.display!=='none');
  el.style.display=open?'none':'block';
  if(c){c.textContent=open?'+':'\u2212';}
}
function toggleAll(){
  var cards=document.querySelectorAll('.card'), anyClosed=false;
  for(var i=0;i<cards.length;i++){
    var el=cards[i].querySelector('.components');
    if(el && el.style.display==='none'){anyClosed=true;break;}
  }
  for(var j=0;j<cards.length;j++){
    var box=cards[j].querySelector('.components');
    if(!box){continue;}
    box.style.display=anyClosed?'block':'none';
    var c=cards[j].querySelector('.caret');
    if(c){c.textContent=anyClosed?'\u2212':'+';}
  }
}
"""


def render_map(graph: dict, focus: str | None = None) -> str:
    """地图式视角：系统 + 模块一屏纵览，点击模块钻取其组件。

    产出单文件 HTML（内嵌 CSS / 原生 JS / 无外部依赖）：
    - 顶层只有「系统横幅 + 模块卡片」，模块数通常 <= 25，一屏可看完；
    - 每张模块卡片显示中文名 + 组件数 + 能力数，点击标题展开组件清单；
    - 组件的绿色小签显示其所属能力的中文名（不暴露能力码原文）；
    - focus 给定节点 id 时，其所在模块与节点本身用橙色高亮并默认展开。
    """
    nodes = {n["id"]: n for n in graph.get("nodes", [])
             if isinstance(n, dict) and isinstance(n.get("id"), str)}
    children = _children_of(graph)
    parents = _parents_of(graph)

    def label(nid: object) -> str:
        return str(nodes.get(str(nid), {}).get("label") or nid)

    by_type: dict[str, list[str]] = {t: [] for t in NODE_TYPES}
    for nid, node in nodes.items():
        by_type.setdefault(str(node.get("type")), []).append(nid)
    for values in by_type.values():
        values.sort()
    systems, modules = by_type["system"], by_type["module"]
    components, caps = set(by_type["component"]), by_type["capability"]
    system_id = systems[0] if systems else "system:root"
    system_label = label(system_id) if systems else "未命名系统"

    # 组件 -> 所属能力中文名（contains: capability -> component）
    comp_caps: dict[str, list[str]] = {c: [] for c in components}
    for cap in caps:
        for impl in children.get(cap, []):
            if impl in components:
                comp_caps[impl].append(label(cap))
    for value in comp_caps.values():
        value.sort()

    # 模块 -> 组件（contains: module -> component）
    mod_comps: dict[str, list[str]] = {}
    for cid in sorted(components):
        mid = parents.get(cid)
        if mid in modules:
            mod_comps.setdefault(mid, []).append(cid)
    mod_caps: dict[str, set[str]] = {
        mid: {cap for cid in comps for cap in comp_caps.get(cid, [])}
        for mid, comps in mod_comps.items()
    }

    # focus 高亮定位：component 取父模块，module 自身，capability 取其实现组件的模块
    focus_id = str(focus) if focus else ""
    focus_modules: set[str] = set()
    focus_components: set[str] = set()
    if focus_id:
        if focus_id in modules:
            focus_modules.add(focus_id)
        elif focus_id in components:
            focus_components.add(focus_id)
            if parents.get(focus_id) in modules:
                focus_modules.add(parents[focus_id])
        elif focus_id in caps:
            for impl in children.get(focus_id, []):
                if impl in components:
                    focus_components.add(impl)
                    if parents.get(impl) in modules:
                        focus_modules.add(parents[impl])
        elif focus_id in systems or focus_id == system_id:
            focus_modules.update(modules)

    parts = [
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">',
        f'<title>架构地图 · {_esc(system_label)}</title>',
        f'<style>{_MAP_CSS}</style>',
        '</head>\n<body>',
        '<header class="hero">',
        f'<h1>架构地图 · {_esc(system_label)}</h1>',
        f'<p class="sub">blueprint-graph/1 · 顶层 {len(systems) + len(modules)} 个节点'
        f'（{len(systems)} 系统 + {len(modules)} 模块）· {len(components)} 个组件 / '
        f'{len(caps)} 个能力 / {len(nodes)} 个节点 · 点击模块卡片展开组件</p>',
        '</header>',
        '<div class="bar">',
        '<div class="legend">',
        '<span><i class="sw" style="background:#123a5e"></i>系统</span>',
        '<span><i class="sw" style="background:#fff;border:1px solid #4b83c4"></i>模块</span>',
        '<span><i class="sw" style="background:#fff7ed;border:2px solid #e2681a"></i>聚焦高亮</span>',
        '<span><i class="sw" style="background:#e8f5e9"></i>能力（中文名）</span>',
        '</div>',
        '<button type="button" onclick="toggleAll()">全部展开 / 收起</button>',
        '</div>',
        '<main class="grid">',
    ]
    if not modules:
        parts.append('<p class="empty">图中暂无模块节点。</p>')
    for index, mid in enumerate(modules):
        comps = mod_comps.get(mid, [])
        highlighted = mid in focus_modules
        cls = "card focus-module" if highlighted else "card"
        badge = '<span class="badge-focus">聚焦</span>' if highlighted else ""
        opened = highlighted
        parts.extend([
            f'<div class="{cls}" id="mod-{index}">',
            f'<div class="card-head" onclick="toggle({index})" title="点击展开 / 收起组件">'
            f'<span class="caret" id="caret-{index}">{"−" if opened else "+"}</span>'
            f'{_esc(label(mid))}{badge}</div>',
            f'<div class="meta">{len(comps)} 个组件 · {len(mod_caps.get(mid, set()))} 个能力</div>',
            f'<div class="components" id="cmp-{index}" '
            f'style="display:{"block" if opened else "none"}">',
        ])
        if not comps:
            parts.append('<div class="comp">（无组件）</div>')
        for cid in comps:
            comp_cls = "comp focus-node" if cid in focus_components else "comp"
            tags = "".join(f'<span class="cap">{_esc(cap)}</span>'
                           for cap in comp_caps.get(cid, []))
            parts.append(f'<div class="{comp_cls}" title="{_esc(cid)}">'
                         f'{_esc(label(cid))}{tags}</div>')
        parts.extend(["</div>", "</div>"])
    parts.extend([
        '</main>',
        '<p class="foot">读法：一张卡片＝一个模块；点击标题展开它包含的组件，'
        '组件后的绿色小签是中文能力名。橙色＝本次聚焦的模块 / 节点。</p>',
        f'<script>{_MAP_JS}</script>',
        '</body>\n</html>\n',
    ])
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# 视角二：聚焦式（同心环 SVG，红=被依赖 / 蓝=包含，零第三方依赖）
# --------------------------------------------------------------------------- #
def render_focus(impact: dict, graph: dict) -> str:
    """聚焦式视角：以被改节点为中心的同心环，回答「改它会波及谁」。

    直接消费 impact_up() 的 by_level / via，不重算影响传导：
    - 中心紫圆＝被改节点；由内向外：组件 → 能力 → 模块 → 系统；
    - 红色＝被依赖（反向依赖），蓝色＝包含（上卷），连线同色；
    - 顶部摘要「改这里会影响 N 个组件、M 个模块」；面向不懂技术的人。
    """
    nodes = {n["id"]: n for n in graph.get("nodes", [])
             if isinstance(n, dict) and isinstance(n.get("id"), str)}

    def label(nid: object) -> str:
        return str(nodes.get(str(nid), {}).get("label") or nid)

    seeds = [str(x) for x in (impact.get("seeds") or [])]
    by_level = impact.get("by_level") or {}
    comp_count = len(by_level.get("component") or [])
    mod_count = len(by_level.get("module") or [])

    depend_color, contain_color, seed_color = "#c62828", "#1f6fb2", "#6a1b9a"
    width, height = 1200, 1160
    cx, cy = width // 2, height // 2
    rings = (
        ("component", 165, "组件 · 直接波及"),
        ("capability", 275, "能力 · 受影响能力"),
        ("module", 385, "模块 · 上卷"),
        ("system", 495, "系统 · 顶层"),
    )

    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" {_FONT}>',
        '<defs><marker id="bp-focus-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{_MUTED}"/></marker></defs>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<rect x="0" y="0" width="{width}" height="62" fill="#123a5e"/>',
        f'<text x="28" y="27" font-size="19" font-weight="700" fill="#fff">'
        f'聚焦图纸 · 改这里会波及谁</text>',
        f'<text x="28" y="49" font-size="12" fill="#bcd6ef">'
        f'改这里会影响 {comp_count} 个组件、{mod_count} 个模块'
        f'（红＝被依赖，蓝＝包含；由内向外逐层上卷）</text>',
    ]
    for _, radius, ring_label in rings:
        body.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
                    f'stroke="#dde4ec" stroke-dasharray="5 7"/>')
        body.append(f'<text x="{cx}" y="{cy - radius + 4}" font-size="11" '
                    f'text-anchor="middle" fill="#9db9d4">{_esc(ring_label)}</text>')

    placed: list[tuple[float, float, float, str, list[str], str, str]] = []
    for level, radius, _ in rings:
        entries = by_level.get(level) or []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            angle = -math.pi / 2 + (2 * math.pi * index / len(entries) if entries else 0)
            x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
            via = [str(k) for k in (entry.get("via") or [])]
            color = depend_color if "depends" in via else contain_color
            nid = str(entry.get("id") or "")
            text = str(entry.get("label") or label(nid))
            placed.append((x, y, angle, color, via, text, nid))
            body.append(
                f'<line x1="{cx + 56 * math.cos(angle):.1f}" y1="{cy + 56 * math.sin(angle):.1f}" '
                f'x2="{x - 7 * math.cos(angle):.1f}" y2="{y - 7 * math.sin(angle):.1f}" '
                f'stroke="{color}" stroke-width="1.6" opacity="0.8" '
                f'marker-end="url(#bp-focus-arrow)"/>')

    seed_text = "、".join(_short(label(s), 16) for s in seeds[:2]) if seeds else "未指定"
    body.extend([
        f'<circle cx="{cx}" cy="{cy}" r="56" fill="{seed_color}" '
        f'stroke="#4a148c" stroke-width="3"/>',
        f'<text x="{cx}" y="{cy - 8}" font-size="12" text-anchor="middle" '
        f'fill="#eadcf5">被改的节点</text>',
        f'<text x="{cx}" y="{cy + 12}" font-size="13" font-weight="700" '
        f'text-anchor="middle" fill="#ffffff">{_esc(_short(seed_text, 20))}'
        f'<title>{_esc("、".join(seeds))}</title></text>',
    ])

    for x, y, angle, color, via, text, _ in placed:
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" '
                    f'stroke="#ffffff" stroke-width="1.5"/>')
        on_right = math.cos(angle) >= 0
        tx = x + 11 if on_right else x - 11
        anchor = "start" if on_right else "end"
        spans = [f'<tspan fill="{_INK}">{_esc(_short(text, 22))}'
                 f'<title>{_esc(text)}</title></tspan>']
        if "depends" in via:
            spans.append(f'<tspan fill="{depend_color}" font-weight="700"> [被依赖]</tspan>')
        if "contains" in via:
            spans.append(f'<tspan fill="{contain_color}" font-weight="700"> [包含]</tspan>')
        body.append(f'<text x="{tx:.1f}" y="{y + 4:.1f}" font-size="12" '
                    f'text-anchor="{anchor}">' + "".join(spans) + '</text>')

    legend_y = height - 56
    body.extend([
        f'<line x1="30" y1="{legend_y - 14}" x2="{width - 30}" y2="{legend_y - 14}" '
        f'stroke="#dde4ec"/>',
        f'<circle cx="40" cy="{legend_y + 2}" r="7" fill="{seed_color}"/>',
        f'<text x="54" y="{legend_y + 6}" font-size="12" fill="{_MUTED}">'
        f'紫＝被改的中心节点</text>',
        f'<circle cx="265" cy="{legend_y + 2}" r="7" fill="{depend_color}"/>',
        f'<text x="279" y="{legend_y + 6}" font-size="12" fill="{_MUTED}">'
        f'红＝被依赖（改它，依赖方跟着变）</text>',
        f'<circle cx="600" cy="{legend_y + 2}" r="7" fill="{contain_color}"/>',
        f'<text x="614" y="{legend_y + 6}" font-size="12" fill="{_MUTED}">'
        f'蓝＝包含（影响上卷到模块 / 能力 / 系统）</text>',
        f'<text x="30" y="{legend_y + 26}" font-size="11" fill="{_MUTED}">'
        f'连线颜色＝传导类型；由内向外：组件 → 能力 → 模块 → 系统。</text>',
    ])
    body.append('</svg>\n')
    return "\n".join(body)
