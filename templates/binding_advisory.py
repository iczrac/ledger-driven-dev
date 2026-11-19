#!/usr/bin/env python3
"""符号级证据绑定 advisory（v2.1.2）：在「路径存在」之上再查「调用关系」。

「声明的测试存在且已入库」（v2.1.0）只证明路径，证明不了「测的就是这个
能力」。这里把判据再收紧一层：测试 import 的名字能否沿 ``__init__.py``
再导出链解析到定义文件，且该文件落在能力的 impl 集合里。判得出来 →
bound（直接）或 via1（经一跳编排层触达）；判不出来 → unbound，多半是
词面配对错挂了测试。

定位是 shadow 门禁：只打印 [UNBOUND] 告警、可产出报告，不改 tier、
不影响退出码。判据必须先在 CI 里晒出问题、被证明「判得对」，才有资格
当硬门禁。绑定是必要条件不是充分条件：有调用关系 ≠ 测的是该能力语义。

架构说明
--------
本模块是生成器（build_capability_model.py）的旁路观察件，独立成模块的
原因是生成器主体必须保持在模块大小硬限之下。``resolve_declared`` /
``glob_files`` 由生成器注入（依赖倒置），避免与生成器互相 import；
registry codec 按既有惯例做同目录 sibling import。

用法
----
    from binding_advisory import binding_advisory, print_binding_advisory
    adv = binding_advisory(repo_root, cfg_all, scope,
                           resolve_declared=resolve_declared,
                           glob_files=glob_files)
    print_binding_advisory(adv)

依赖：仅标准库 + registry_codec（同目录）。
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

# 与生成器同一惯例：脚本被复制到目标项目时，sys.path[0] 是脚本目录；
# 被测试以 spec 方式加载时，显式补同目录，避免第二套编码实现。
try:
    from registry_codec import cap_code as codec_cap_code
    from registry_codec import normalize_projects
except ModuleNotFoundError:  # pragma: no cover - 仅在 spec 加载路径触发
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from registry_codec import cap_code as codec_cap_code
    from registry_codec import normalize_projects


class SymbolIndex:
    """点分模块名 → 文件的多别名索引（按项目就近消歧）。

    测试写 ``from src.core import foo`` 时，``src.core`` 的真实位置取决于
    测试属于哪个项目（projects/<x>/src/core）。索引为每个点分名保留全部
    候选，查找时可按「与引用者同项目」消歧；``from src.pkg import X`` 这种
    汇总导出沿再导出链追到定义文件——直接按模块路径匹配会漏掉这类真实
    耦合（v2.1.2 前的探针就漏过，险些误判为「无关系」）。
    """

    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".workbuddy"}

    def __init__(self, repo_root: Path, scope=None):
        self.repo_root = Path(repo_root)
        self._index: dict[str, list[str]] = {}
        self._ast_cache: dict[str, ast.Module | None] = {}
        for dp, dn, fn in os.walk(self.repo_root):
            dn[:] = [d for d in dn if d not in self.SKIP_DIRS]
            for f in fn:
                if not f.endswith(".py"):
                    continue
                full = Path(dp) / f
                if scope is not None and not scope.allows(full):
                    continue
                rel = os.path.relpath(full, self.repo_root).replace(os.sep, "/")
                parts = list(Path(rel).with_suffix("").parts)
                if parts and parts[-1] == "__init__":
                    parts = parts[:-1]
                for i in range(len(parts)):
                    dotted = ".".join(parts[i:])
                    if dotted:
                        self._index.setdefault(dotted, []).append(rel)

    @staticmethod
    def _project_of(rel: str) -> str:
        parts = Path(rel).parts
        return "/".join(parts[:2]) if len(parts) > 2 else ""

    def lookup(self, dotted: str, near: str = "") -> str | None:
        cands = self._index.get(dotted) or []
        if not cands:
            return None
        if near:
            pn = self._project_of(near)
            for c in cands:
                if self._project_of(c) == pn:
                    return c
        return cands[0]

    def tree_of(self, rel: str) -> ast.Module | None:
        if rel not in self._ast_cache:
            try:
                self._ast_cache[rel] = ast.parse(
                    (self.repo_root / rel).read_text(encoding="utf-8"), filename=rel)
            except (SyntaxError, UnicodeDecodeError, OSError):
                self._ast_cache[rel] = None
        return self._ast_cache[rel]

    def defined_names(self, rel: str) -> tuple[set[str], dict[str, tuple[str, str]]]:
        """文件顶层定义的名字 + 从别处 import 进来的名字（再导出候选）。"""
        t = self.tree_of(rel)
        if t is None:
            return set(), {}
        local: set[str] = set()
        reexport: dict[str, tuple[str, str]] = {}
        for node in t.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                local.add(node.name)
            elif isinstance(node, ast.Assign):
                for tg in node.targets:
                    if isinstance(tg, ast.Name):
                        local.add(tg.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                local.add(node.target.id)
            elif isinstance(node, ast.ImportFrom):
                base = self.resolve_relative(rel, node.module, node.level)
                for a in node.names:
                    if a.name == "*":
                        continue
                    reexport[a.asname or a.name] = (base, a.name)
        return local, reexport

    def resolve_relative(self, from_rel: str, module: str | None, level: int) -> str:
        """把相对导入还原为绝对点分名。

        ``__init__.py`` 里的 ``from .x import y``：包是 ``__init__`` 所在目录
        本身——去掉 ``__init__`` 后即包，不能再多剥一层。
        """
        if not level:
            return module or ""
        parts = list(Path(from_rel).with_suffix("").parts)
        pkg = parts[:-1]  # 文件所在包；__init__ 的所在包即其目录本身
        if level > 1:
            pkg = pkg[: len(pkg) - (level - 1)]
        if module:
            pkg = pkg + module.split(".")
        return ".".join(pkg)

    def resolve_symbol(self, module: str, name: str, depth: int = 0,
                       seen: set | None = None, near: str = ""):
        """沿再导出链找 name 的真实定义文件。返回 (file, origin, 方式) 或 None。"""
        if depth > 4:
            return None
        seen = seen if seen is not None else set()
        if module in seen:
            return None
        seen.add(module)
        rel = self.lookup(module, near)
        if rel is None:
            sub = self.lookup(f"{module}.{name}" if module else name, near)
            return (sub, name, "module") if sub else None
        local, reexport = self.defined_names(rel)
        if name in local:
            return (rel, name, "defined")
        if name in reexport:
            base, orig = reexport[name]
            if base:
                got = self.resolve_symbol(base, orig, depth + 1, seen,
                                         near=near or rel)
                if got:
                    return got
            sub = self.lookup(f"{base}.{orig}" if base else orig, near or rel)
            if sub:
                return (sub, orig, "module")
            return None
        sub = self.lookup(f"{module}.{name}" if module else name, near)
        if sub:
            return (sub, name, "module")
        return None

    def bindings_of_test(self, rel: str):
        """测试文件全部 import 解析到的文件集合 + 解析失败的名字。"""
        t = self.tree_of(rel)
        if t is None:
            return None, []
        got: set[str] = set()
        failures: list[str] = []
        for node in ast.walk(t):
            if isinstance(node, ast.Import):
                for a in node.names:
                    rel_f = self.lookup(a.name, rel)
                    if rel_f:
                        got.add(rel_f)
            elif isinstance(node, ast.ImportFrom):
                base = self.resolve_relative(rel, node.module, node.level)
                for a in node.names:
                    if a.name == "*":
                        continue
                    r = self.resolve_symbol(base, a.name, near=rel)
                    if r:
                        got.add(r[0])
                    else:
                        failures.append(f"{base}:{a.name}")
        return got, failures


def binding_advisory(repo_root: Path, cfg_all: dict, scope=None, *,
                     resolve_declared=None, glob_files=None) -> dict:
    """对每个「有测试也有实现」的能力做符号级绑定检查（advisory）。

    返回 ``{counts, rows}``；rows 每条含 code/status/tests/impl_files。
    它不参与 level/tier 判定，也不写进账本——账本仍是
    f(registry, 仓库, 报告)；绑定检查是这层函数之外的旁路观察。

    ``resolve_declared`` / ``glob_files`` 由调用方（生成器）注入，签名与
    生成器同名函数一致；不注入则跳过该项检查（保持本模块可独立单测）。
    """
    idx = SymbolIndex(repo_root, scope)
    rows: list[dict] = []
    for project_cfg in normalize_projects(cfg_all):
        proj_rel = project_cfg["root"]
        proj_root = Path(repo_root) / proj_rel
        pcode = project_cfg["code"]
        for midx, mod in enumerate(project_cfg["modules"], 1):
            mcode = str(mod.get("code", "CORE") or "CORE").strip().upper()
            for cidx, cap in enumerate(mod.get("caps") or [], 1):
                domain = str(cap.get("domain")).strip().upper()
                code = codec_cap_code(pcode, mcode, domain, cidx,
                                      cap.get("code", ""))
                declared_tests: list[str] = []
                if resolve_declared is not None:
                    tests_decl = (cap.get("tests")
                                  if isinstance(cap.get("tests"), list) else None)
                    declared_tests, _miss = resolve_declared(
                        repo_root, tests_decl or [], scope, proj_rel)
                impls: set[str] = set()
                if glob_files is not None:
                    impls = {os.path.relpath(x, repo_root).replace(os.sep, "/")
                             for x in glob_files(proj_root, cap.get("impl") or [], scope)}
                row: dict = {"code": code, "tests": len(declared_tests),
                             "impl_files": len(impls)}
                if not declared_tests:
                    row["status"] = "no_tests"
                elif not impls:
                    row["status"] = "no_impl"
                else:
                    hit = 0
                    for t in declared_tests:
                        got, _f = idx.bindings_of_test(t) or (set(), [])
                        if got and (got & impls):
                            hit += 1
                    if hit:
                        row["status"] = "bound"
                        row["tests_bound"] = hit
                    else:
                        bridges: set[str] = set()
                        for t in declared_tests:
                            lvl1, _f = idx.bindings_of_test(t) or (set(), [])
                            for f1 in lvl1:
                                lvl2, _g = idx.bindings_of_test(f1) or (set(), [])
                                if lvl2 & impls:
                                    bridges.add(f1)
                        row["status"] = "via1" if bridges else "unbound"
                        row["bridges"] = sorted(bridges)[:4]
                rows.append(row)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"counts": counts, "rows": rows}


def print_binding_advisory(advisory: dict) -> None:
    """把绑定结果打成一行摘要 + 每条 [UNBOUND] 告警（shadow 门禁口径）。"""
    c = advisory.get("counts", {})
    print("[BIND] 符号级证据绑定（advisory）："
          f"bound {c.get('bound', 0)} / via1 {c.get('via1', 0)} / "
          f"unbound {c.get('unbound', 0)} / no_impl {c.get('no_impl', 0)} / "
          f"no_tests {c.get('no_tests', 0)}")
    for r in advisory.get("rows", []):
        if r["status"] == "unbound":
            print(f"[UNBOUND] {r['code']}: 声明的 {r['tests']} 个测试与声明的实现之间"
                  "无机器可查的调用关系（疑似词面配对错挂；不影响 tier，先晒出）")
        elif r["status"] == "no_impl":
            print(f"[UNBOUND] {r['code']}: 声明了 {r['tests']} 个测试但 impl 为空"
                  "（证据挂不上实现；不影响 tier，先晒出）")
