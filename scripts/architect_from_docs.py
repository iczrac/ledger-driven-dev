#!/usr/bin/env python3
"""从规范化文档抽取目标架构（文档 → 规划图）。

与 discover_project.py（文件系统 → 现状草稿）互补：本脚本读的是人写下的目标——
registry 的能力声明（code / committed / target_level / depends_on）为规划码唯一来源，
PROJECT_BRIEF / MODULE_MAP 只增强目标与模块，CAPABILITY_INDEX 仅作现状投影，
产出 TARGET_ARCHITECTURE.json，供 compare_graphs.py 与实际能力图比对。

用法：
    python3 scripts/architect_from_docs.py --target /path/to/project --dry-run
    python3 scripts/architect_from_docs.py --target /path/to/project
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from trace_common import (STRICT_CODE_RE, canonical_code, iter_code_candidates,
                          load_json, registry_iter_caps, rel_path, write_if_absent)

DEP_RE = re.compile(r"依赖\s*[:：]\s*((?:[A-Z][A-Z0-9]*\.){3}\d{2}(?:\s*[,，、]\s*(?:[A-Z][A-Z0-9]*\.){3}\d{2})*)")
TARGET_RE = re.compile(r"目标\s*[:：]\s*L([0-5])")


def _section(text: str, title: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            inside = line.strip() == f"## {title}"
            continue
        if inside and line.strip().startswith("- "):
            out.append(line.strip()[2:].strip())
    return out


def build(target: Path, docs_dir: Path, registry: dict) -> dict:
    files = sorted(p for p in docs_dir.rglob("*.md") if p.is_file()) if docs_dir.exists() else []
    texts = {rel_path(p, target): p.read_text(encoding="utf-8", errors="replace") for p in files}
    warnings: list[str] = []
    if not texts:
        warnings.append("未发现文档；目标架构为空，请先运行 rebuild_docs.py 或手工写规划文档。")

    codes: dict[str, dict] = {}

    def valid_code(src: str, lineno: int, token: str) -> str:
        """唯一抽码口径：候选先过严格 codec，非法则给出可操作的改法并 fail-closed。"""
        if STRICT_CODE_RE.fullmatch(token):
            return token
        suggestion = canonical_code(token)
        hint = suggestion or "大写四段式，段内只用字母/数字，序号两位"
        raise ValueError(f"{src}:{lineno} 发现非四段式能力码 {token}；"
                         f"请改为 {hint}（registry_codec 是唯一 codec）")

    # E2：规划码唯一来源是 registry 的人工声明（committed / target_level / depends_on）。
    # CAPABILITY_INDEX 是账本现状投影，只能补充已知码的名称与 impl_hint，
    # 不得反向定义规划集——否则「账本投影 → 规划 → 与实际账本比对」就是自证。
    declared = 0
    # 与 CAPABILITY_INDEX 完全同一套 codec：显式 code 优先，否则按 registry 顺序派生。
    declared_caps = registry_iter_caps(registry)
    pos = 0
    for m in registry.get("modules", []):
        for c in m.get("caps", []) or []:
            raw = declared_caps[pos] if pos < len(declared_caps) else None
            pos += 1
            if not raw:
                continue
            code = valid_code("registry.json", 0, str(raw["code"]).upper())
            codes[code] = {
                "code": code, "sources": ["registry.json"], "name": str(c.get("name", "")),
                "depends_on": [str(x) for x in (c.get("depends_on") or [])],
                "target_level": c.get("target_level"),
                "impl_hint": [], "committed": bool(c.get("committed")),
            }
            declared += 1
    if not declared:
        warnings.append("registry 未声明任何能力码；规划集为空，请先在唯一手写清单中声明。")

    index_src = next((k for k in texts if k.endswith("CAPABILITY_INDEX.md")),
                     "docs/generated/CAPABILITY_INDEX.md")
    index_text = texts.get(index_src, "")
    for lineno, token in iter_code_candidates(index_text):
        code = valid_code(index_src, lineno, token)
        if code not in codes:
            continue  # 现状投影不得新增规划条目
        entry = codes[code]
        row = next((l for l in index_text.splitlines()
                    if l.startswith("| " + code + " |")), "")
        if row:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) > 2 and cells[2] and not entry["name"]:
                entry["name"] = cells[2]
            if len(cells) > 5 and cells[5] and cells[5] != "—":
                entry["impl_hint"] = sorted({x.strip("` ")
                                             for x in cells[5].split(",") if x.strip("` ")})

    # 手写文档只做增强：目标：Lx / 依赖：CODE 只对已存在的规划码生效。
    for src, text in texts.items():
        if src == index_src:
            continue
        lines = text.splitlines()
        for lineno, line in enumerate(lines, 1):
            present = [t for _, t in iter_code_candidates(line) if t in codes]
            if not present:
                continue
            tl = TARGET_RE.search(line)
            for code in present:
                if src not in codes[code]["sources"]:
                    codes[code]["sources"].append(src)
                if tl:
                    codes[code]["target_level"] = f"L{tl.group(1)}"
            dep = DEP_RE.search(line)
            if dep:
                for parent_token in present:
                    for _, child_token in iter_code_candidates(dep.group(1)):
                        child = valid_code(src, lineno, child_token)
                        if child not in codes:
                            continue  # 未知码只提示，不新增规划条目
                        if child != parent_token and child not in codes[parent_token]["depends_on"]:
                            codes[parent_token]["depends_on"].append(child)

    brief = next((v for k, v in texts.items() if k.endswith("PROJECT_BRIEF.md")), "")
    goals = _section(brief, "目标")
    if not goals:
        warnings.append("PROJECT_BRIEF.md 缺少「## 目标」小节；目标架构将只包含编码结构。")
        goals = [f"覆盖能力 {len(codes)} 项（由文档编码推断）"] if codes else []

    modules: dict[str, dict] = {}
    map_src = next((k for k in texts if k.endswith("MODULE_MAP.md")), "MODULE_MAP.md")
    map_text = texts.get(map_src, "")
    for lineno, line in enumerate(map_text.splitlines(), 1):
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"[A-Z][A-Z0-9]*", cells[0]) or cells[0] == "模块":
            continue
        mcode, name, src, cap_cells = cells[0], cells[1], cells[2], cells[3]
        if cap_cells.strip() in ("", "（无）", "—", "-"):
            # 能力列留空是合法的人写缺口：从同一份文档已抽取的编码按模块回退。
            caps = [c["code"] for c in codes.values()
                    if c["code"].split(".")[1] == mcode]
        else:
            # B 项：合法性仍经唯一 codec 校验（generated 投影里的坏码必须 fail-closed），
            # 但只纳入规划集内已存在的码，手写表格的示例码不得反向污染规划图。
            caps = []
            for _, token in iter_code_candidates(cap_cells):
                checked = valid_code(map_src, lineno, token)
                if checked in codes:
                    caps.append(checked)
        modules[mcode] = {
            "code": mcode, "name": name,
            "src": [x.strip("` ") for x in src.split(",") if x.strip() and x.strip() != "（无）"],
            "caps": caps,
        }

    if not modules and codes:
        for code, info in codes.items():
            mcode = code.split(".")[1]
            modules.setdefault(mcode, {"code": mcode, "name": mcode, "src": [], "caps": []})
            modules[mcode]["caps"].append(code)
        warnings.append("未解析到 MODULE_MAP 表格；模块名与 src 由编码推断，请人工校准。")

    project_code = str(registry.get("project", {}).get("code", "")).upper()
    if not project_code and codes:
        project_code = next(iter(codes.values()))["code"].split(".")[0]
    confidence = "high" if goals and modules and codes else ("medium" if codes else "low")
    return {
        "schema": "target-arch/1",
        "source": "registry-declaration",
        "project": {
            "code": project_code,
            "name": str(registry.get("project", {}).get("name", project_code)),
        },
        "goals": goals,
        "modules": [modules[k] for k in sorted(modules)],
        "capabilities": [codes[k] for k in sorted(codes)],
        "source_docs": sorted(texts),
        "warnings": warnings,
        "confidence": confidence,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根目录")
    ap.add_argument("--docs-dir", help="文档目录（默认 <target>/docs）")
    ap.add_argument("--out", help="输出路径（默认 <target>/governance/TARGET_ARCHITECTURE.json）")
    ap.add_argument("--force", action="store_true", help="覆盖既有目标架构")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    docs = Path(args.docs_dir).expanduser().resolve() if args.docs_dir else target / "docs"
    gov = target / "governance"
    reg_path = gov / "registry.json"
    registry = load_json(reg_path, "registry") if reg_path.exists() else {}
    try:
        result = build(target, docs, registry)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out = Path(args.out).expanduser().resolve() if args.out else gov / "TARGET_ARCHITECTURE.json"

    if not args.dry_run:
        status = write_if_absent(out, json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                 args.force)
        if not args.json:
            print(f"[{status}] {out}")
    if args.json or args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"目标架构：模块 {len(result['modules'])} / 能力 {len(result['capabilities'])} "
              f"/ 目标 {len(result['goals'])}，置信度 {result['confidence']}")
        for w in result["warnings"]:
            print(f"[WARN] {w}")
        if not sys.stdout.isatty():
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
