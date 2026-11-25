#!/usr/bin/env python3
"""存量项目只读发现：从真实文件证据生成 registry 草稿与接入报告。

第一性原理：历史项目的价值在既有代码与决策痕迹，自动化必须先承认「我不知道」。
本脚本因此只做三件事：只读扫描、产出草稿、明确警告；绝不修改源码、账本、
看板或既有 registry.json。草稿需要人工确认后才能成为正式清单。

用法：
    python3 scripts/discover_project.py --target /path/to/project --dry-run
    python3 scripts/discover_project.py --target /path/to/project
    python3 scripts/discover_project.py --target . --max-caps 5 --json

产物（默认写在 <target>/governance/）：
    registry.draft.json   可编辑的能力注册表草稿
    ADOPTION_REPORT.md    人类可读的盘点报告
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCHEMA = "registry-draft/1"
EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", ".workbuddy", ".codegraph", ".gitnexus",
    "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "logs", "artifacts", "governance",
}
SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".scala", ".sql",
}
DOC_EXTS = {".md", ".rst", ".adoc"}
TEST_RE = re.compile(r"(^|/)(tests?|specs?)/|(^|/)test_[^/]+|(^|/)[^/]+\.(test|spec)\.[^/]+$")
ROOT_HINTS = ("src", "app", "lib", "packages", "internal", "services", "modules")


def sanitize_code(name: str, fallback: str = "ITEM") -> str:
    """把任意文件名收敛为契约合法的单段码（[A-Z][A-Z0-9]*）。

    v2.20.0（A 项）：旧实现把非法字符替换成下划线，产出 ``SECRET_SYNC``
    这类违反四段码契约的草稿，生成器随后抛裸 ValueError。契约是跨三处
    的稳定身份，不放宽；这里改生产者——直接剔除非法字符，保留可读大写。
    """
    code = re.sub(r"[^A-Za-z0-9]+", "", name).upper()
    if not code:
        code = re.sub(r"[^A-Za-z0-9]+", "", fallback).upper() or "ITEM"
    if code[0].isdigit():
        code = "X" + code
    return code[:24]


def _module_root(rel: str) -> str:
    parts = Path(rel).parts
    if parts[0] in ROOT_HINTS:
        # src/domain/order.py → src/domain；src/order.py → src
        return "/".join(parts[:2]) if len(parts) > 2 else parts[0]
    return parts[0] if len(parts) > 1 else "."


SPEC_REPO_MAX_CODE_RATIO = 0.25


def _detect_spec_repo(collected: list[str], counts: dict,
                      source_files: list[str]) -> tuple[bool, list[str], list[str]]:
    """规范型仓库识别：少代码多文档 + 结构化标记（SKILL.md / agents/*.md）。

    v2.29.0：代码型发现器对 SKILL.md/agents 文档型仓库产不出有意义的草稿
    （此前 julia 类仓库只能得到空骨架）。识别为 spec-repo 后改以文档结构
    为能力点候选——判据：代码文件占比低（<= 25% 或绝对值极少）且存在标记。
    """
    skill_files = [p for p in collected
                   if p.endswith("SKILL.md") and not TEST_RE.search("/" + p)]
    agent_files = [p for p in collected
                   if p.startswith("agents/") and p.endswith(".md")]
    total = max(counts["scanned"], 1)
    low_code = (len(source_files) <= 3
                or len(source_files) / total <= SPEC_REPO_MAX_CODE_RATIO)
    marked = bool(skill_files or agent_files)
    return (low_code and marked, skill_files, agent_files)


def _cap_from_file(rel: str, used: set[str]) -> dict:
    stem = Path(rel).stem if not rel.endswith("SKILL.md") else Path(rel).parent.name
    domain = sanitize_code(stem, "ITEM")
    if domain in used:
        domain = f"{domain}{len(used) + 1:02d}"
    used.add(domain)
    return {"name": stem.replace("_", " ").replace("-", " ").strip().title() or stem,
            "domain": domain, "impl": [rel],
            "hints": [stem.lower()]}


def _spec_repo_modules(skill_files: list[str], agent_files: list[str],
                       source_files: list[str], max_caps: int) -> list[dict]:
    """spec-repo 草稿：TEAM=agents、SKILLS=SKILL.md、INFRA=残余源码。"""
    modules: list[dict] = []
    if agent_files:
        used: set[str] = set()
        caps = [_cap_from_file(rel, used) for rel in sorted(agent_files)][:max_caps]
        modules.append({"code": "TEAM", "name": "专家团队", "src": ["agents/"], "caps": caps})
    if skill_files:
        used: set[str] = set()
        caps = [_cap_from_file(rel, used) for rel in sorted(skill_files)][:max_caps]
        modules.append({"code": "SKILLS", "name": "技能", "src": ["skills/"], "caps": caps})
    residual = [p for p in source_files
                if p not in ("agents/",) and not p.startswith("agents/")
                and "/skills/" not in f"/{p}"]
    if residual:
        used: set[str] = set()
        caps = [_cap_from_file(rel, used) for rel in sorted(residual)][:max_caps]
        modules.append({"code": "INFRA", "name": "基建脚本", "src": ["scripts/"], "caps": caps})
    if not modules:
        modules.append({"code": "CORE", "name": "核心能力", "src": [], "caps": []})
    return modules


def discover(target: Path, max_files: int = 3000, max_caps: int = 8) -> dict:
    """只读扫描并返回草稿 dict。target 必须是项目根目录。"""
    collected: list[str] = []
    counts = {"source": 0, "test": 0, "doc": 0, "config": 0,
              "scanned": 0, "truncated": False}
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs
                         if d not in EXCLUDE_DIRS and not d.startswith("."))
        rel_root = Path(os.path.relpath(root, target))
        for name in sorted(files):
            if counts["scanned"] >= max_files:
                counts["truncated"] = True
                break
            if name.startswith("."):
                continue
            counts["scanned"] += 1
            rel = (rel_root / name).as_posix().lstrip("./")
            collected.append(rel)
            low = name.lower()
            ext = Path(name).suffix.lower()
            if TEST_RE.search("/" + rel):
                counts["test"] += 1
            elif ext in SOURCE_EXTS:
                counts["source"] += 1
            elif ext in DOC_EXTS:
                counts["doc"] += 1
            elif low in {"package.json", "pyproject.toml", "requirements.txt",
                         "cargo.toml", "go.mod", "makefile", "dockerfile"}:
                counts["config"] += 1
        if counts["truncated"]:
            break

    source_files = [
        p for p in collected
        if Path(p).suffix.lower() in SOURCE_EXTS and not TEST_RE.search("/" + p)
    ]

    warnings: list[str] = []
    spec_mode, skill_files, agent_files = _detect_spec_repo(
        collected, counts, source_files)
    if spec_mode:
        modules = _spec_repo_modules(skill_files, agent_files, source_files, max_caps)
        warnings.append("规范型仓库模式：能力点候选来自 SKILL.md/agents 文档结构，"
                        "编码与分域需人工确认（draft 仅供采纳起点）。")
    else:
        groups: dict[str, list[str]] = {}
        for rel in source_files:
            groups.setdefault(_module_root(rel), []).append(rel)

    if counts["truncated"]:
        warnings.append(f"扫描在 {max_files} 个文件处截断，草稿可能不完整。")
    if not source_files:
        warnings.append("未发现可识别的源码文件；草稿仅提供治理骨架，请手工补能力。")
    if not counts["test"]:
        warnings.append("未发现测试文件；这些能力预期停在 L0-L2，不要误判为完成。")
    if not counts["doc"]:
        warnings.append("未发现文档文件；文档索引预计为空。")

    if not spec_mode:
        modules = []
        used_codes: set[str] = set()
        for group in sorted(groups):
            paths = sorted(groups[group])
            leaf = Path(group).name if group != "." else target.name
            base_code = sanitize_code(leaf, "CORE")
            code = base_code
            n = 2
            while code in used_codes:
                code = f"{base_code}{n:02d}"
                n += 1
            used_codes.add(code)

            caps: list[dict] = []
            used_domains: set[str] = set()
            for rel in paths[:max_caps]:
                stem = Path(rel).stem
                domain = sanitize_code(stem, "ITEM")
                if domain in used_domains:
                    domain = f"{domain}{len(used_domains) + 1:02d}"
                used_domains.add(domain)
                caps.append({
                    "name": stem.replace("_", " ").strip().title() or stem,
                    "domain": domain,
                    "impl": [rel],
                    "hints": [stem.lower(), leaf.lower()],
                })
            if len(paths) > max_caps:
                warnings.append(f"{group} 发现 {len(paths)} 个源码文件，草稿只取前 {max_caps} 个。")
            modules.append({
                "code": code,
                "name": leaf.replace("_", " ").strip().title() or leaf,
                "src": [group.rstrip("/") + "/"],
                "caps": caps,
            })

        if not modules:
            modules.append({"code": "CORE", "name": "核心能力", "src": [], "caps": []})

    draft = {
        "_comment": "只读发现的草稿：需人工确认与精简，再复制为 governance/registry.json。",
        "_discovery": {
            "schema": SCHEMA,
            "source": "filesystem-only/spec-repo" if spec_mode else "filesystem-only",
            "counts": counts,
            "warnings": warnings,
            "candidate_modules": len(modules),
            "candidate_caps": sum(len(m["caps"]) for m in modules),
            "confidence": ("medium" if sum(len(m["caps"]) for m in modules) else "low")
                          if spec_mode else
                          ("medium" if source_files and counts["test"] else "low"),
        },
        "project": {
            "code": "NEWPROJ",
            "name": target.name,
            "root": ".",
            "governance_gate": False,
            "contracts_dir": "src/contracts",
            "unit_test_dir": "tests",
            "test_record_dir": "docs/test_records",
            "docs_dir": "docs",
            "governance_dir": "governance",
        },
        "modules": modules,
    }
    return draft


def render_report(draft: dict) -> str:
    d = draft["_discovery"]
    c = d["counts"]
    lines = [
        "# 存量项目接入报告",
        "",
        "> 本报告由只读扫描生成，未修改任何既有文件。草稿需经人工确认才可成为正式清单。",
        "",
        f"- 模式：{d['source']} / schema {d['schema']}",
        f"- 文件计数：源码 {c['source']}、测试 {c['test']}、文档 {c['doc']}、配置 {c['config']}",
        f"- 候选：模块 {d['candidate_modules']}、能力点 {d['candidate_caps']}",
        f"- 置信度：{d['confidence']}",
        "",
        "## 候选模块",
        "",
        "| 模块码 | 扫描入口 | 能力点数 |",
        "|---|---|---:|",
    ]
    for m in draft["modules"]:
        lines.append(f"| {m['code']} | {', '.join(m['src']) or '（无）'} | {len(m['caps'])} |")
    lines.extend(["", "## 警告", ""])
    if d["warnings"]:
        lines.extend(f"- {w}" for w in d["warnings"])
    else:
        lines.append("- 无")
    lines.extend([
        "",
        "## 下一步",
        "",
        "1. 编辑 `governance/registry.draft.json`：删除非能力文件、合并重复域、校准 hints。",
        "2. 用 `init_project.py --mode adopt --from-draft ...` 生成治理骨架。",
        "3. 在项目根运行 `governance/build_capability_model.py --root . --dry-run` 对照真实等级。",
        "4. 确认后再正式生成并跑 `governance/verify_ledger.py --root . --strict`。",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="存量项目根目录")
    ap.add_argument("--out-dir", help="草稿输出目录（默认 <target>/governance）")
    ap.add_argument("--max-files", type=int, default=3000, help="扫描文件数上限")
    ap.add_argument("--max-caps", type=int, default=8, help="每个模块最多保留的能力点数")
    ap.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    ap.add_argument("--force", action="store_true", help="覆盖既有草稿与报告")
    ap.add_argument("--json", action="store_true", help="输出 JSON 草稿")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(f"目标目录不存在：{args.target}", file=sys.stderr)
        return 2

    draft = discover(target, max_files=args.max_files, max_caps=args.max_caps)
    report = render_report(draft)
    if args.json:
        print(json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.dry_run:
        print(report)
    else:
        out = Path(args.out_dir).expanduser().resolve() if args.out_dir else target / "governance"
        out.mkdir(parents=True, exist_ok=True)
        written = []
        for name, content in (("registry.draft.json",
                               json.dumps(draft, ensure_ascii=False, indent=2) + "\n"),
                              ("ADOPTION_REPORT.md", report)):
            path = out / name
            if path.exists() and not args.force:
                print(f"跳过（已存在，如需覆盖请加 --force）: {path}")
                continue
            path.write_text(content, encoding="utf-8")
            written.append(path)
            print(f"写入: {path}")
        if not written:
            print("没有写入任何文件；既有草稿与报告保持原样。")
        d = draft["_discovery"]
        print(f"盘点完成：源码 {d['counts']['source']} / 测试 {d['counts']['test']} / "
              f"文档 {d['counts']['doc']}，候选能力 {d['candidate_caps']}，"
              f"置信度 {d['confidence']}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
