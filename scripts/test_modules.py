#!/usr/bin/env python3
"""测试架构校验：让「按开发模块组织」成为可复算事实，而不是目录外观。

为什么
------
方法论要求项目用 `PROJ.MODULE.DOMAIN.NN` 把「文档 - 测试 - 代码 - 账本」
对应起来，但自己原有的 17 个 `tests/test_*.py` 是扁平的：按脚本横切命名，
没有模块归属，也没有机器能检查的映射。目录好看不等于架构成立。

v1.2.0 把测试按六个开发模块重组，并用三处互相自证：
  1. `tests/MODULES.json`：模块 → 文件 → 所属脚本的唯一清单；
  2. 每个测试文件里的 `MODULE_ID`：文件自证归属，防「清单对了目录搬错了」；
  3. `scripts/run_tests.py` 的 `rglob("test_*.py")`：发现口径与清单必须一致。

另外 `--target P` 会把目标项目的能力模块与 `doc_index.unit_tests` 对齐，
输出「哪个模块还没有测试」，把测试架构检查推广到被治理项目。

用法
----
    python3 scripts/test_modules.py --check
    python3 scripts/test_modules.py --json
    python3 scripts/test_modules.py --emit-md docs/generated/TEST_MODULES.md
    python3 scripts/test_modules.py --target P --json

退出码：0 通过；1 目标项目存在无测试模块；2 定义自检失败。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_REL = "tests/MODULES.json"
SCHEMA = "test-modules/1"
SCHEMA_CHECK = "test-modules-check/1"
PATTERN = "test_*.py"
MODULE_ID_RE = re.compile(r"^MODULE_ID\s*=\s*[\"']([^\"']+)[\"']", re.M)


def load_map(root: Path = ROOT) -> dict:
    return json.loads((Path(root) / MAP_REL).read_text(encoding="utf-8"))


def discovered(root: Path = ROOT) -> list[str]:
    test_dir = Path(root) / "tests"
    return sorted(p.relative_to(root).as_posix()
                  for p in test_dir.rglob(PATTERN) if p.is_file()
                  and "__pycache__" not in p.parts)


def declared(root: Path = ROOT) -> list[str]:
    m = load_map(root)
    return sorted(f for mod in m["modules"] for f in mod["files"])


def validate(root: Path = ROOT) -> list[str]:
    root = Path(root)
    m = load_map(root)
    errs: list[str] = []
    if m.get("schema") != SCHEMA:
        errs.append(f"清单 schema 错误：{m.get('schema')}")
    ids = [x["id"] for x in m["modules"]]
    if len(ids) != len(set(ids)) or any(not x for x in ids):
        errs.append("模块 id 必须唯一且非空")
    # 避开标准库冲突：unittest discover 会把同名顶层模块当成非包
    for x in ids:
        if x in {"platform", "trace", "test", "types", "inspect", "json", "logging"}:
            errs.append(f"模块名 {x} 与标准库/内建模块冲突，会导致 discover 误解析")
    files = [f for x in m["modules"] for f in x["files"]]
    if len(files) != len(set(files)):
        errs.append("同一测试文件被分配到多个模块")
    disc = discovered(root)
    if sorted(files) != disc:
        errs.append("清单与 rglob 发现结果不一致："
                    f"仅清单={sorted(set(files)-set(disc))[:3]} "
                    f"仅磁盘={sorted(set(disc)-set(files))[:3]}")
    for mod in m["modules"]:
        mid = mod["id"]
        if not mod.get("name") or not mod.get("scope") or not mod.get("owner_scripts"):
            errs.append(f"{mid}: 缺 name / scope / owner_scripts")
        for s in mod.get("owner_scripts", []):
            if not (root / s).is_file():
                errs.append(f"{mid}: 所属脚本不存在 {s}")
        for rel in mod.get("files", []):
            p = root / rel
            if not p.is_file():
                errs.append(f"{mid}: 测试文件不存在 {rel}")
                continue
            if not rel.startswith(f"tests/{mid}/"):
                errs.append(f"{mid}: 文件不在本模块目录 {rel}")
            found = MODULE_ID_RE.search(p.read_text(encoding="utf-8"))
            if not found:
                errs.append(f"{rel}: 缺少 MODULE_ID 常量")
            elif found.group(1) != mid:
                errs.append(f"{rel}: MODULE_ID={found.group(1)} 与清单 {mid} 不一致")
            try:
                ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                errs.append(f"{rel}: 语法错误 {exc}")
    runner = (root / "scripts" / "run_tests.py").read_text(encoding="utf-8")
    if PATTERN not in runner:
        errs.append("run_tests.py 的默认发现模式与清单口径不一致")
    return errs


def target_report(target: Path) -> dict:
    """目标项目：能力模块 ↔ 单测路径的缺口报告（只读）。"""
    target = Path(target)
    ledger_path = target / "governance" / "DECISION_LEDGER.json"
    if not ledger_path.is_file():
        raise ValueError(f"目标项目缺少账本：{ledger_path}")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    cm = ledger.get("capability_model") or {}
    rows = []
    for p in cm.get("projects", []):
        for m in p.get("modules", []):
            caps = m.get("caps", [])
            tests = sorted({(x.get("path") if isinstance(x, dict) else str(x))
                            for c in caps
                            for x in (c.get("doc_index") or {}).get("unit_tests", [])
                            if x})
            rows.append({"module": m.get("code", ""), "capabilities": len(caps),
                         "unit_tests": len(tests), "paths": tests,
                         "status": "ok" if tests else "no-tests"})
    return {"schema": "test-module-coverage/1", "target": ".",
            "modules": rows,
            "modules_without_tests": [r["module"] for r in rows if not r["unit_tests"]],
            "note": "只读；缺口由人在 registry 补 unit_test 声明后再跑测试报告"}


def render_md(root: Path = ROOT) -> str:
    m = load_map(root)
    disc = discovered(root)
    lines = [
        "# 测试架构与模块映射（生成物）", "",
        "> 由 `scripts/test_modules.py` 从 `tests/MODULES.json` 渲染。",
        "> **不要手改**；增删测试请改清单并重跑 `--emit-md`。", "",
        f"共 {len(m['modules'])} 个开发模块 · {len(disc)} 个 `test_*.py` · "
        f"发现口径 `{m['discovery']}`。", "",
        "| 模块 id | 名称 | 覆盖域 | 所属脚本 | 测试文件 |",
        "|---|---|---|---|---|",
    ]
    for x in m["modules"]:
        lines.append(f"| `{x['id']}` | {x['name']} | {x['scope']} | " +
                     ", ".join(f"`{s}`" for s in x["owner_scripts"]) +
                     " | " + ", ".join(f"`{f}`" for f in x["files"]) + " |")
    lines += ["", "## 纪律", "",
              "- 每个测试文件必须有 `MODULE_ID`，且与所在目录、清单三者一致；",
              "- 模块名不得与 Python 标准库冲突，否则 `unittest discover` 会误解析；",
              "- `run_tests.py` 的 `rglob` 与 `unittest discover` 是两套交叉验证，",
              "  两者用例数必须相同（门禁里都跑）；",
              "- `--target P` 可检查被治理项目的能力模块是否缺单测。", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="自检测试架构定义")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--emit-md", help="渲染 Markdown 到指定路径")
    ap.add_argument("--target", help="被治理项目根目录（只读覆盖报告）")
    ap.add_argument("--root", default=str(ROOT), help="方法论仓库根")
    args = ap.parse_args(argv)
    root = Path(args.root).expanduser().resolve()

    if args.emit_md:
        p = Path(args.emit_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_md(root), encoding="utf-8")
        print(f"已生成 {p}")
        return 0
    if args.target:
        try:
            result = target_report(Path(args.target).expanduser().resolve())
        except ValueError as exc:
            print(f"拒绝：{exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if result["modules_without_tests"] and not args.json else 0
    errs = validate(root)
    result = {"schema": SCHEMA_CHECK, "ok": not errs, "errors": errs,
              "modules": len(load_map(root)["modules"]),
              "test_files": len(discovered(root))}
    if args.check or not args.json:
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 2
        if not args.json:
            print(f"测试架构自检通过：{result['modules']} 个模块 / "
                  f"{result['test_files']} 个测试文件")
            return 0
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errs else 2


if __name__ == "__main__":
    raise SystemExit(main())
