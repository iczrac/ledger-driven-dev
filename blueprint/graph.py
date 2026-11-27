"""架构图纸引擎：组合关系图的数据结构、自动推导、人确认修正与影响传导。

纯标准库、只读、确定性。同一份输入（源码 + registry + 修正文件）恒产出同一张图，
不写任何文件、不产生时间戳、不泄露绝对路径（图内一律相对 root 的 posix 路径）。

数据结构 ``blueprint-graph/1``
------------------------------
graph = {
    "schema": "blueprint-graph/1",
    "root": ".",                      # 恒定 ".": 路径全部相对 root，无绝对路径
    "nodes": [                        # 按 id 排序
        {
            "id": "component:scripts/foo.py",   # 全局唯一
            "type": "component|module|capability|system",
            "label": "foo.py",        # 面向人的标签（文件名 / 中文能力名 / 项目名）
            "path": "scripts/foo.py", # 相对路径；capability/system 为 None
            "meta": {},               # 附加信息（能力码 / domain / 目录等）
        }, ...
    ],
    "edges": [                        # 按 (from, to, kind) 排序
        {"from": "<node id>", "to": "<node id>", "kind": "contains|depends"}, ...
    ],
}

``contains`` 的 from=父、to=子（system -> module/capability, module -> component,
capability -> component 的 realization 也用 contains 表达）。``depends`` 的 from=依赖方、
to=被依赖方。两者都要求是 DAG；``check_graph`` 会检测环。
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "blueprint-graph/1"
IMPACT_SCHEMA = "blueprint-impact/1"
NODE_TYPES = ("component", "module", "capability", "system")
EDGE_KINDS = ("contains", "depends")

# 与 governance/registry_codec.py 的 CODE_RE 模式逐字一致（该模块无 __init__.py，
# 且本引擎必须独立运行、不触发治理链，故复制判据而非 import）。
CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")

# 推导时跳过的目录：隐藏目录、缓存与虚拟环境，避免把副本/临时物当成组件。
_SKIP_DIRS = {"__pycache__", ".git", ".hg", ".svn", ".venv", "venv", "node_modules"}
_SYSTEM_ID = "system:root"


# --------------------------------------------------------------------------- #
# 能力码小工具（命名沿用派工单；registry_codec.py 实际只提供 CODE_RE / cap_code）
# --------------------------------------------------------------------------- #
def valid_code(code: object) -> bool:
    """能力码是否合法（SEG.SEG.SEG.NN）。"""
    return isinstance(code, str) and bool(CODE_RE.fullmatch(code))


def short_code(code: str) -> str:
    """给人看的短码：保留后两段，如 METHOD.GOV.FEEDBACK.01 -> FEEDBACK.01。"""
    parts = str(code or "").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else str(code or "")


# --------------------------------------------------------------------------- #
# 内部辅助
# --------------------------------------------------------------------------- #
def _rel(path: Path, root: Path) -> str:
    """相对 root 的 posix 路径；绝不返回绝对路径。"""
    return path.relative_to(root).as_posix()


def _node(node_id: str, kind: str, label: str, path: str | None = None,
          meta: dict | None = None) -> dict:
    return {"id": node_id, "type": kind, "label": str(label),
            "path": path, "meta": dict(meta or {})}


def _add_edge(edges: list[dict], frm: str, to: str, kind: str) -> None:
    edge = {"from": frm, "to": to, "kind": kind}
    if edge not in edges:
        edges.append(edge)


def _skipped(path: Path, root: Path) -> bool:
    return any(part in _SKIP_DIRS or part.startswith(".") for part in path.relative_to(root).parts[:-1])


def _name_candidates(rel: str) -> list[str]:
    """一个源文件可被 import 引用的名字候选（含包 __init__ 与逐级后缀）。"""
    parts = rel.split("/")
    file = parts[-1]
    stem = file[:-3] if file.endswith(".py") else file
    if stem == "__init__":
        dotted = parts[:-1]
    else:
        dotted = parts[:-1] + [stem]
    out: list[str] = []
    for i in range(len(dotted)):
        name = ".".join(dotted[i:])
        if name:
            out.append(name)
    return out


def _build_name_index(files: list[Path], root: Path) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for p in files:
        cid = "component:" + _rel(p, root)
        for name in set(_name_candidates(_rel(p, root))):
            index.setdefault(name, []).append(cid)
    for cids in index.values():
        cids.sort()
    return index


def _resolve_import(name: str, level: int, importer_rel: str,
                    index: dict[str, list[str]]) -> str | None:
    """把一条 import 的名字解析到 root 内唯一组件；歧义/外部库返回 None。"""
    importer_dir = importer_rel.rsplit("/", 1)[0] if "/" in importer_rel else ""
    if level:
        parts = importer_dir.split("/") if importer_dir else []
        if level > 1:
            parts = parts[:len(parts) - (level - 1)] if len(parts) >= level - 1 else []
        candidate = ".".join(parts + ([name] if name else []))
        keys = [candidate] if candidate else []
    else:
        keys = [name] if name else []
    found: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for cid in index.get(key, []):
            if cid not in seen:
                seen.add(cid)
                found.append(cid)
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    # 多个同名文件时只认与引用方同目录的那个；仍不唯一则跳过（确定性、不猜）。
    same_dir = [c for c in found if c[len("component:"):].rsplit("/", 1)[0] == importer_dir]
    return same_dir[0] if len(same_dir) == 1 else None


def _derive_code(project_code: object, module_code: object, domain: object, index: int) -> str:
    m = str(module_code or "CORE").strip().upper()
    if "." in m:
        namespace = m                      # 模块码已含项目段，勿拼成五段
    else:
        namespace = f"{str(project_code or 'PROJ').strip().upper()}.{m}"
    return f"{namespace}.{str(domain or 'ITEM').strip().upper()}.{index:02d}"


def _normalize_impl(value: object) -> str:
    p = str(value or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _impl_target(impl: str, component_ids: set[str]) -> str | None:
    exact = "component:" + impl
    if exact in component_ids:
        return exact
    suffix = "/" + impl
    matches = sorted(cid for cid in component_ids if cid.endswith(suffix))
    return matches[0] if len(matches) == 1 else None


def _registry_caps(registry_path: Path) -> tuple[str, list[dict]]:
    """只读 registry，返回 (项目名, 展开后的 cap 列表)；兼容 v1/v2 形状。"""
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        return "", []
    projects = registry.get("projects")
    if isinstance(projects, list) and projects:
        project = projects[0] if isinstance(projects[0], dict) else {}
        modules = project.get("modules") or []
    else:
        project = registry.get("project") if isinstance(registry.get("project"), dict) else {}
        modules = registry.get("modules") or []
    caps: list[dict] = []
    for module in modules if isinstance(modules, list) else []:
        if not isinstance(module, dict):
            continue
        for index, cap in enumerate(module.get("caps") or [], 1):
            if isinstance(cap, dict):
                caps.append({
                    "code": cap.get("code") or _derive_code(
                        project.get("code"), module.get("code"), cap.get("domain"), index),
                    "name": cap.get("name") or "",
                    "domain": cap.get("domain") or "",
                    "module": module.get("name") or module.get("code") or "",
                    "impl": list(cap.get("impl") or []),
                })
    return str(project.get("name") or ""), caps


# --------------------------------------------------------------------------- #
# 1. 自动推导
# --------------------------------------------------------------------------- #
def build_from_source(root: Path, registry_path: Path | None = None,
                      extensions: tuple[str, ...] = (".py",)) -> dict:
    """从源码（+ 可选 registry）自动推导一张 ``blueprint-graph/1``。

    - 组件：root 下所有 ``extensions`` 文件（跳过隐藏目录与缓存）。
    - 模块：每个祖先目录一层；目录层级之间用 contains 串成树。
    - 依赖：ast 解析 import，只保留能唯一解析到 root 内组件的边；注释/字符串
      里的伪 import 不会被 ast 当成 Import 节点，天然不会误抽。
    - 能力：registry 的 caps[].impl 映射到组件（capability contains component）。
    - 系统：唯一顶层容器 system:root。
    """
    root = Path(root).resolve()
    nodes: dict[str, dict] = {_SYSTEM_ID: _node(_SYSTEM_ID, "system", "系统", None, {"root": "."})}
    edges: list[dict] = []

    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix in extensions and not _skipped(p, root)),
        key=lambda p: _rel(p, root),
    )
    component_ids: set[str] = set()
    for p in files:
        rel = _rel(p, root)
        cid = "component:" + rel
        component_ids.add(cid)
        nodes[cid] = _node(cid, "component", p.name, rel)

    # 模块层：文件父目录及其所有祖先目录
    module_dirs: set[Path] = set()
    for p in files:
        directory = p.parent
        while directory != root and root in directory.parents:
            module_dirs.add(directory)
            directory = directory.parent
    for directory in sorted(module_dirs, key=lambda d: _rel(d, root)):
        rel = _rel(directory, root)
        nodes["module:" + rel] = _node("module:" + rel, "module", directory.name, rel,
                                       {"dir": rel})

    # contains：上级模块/系统 -> 下级模块，模块/系统 -> 组件
    for directory in sorted(module_dirs, key=lambda d: _rel(d, root)):
        mid = "module:" + _rel(directory, root)
        parent_dir = directory.parent
        pid = _SYSTEM_ID if parent_dir == root else "module:" + _rel(parent_dir, root)
        _add_edge(edges, pid, mid, "contains")
    for p in files:
        cid = "component:" + _rel(p, root)
        parent_dir = p.parent
        pid = _SYSTEM_ID if parent_dir == root else "module:" + _rel(parent_dir, root)
        _add_edge(edges, pid, cid, "contains")

    # depends：ast import 解析
    name_index = _build_name_index(files, root)
    for p in files:
        rel = _rel(p, root)
        cid = "component:" + rel
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for stmt in ast.walk(tree):
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    target = _resolve_import(alias.name, 0, rel, name_index)
                    if target and target != cid:
                        _add_edge(edges, cid, target, "depends")
            elif isinstance(stmt, ast.ImportFrom):
                target = _resolve_import(stmt.module or "", stmt.level, rel, name_index)
                if target and target != cid:
                    _add_edge(edges, cid, target, "depends")

    # 能力层：registry caps[].impl -> component（realization 用 contains 表达）
    if registry_path is not None:
        project_name, caps = _registry_caps(Path(registry_path))
        if project_name:
            nodes[_SYSTEM_ID]["label"] = project_name
        for cap in caps:
            code = cap["code"]
            if not valid_code(code):
                continue
            capid = "capability:" + code
            nodes[capid] = _node(capid, "capability", cap["name"] or short_code(code), None,
                                 {"code": code, "domain": cap["domain"], "module": cap["module"]})
            _add_edge(edges, _SYSTEM_ID, capid, "contains")
            for impl in cap["impl"]:
                target = _impl_target(_normalize_impl(impl), component_ids)
                if target:
                    _add_edge(edges, capid, target, "contains")

    return {
        "schema": SCHEMA,
        "root": ".",
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": sorted(edges, key=lambda e: (e["from"], e["to"], e["kind"])),
    }


# --------------------------------------------------------------------------- #
# 2. 人确认修正（唯一需人维护的事实源；叠加在自动推导之上且修正优先）
# --------------------------------------------------------------------------- #
def apply_overrides(graph: dict, overrides_path: Path) -> dict:
    """把人写的 add_node / add_edge / remove_edge 叠加到自动推导图上。

    修正优先的三条保证：
    1. add_node 与自动节点同 id 时，以修正节点整条记录替换；
    2. add_edge 与自动边同 (from,to,kind) 时只保留修正版本（幂等，不产生双份）；
    3. remove_edge 最后执行，能删掉自动边，也能删掉本次 add_edge 新增的边。

    赞成/反对之外的未知 op 被忽略；接受 ``{"ops":[...]}``、``{"overrides":[...]}``
    或顶层数组三种写法。悬空边不会被静默丢弃——留给 ``check_graph`` 判红。
    """
    data = json.loads(Path(overrides_path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        ops = data.get("ops") or data.get("overrides") or []
    elif isinstance(data, list):
        ops = data
    else:
        ops = []
    if not isinstance(ops, list):
        ops = []

    nodes = {n["id"]: dict(n) for n in graph.get("nodes", [])
             if isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"]}
    touched_nodes: set[str] = set()
    override_edges: list[tuple[str, str, str]] = []
    override_edge_keys: set[tuple[str, str, str]] = set()
    removals: list[tuple[str, str, str | None]] = []

    for raw in ops:
        if not isinstance(raw, dict):
            continue
        op = raw.get("op") or raw.get("action")
        if op == "add_node":
            n = raw.get("node", raw)
            if isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"]:
                nid = n["id"]
                touched_nodes.add(nid)
                nodes[nid] = _node(nid, n.get("type", "component"),
                                   str(n.get("label") or nid), n.get("path"), n.get("meta"))
        elif op in ("add_edge", "remove_edge"):
            e = raw.get("edge", raw)
            if not isinstance(e, dict):
                continue
            frm, to = e.get("from"), e.get("to")
            if not frm or not to:
                continue
            if op == "add_edge":
                key = (str(frm), str(to), str(e.get("kind") or "contains"))
                if key not in override_edge_keys:
                    override_edge_keys.add(key)
                    override_edges.append(key)
            else:
                removals.append((str(frm), str(to),
                                 str(e["kind"]) if e.get("kind") else None))

    kept: dict[tuple[str, str, str], dict] = {}
    for e in graph.get("edges", []):
        if not isinstance(e, dict):
            continue
        key = (str(e.get("from")), str(e.get("to")), str(e.get("kind")))
        if key in override_edge_keys:        # 修正的 add_edge 覆盖自动边
            continue
        kept[key] = {"from": key[0], "to": key[1], "kind": key[2]}
    for key in override_edges:
        kept[key] = {"from": key[0], "to": key[1], "kind": key[2]}

    for frm, to, kind in removals:           # remove_edge 最后执行，修正说了算
        for key in list(kept):
            if key[0] == frm and key[1] == to and (kind is None or key[2] == kind):
                kept.pop(key, None)

    return {
        "schema": graph.get("schema", SCHEMA),
        "root": ".",
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": [kept[k] for k in sorted(kept)],
    }


# --------------------------------------------------------------------------- #
# 3. 向上 / 反向影响传导（blast radius）
# --------------------------------------------------------------------------- #
_RELATION_WORD = {"contains": "包含", "depends": "被依赖"}


def impact_up(graph: dict, node_ids: Iterable[str]) -> dict:
    """沿 contains 向上、沿 depends 反向遍历，回答「改了它会波及谁」。

    两种传导合并进同一个 by_level（按节点类型分组）：
    - contains 向上：当前节点 → 包含它的父节点（模块 / 能力 / 系统）；
    - depends 反向：当前节点 → 依赖它的节点（谁 depends 我，我改就影响谁）。

    两种传导可叠加：测试依赖了某脚本，脚本改动先波及测试文件，再沿 contains
    上卷到测试所在模块与系统，形成完整的 blast radius。

    每条路径给三份视图：
    - ``paths``：节点 id 序列（首项为 seed，兼容旧消费者）；
    - ``path_kinds``：每一步的边 kind（contains / depends）；
    - ``path_labels``：人读版，逐段标注「包含」或「被依赖」。
    另附 ``via``（该节点被哪几种传导触达）。用 per-path visited set 防环，
    既不无限递归，也不丢失同一节点的多条影响路径。
    """
    nodes = {n["id"]: n for n in graph.get("nodes", [])
             if isinstance(n, dict) and isinstance(n.get("id"), str)}
    parents: dict[str, set[str]] = {}       # contains: child -> parents
    dependents: dict[str, set[str]] = {}    # depends: dependency -> dependents（反向）
    for e in graph.get("edges", []):
        if not isinstance(e, dict) or not e.get("from") or not e.get("to"):
            continue
        frm, to = str(e["from"]), str(e["to"])
        if e.get("kind") == "contains":
            parents.setdefault(to, set()).add(frm)
        elif e.get("kind") == "depends":
            dependents.setdefault(to, set()).add(frm)   # 谁依赖我

    seeds = [str(x) for x in node_ids]
    found: dict[str, set[tuple[str, ...]]] = {}
    kinds_of: dict[tuple[str, ...], tuple[str, ...]] = {}

    def walk(current: str, path: tuple[str, ...], kinds: tuple[str, ...],
             visited: frozenset[str]) -> None:
        moves: list[tuple[str, str]] = []
        moves.extend((p, "contains") for p in parents.get(current, ()))
        moves.extend((d, "depends") for d in dependents.get(current, ()))
        for neighbor, kind in sorted(moves):        # 排序保证确定性
            if neighbor in visited:                 # per-path visited set：防环且保留多路径
                continue
            extended = path + (neighbor,)
            extended_kinds = kinds + (kind,)
            found.setdefault(neighbor, set()).add(extended)
            kinds_of[extended] = extended_kinds
            walk(neighbor, extended, extended_kinds, visited | {neighbor})

    for seed in seeds:
        walk(seed, (seed,), (), frozenset({seed}))

    def label_of(step: str) -> str:
        return str(nodes.get(step, {}).get("label") or step)

    def label_path(path: tuple[str, ...]) -> str:
        parts = [label_of(path[0])]
        for step, kind in zip(path[1:], kinds_of[path]):
            parts.append(f" →[{_RELATION_WORD.get(kind, kind)}] {label_of(step)}")
        return "".join(parts)

    grouped: dict[str, list[dict]] = {}
    for nid, paths in found.items():
        node = nodes.get(nid, {})
        ordered = sorted(paths)
        grouped.setdefault(str(node.get("type", "unknown")), []).append({
            "id": nid,
            "label": str(node.get("label") or nid),
            "type": str(node.get("type", "unknown")),
            "paths": [list(p) for p in ordered],
            "path_kinds": [list(kinds_of[p]) for p in ordered],
            "path_labels": [label_path(p) for p in ordered],
            "via": sorted({k for p in ordered for k in kinds_of[p]}),
        })
    return {
        "schema": IMPACT_SCHEMA,
        "seeds": seeds,
        "relation_legend": {
            "contains": "包含：影响沿「父包含子」关系上卷到模块 / 能力 / 系统",
            "depends": "被依赖：依赖方会因被依赖方改动而受影响（反向依赖）",
        },
        "by_level": {level: sorted(grouped[level], key=lambda e: e["id"])
                     for level in sorted(grouped)},
    }


# --------------------------------------------------------------------------- #
# 4. 合法性校验（CLI --check：id 唯一 / 边端点存在 / 无环）
# --------------------------------------------------------------------------- #
def check_graph(graph: object) -> list[str]:
    """返回错误列表；空列表表示合法。"""
    errs: list[str] = []
    if not isinstance(graph, dict):
        return ["graph 必须是对象"]
    if graph.get("schema") != SCHEMA:
        errs.append(f"schema 非法：{graph.get('schema')}（期望 {SCHEMA}）")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list):
        return errs + ["nodes 必须是数组"]
    if not isinstance(edges, list):
        return errs + ["edges 必须是数组"]

    ids: list[str] = []
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errs.append(f"nodes[{i}] 必须是对象")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not nid:
            errs.append(f"nodes[{i}].id 缺失或非法")
        else:
            ids.append(nid)
        if n.get("type") not in NODE_TYPES:
            errs.append(f"{nid}: type 非法：{n.get('type')}")
        if not isinstance(n.get("label"), str) or not n["label"]:
            errs.append(f"{nid}: label 缺失或非法")
    if len(ids) != len(set(ids)):
        errs.append("节点 id 不唯一")
    idset = set(ids)

    seen_edges: set[tuple[str, str, str]] = set()
    adjacency: dict[str, list[str]] = {nid: [] for nid in idset}
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errs.append(f"edges[{i}] 必须是对象")
            continue
        frm, to, kind = e.get("from"), e.get("to"), e.get("kind")
        if not isinstance(frm, str) or not frm or not isinstance(to, str) or not to:
            errs.append(f"edges[{i}] 的 from/to 非法")
            continue
        if kind not in EDGE_KINDS:
            errs.append(f"edges[{i}]: kind 非法：{kind}")
        if frm not in idset:
            errs.append(f"edges[{i}] 引用不存在的起点节点：{frm}")
        if to not in idset:
            errs.append(f"edges[{i}] 引用不存在的终点节点：{to}")
        key = (frm, to, str(kind))
        if key in seen_edges:
            errs.append(f"edges[{i}] 重复边：{frm} -[{kind}]-> {to}")
        seen_edges.add(key)
        adjacency.setdefault(frm, []).append(to)

    # 迭代式 DFS 三色环检测（不依赖递归深度）
    color: dict[str, int] = {}
    for start in sorted(adjacency):
        if color.get(start):
            continue
        color[start] = 1
        stack: list[tuple[str, Any]] = [(start, iter(adjacency[start]))]
        while stack:
            current, iterator = stack[-1]
            nxt = next(iterator, None)
            if nxt is None:
                color[current] = 2
                stack.pop()
            elif color.get(nxt) == 1:
                errs.append(f"检测到环：{nxt} → … → {current} → {nxt}")
            elif color.get(nxt) is None:
                color[nxt] = 1
                stack.append((nxt, iter(adjacency.get(nxt, []))))
    return errs
