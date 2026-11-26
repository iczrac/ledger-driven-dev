#!/usr/bin/env python3
"""确定性专家路由：把「项目状态 + 用户意图」映射成唯一负责人。

设计原则（第一性原理）：
  1. 证据先于权威：先读真实文件系统，不信口头描述；
  2. 单一事实源：只给建议，不写账本、不改源码；
  3. 最小权限：每个专家只拿完成本职责所需的技能与工具；
  4. 确定性：相同输入必得相同输出，冲突时不猜、要求澄清；
  5. fail-closed：账本损坏或状态不明时先停下来审计，不进入编码。

用法：
    python3 scripts/route_expert.py --target /path/to/project --intent "历史项目，帮我接手"
    python3 scripts/route_expert.py --target . --intent "CI 校验账本" --json
    python3 scripts/route_expert.py --target . --mode greenfield --intent "新建项目"

输出 schema: expert-route/1（--json）。仅依赖标准库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from board_path import resolve

SCHEMA = "expert-route/1"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
ASSET_SCHEMA = "expert-assets/1"
# 与 asset_bundle.py 的 sha256-files-v1 对齐：同一份资产，无论从权威源算还是从
# 安装副本算，都必须得到同一个摘要。此前两边各用一套规范化（有无安装前缀、
# 有无尾换行），同一件事产出两个值，且后者无人对账。
INSTALL_PREFIX = ".workbuddy/"
FM_NAME = re.compile(r"^name:\s*([A-Za-z0-9._-]+)\s*$", re.M)
FM_DESC = re.compile(r"^description:\s*\|?\s*(.*)$", re.M)


def _fm(text: str) -> tuple[str, str, str]:
    """极简 frontmatter 读取：name / description 首行 / Triggers 行。标准库实现。"""
    head = text.split("---", 2)
    block = head[1] if len(head) >= 3 else ""
    m = FM_NAME.search(block)
    name = m.group(1) if m else ""
    desc = ""
    triggers = ""
    for line in block.splitlines():
        s = line.strip()
        if not desc and s and not s.startswith(("name:", "description:", "license:",
                                                "metadata:", "risk_level:", "related_skills:")):
            desc = s
        if s.lower().startswith("triggers:"):
            triggers = s
    return name, desc, triggers


def asset_root(target: Path, explicit: Path | None = None) -> Path:
    """优先读项目内已安装的资产，其次回落方法论仓库源。"""
    if explicit:
        return Path(explicit)
    installed = Path(target) / ".workbuddy"
    if (installed / "experts").is_dir() and (installed / "skills").is_dir():
        return installed
    return SOURCE_ROOT


def installed_manifest_paths(root: Path) -> set[str] | None:
    """项目级 .workbuddy/ 有资产清单时，只认清单内的只读部署副本。

    真实项目常在 .workbuddy/skills/ 下放自有技能（格式未必符合方法论
    frontmatter 约定）。它们不是被安装的资产，不该让 --check-assets 把
    「项目自有技能缺 description」误判成方法论资产 incomplete。
    清单缺失 / 损坏 / root 不是项目级资产目录时返回 None，保持全量枚举。
    """
    root = Path(root)
    if root.name != ".workbuddy":
        return None
    mf = root.parent / "governance" / "ASSET_MANIFEST.json"
    if not mf.is_file():
        return None
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    prefix = str(data.get("install_root", ".workbuddy")).rstrip("/") + "/"
    paths = {
        str(row.get("path", ""))[len(prefix):]
        for row in data.get("files", [])
        if isinstance(row, dict) and str(row.get("path", "")).startswith(prefix)
    }
    return paths or None


def load_assets(root: Path, scope: set[str] | None = None) -> dict:
    """真正读取 EXPERT.md / SKILL.md 内容，而不是只信任硬编码卡片。

    scope 由 installed_manifest_paths() 给出：只把清单内的只读副本当作
    方法论资产；项目自有技能不参与摘要，也不参与 frontmatter 检查。
    """
    root = Path(root)
    experts: dict[str, dict] = {}
    skills: dict[str, dict] = {}
    rows: list[str] = []
    files: dict[str, str] = {}
    for group, pattern, out in (("experts", "experts/*/EXPERT.md", experts),
                                ("skills", "skills/*/SKILL.md", skills)):
        for p in sorted(root.glob(pattern)):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if scope is not None and rel not in scope:
                continue
            text = p.read_text(encoding="utf-8")
            name, desc, triggers = _fm(text)
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            out[p.parent.name] = {"name": name, "description": desc,
                                  "triggers": triggers, "sha256": sha}
            files[rel] = sha
            rows.append(f"{INSTALL_PREFIX}{rel}:{sha}\n")
    missing_experts = sorted(set(EXPERT_CARDS) - set(experts))
    referenced = {s for c in EXPERT_CARDS.values() for s in c["skills"]}
    missing_skills = sorted(referenced - set(skills))
    return {
        "schema": ASSET_SCHEMA,
        "root_kind": "installed" if root.name == ".workbuddy" else "source",
        "expert_count": len(experts), "skill_count": len(skills),
        "digest": hashlib.sha256("".join(rows).encode("utf-8")).hexdigest(),
        "digest_algorithm": "sha256-files-v1",
        "files": files,
        "missing_experts": missing_experts, "missing_skills": missing_skills,
        "status": "ok" if not (missing_experts or missing_skills) else "incomplete",
        "experts": experts, "skills": skills,
        "scoped": scope is not None, "asset_count": len(rows),
        "note": "卡片不再只是硬编码：路由输出携带真实资产摘要，缺文件即 fail-closed",
    }


def _manifest_expectation(root: Path) -> dict | None:
    """账面对资产的期望：清单登记了哪些副本、每个副本的 sha256、整包摘要。

    只在项目级 `.workbuddy/` 且有 `governance/ASSET_MANIFEST.json` 时成立。
    没有清单就没有「账」，返回 None，由调用方标 manifest_checked=False。
    """
    root = Path(root)
    if root.name != ".workbuddy":
        return None
    mf = root.parent / "governance" / "ASSET_MANIFEST.json"
    if not mf.is_file():
        return None
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    prefix = str(data.get("install_root", ".workbuddy")).rstrip("/") + "/"
    entries: dict[str, str] = {}
    for row in data.get("files") or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path", ""))
        if not path.startswith(prefix):
            continue
        entries[path[len(prefix):]] = str(row.get("sha256", ""))
    return {"entries": entries, "digest": str(data.get("digest", "")),
            "manifest": str(mf.relative_to(root.parent).as_posix())}


def check_assets(root: Path) -> dict:
    """资产自检：既有「形态合法」，也有「字节等于账面」。

    只查 frontmatter 的回答是「这个名字写没写全」，回答不了「装进来的东西
    还是不是发出去的那份」。所以清单存在时必须逐文件对账 + 整包摘要对账，
    任一不符即 ok=False（fail-closed），而不是把摘要当装饰打印出来。
    """
    scope = installed_manifest_paths(root)
    a = load_assets(root, scope)
    errors = list(a["missing_experts"])
    errors += ["skills/" + s for s in a["missing_skills"]]
    for group in ("experts", "skills"):
        for dirname, meta in a[group].items():
            if meta["name"] != dirname:
                errors.append(f"{group}/{dirname}: frontmatter name={meta['name']} 与目录名不一致")
            if not meta["description"]:
                errors.append(f"{group}/{dirname}: 缺少 description")

    exp = _manifest_expectation(root)
    digest_match: bool | None = None
    if exp:
        for rel, want in sorted(exp["entries"].items()):
            got = a["files"].get(rel)
            if got is None:
                errors.append(f"manifest:{rel}: 清单登记的副本不存在")
            elif got != want:
                errors.append(f"manifest:{rel}: sha256 与清单不符（副本被改或清单过期）")
        for rel in sorted(set(a["files"]) - set(exp["entries"])):
            errors.append(f"manifest:{rel}: 安装副本未登记在清单内")
        if exp["digest"]:
            digest_match = a["digest"] == exp["digest"]
            if not digest_match:
                errors.append("manifest:整包摘要不一致（账面 %s… vs 实测 %s…）"
                              % (exp["digest"][:12], a["digest"][:12]))

    return {"schema": "expert-assets-check/1", "ok": not errors,
            "errors": errors, "digest": a["digest"],
            "digest_algorithm": a["digest_algorithm"],
            "manifest_checked": exp is not None,
            "manifest": (exp or {}).get("manifest", ""),
            "digest_match": digest_match,
            "expert_count": a["expert_count"], "skill_count": a["skill_count"],
            "scoped": a["scoped"], "asset_count": a["asset_count"]}

EXPERT_CARDS = {
    "expert-router": {
        "title": "专家路由",
        "duty": "识别状态与意图，选唯一负责人；冲突时要求澄清。",
        "skills": ["intent-restate", "expert-route"],
        "writes": [],
    },
    "greenfield-architect": {
        "title": "新建项目架构师",
        "duty": "从最小意图生成项目治理骨架，只声明必要能力，不替人排业务优先级。",
        "skills": ["project-bootstrap", "layout-inspect", "doc-rebuild", "ledger-scan", "ledger-verify"],
        "writes": ["governance/registry.json", "governance/DECISION_LEDGER.json"],
    },
    "project-archaeologist": {
        "title": "存量项目考古专家",
        "duty": "只读盘点历史项目，产出 registry 草稿与接入报告，绝不覆盖既有治理文件。",
        "skills": ["project-discover", "layout-inspect", "graph-compare", "ledger-scan", "ledger-verify"],
        "writes": ["governance/registry.draft.json", "governance/ADOPTION_REPORT.md"],
    },
    "ledger-steward": {
        "title": "账本治理专家",
        "duty": "维护决策取代链、确认经验、从 next_queue 产出可执行任务卡。",
        "skills": ["ledger-scan", "ledger-verify", "ledger-decide", "ledger-lesson",
                   "graph-compare", "layout-inspect", "agent-gate", "work-panel",
                   "doc-lifecycle", "doc-rebuild"],
        "writes": ["entries", "lessons.items", "docs.registry", "docs.obligations"],
    },
    "evidence-auditor": {
        "title": "证据审计专家",
        "duty": "跑不变量与实测报告，识别假绿灯；失败时冻结后续写入。",
        "skills": ["ledger-guard", "ledger-verify", "graph-compare", "layout-inspect",
                   "agent-gate", "board-layout", "scale-budget", "test-map", "work-panel",
                   "doc-lifecycle"],
        "writes": [],
    },
    "loop-executor": {
        "title": "循环执行专家",
        "duty": "从一条任务卡补齐契约/实现/单测/测试记录；不得改等级、历史或看板。",
        "skills": ["ledger-scan", "ledger-verify", "doc-rebuild", "graph-compare",
                   "agent-gate", "work-panel", "test-map", "doc-lifecycle"],
        "writes": ["src/**", "tests/**", "docs/test_records/**"],
    },
    "release-steward": {
        "title": "生命周期与发布治理专家",
        "duty": "冻结/归档/退役/移交期间只做只读取证；解冻与归档必须有人批准记录。",
        "skills": ["ledger-verify", "ledger-guard", "graph-compare", "scenario-guard",
                   "layout-inspect", "agent-gate"],
        "writes": ["lifecycle", "retired_caps"],
    },
    "platform-steward": {
        "title": "平台治理专家",
        "duty": "治理骨架升级与多 Agent 接入登记的规划与协调；只准备计划与交接卡，不替人批准。",
        "skills": ["ledger-upgrade", "agent-gate", "scenario-guard", "layout-inspect",
                   "board-layout", "scale-budget", "method-assets", "asset-install",
                   "test-map", "work-panel"],
        "writes": ["governance_meta", "access（均需人批准，由脚本执行）"],
    },
    "goal-orchestrator": {
        "title": "目标编排监督者",
        "duty": "在授权预算内围绕单一目标做受控自动循环：每轮重路由、强验证、方向检查、推进计数；"
                "超预算或偏移即停并提议，绝不自改目标。只读监督者。",
        "skills": ["goal-orchestrate", "expert-route", "expert-run", "ledger-scan",
                   "ledger-verify", "scenario-guard", "agent-gate", "work-panel"],
        "writes": [],
    },
}

INTENT_PATTERNS = {
    "new": ("新建", "新项目", "从零", "初始化", "立项", "白纸", "bootstrap",
            "scaffold", "init project", "create project", "greenfield"),
    "adopt": ("历史项目", "存量项目", "已有项目", "接手", "盘点", "梳理", "迁移",
              "接入", "考古", "发现能力", "brownfield", "legacy", "adopt", "discover"),
    "verify": ("校验", "验证", "检查", "门禁", "不变量", "假绿灯", "测试报告",
               "verify", "audit", "quality gate", "ci", "check"),
    "plan": ("决策", "规划", "任务卡", "下一步", "路线图", "裁决", "立项决策",
             "next_queue", "decide", "plan", "roadmap"),
    "code": ("编码", "实现", "开发", "修复", "修 bug", "补测试", "补单测",
             "implement", "code", "fix", "write test"),
    "lesson": ("经验", "复盘", "踩坑", "沉淀", "lesson", "retrospective"),
    "route": ("路由", "该找谁", "哪个专家", "专家路由", "expert route", "route"),
    "archive": ("归档", "冻结", "解冻", "发布窗口", "移交", "交付完成",
                "archive", "freeze", "unfreeze", "handover"),
    "migrate": ("跨版本", "版本升级", "schema", "账本升级", "升级治理骨架",
                "方法论升级", "工具副本", "回滚升级", "升级后流程",
                "专家升级", "技能升级", "资产摘要", "看板骨架", "版面差异",
                "规模预算", "项目太大", "资产安装", "专家可用", "技能可用",
                "工作台", "工作项", "TODO", "issue", "测试结果视图",
                "测试架构", "测试模块", "模块重组", "节点视图",
                "migrate", "migration", "upgrade", "rollback", "ledger_version",
                "method-assets", "board-contract", "scale-budget",
                "asset-bundle", "work-panel", "test-modules"),
    "access": ("接入 agent", "注册 agent", "多 agent", "agent 权限", "越权",
               "谁能改账本", "接入控制", "审计", "租约",
               "agent registry", "access control", "register agent"),
    "retire": ("退役", "下线能力", "废弃能力", "移除能力", "编码不复用",
               "retire", "deprecate"),
    "resume": ("中断", "续跑", "接着做", "断点", "恢复执行", "任务锁",
               "resume", "continue", "claim"),
    "goal": ("目标循环", "自动迭代", "迭代达成", "监督循环", "编排目标", "目标预算",
             "达成目标", "目标推进", "调整目标", "受控循环", "自动跑到达成",
             "goal loop", "goal orchestrat", "orchestrate goal", "auto iterate",
             "propose goal change", "target loop"),
    "doc": ("文档", "文檔", "文档化", "规范化", "规范化生成", "文档过期", "文档失效",
            "文档漂移", "文档复核", "文档重建", "文档索引", "文档覆盖", "文档状态",
            "文档信任", "文档生命周期", "文档义务", "孤儿文档", "过期标记", "待人工填写",
            "suspect", "stale", "doc lifecycle", "rebuild docs", "doc drift", "doc trust",
            "doc coverage", "doc registry", "mark stale", "clear suspect"),
}

FOLLOW_UP = {
    "verify": "evidence-auditor",
    "plan": "ledger-steward",
    "code": "loop-executor",
    "lesson": "ledger-steward",
    "adopt": "project-archaeologist",
    "new": "greenfield-architect",
    "archive": "release-steward",
    "migrate": "platform-steward",
    "access": "platform-steward",
    "retire": "release-steward",
    "resume": "loop-executor",
    "goal": "goal-orchestrator",
    "doc": "ledger-steward",
}

HANDOFF_CHAIN = {
    "expert-router": ["expert-router", "ledger-steward", "evidence-auditor"],
    "greenfield-architect": ["greenfield-architect", "ledger-steward",
                             "evidence-auditor"],
    "project-archaeologist": ["project-archaeologist", "greenfield-architect",
                              "ledger-steward"],
    "ledger-steward": ["ledger-steward", "loop-executor", "evidence-auditor"],
    "loop-executor": ["loop-executor", "evidence-auditor", "ledger-steward"],
    "evidence-auditor": ["evidence-auditor", "ledger-steward", "loop-executor"],
    "release-steward": ["release-steward", "evidence-auditor", "ledger-steward"],
    "platform-steward": ["platform-steward", "evidence-auditor", "loop-executor"],
    "goal-orchestrator": ["goal-orchestrator", "evidence-auditor", "ledger-steward"],
    # 文档任务链：doc 意图命中时的唯一交接顺序（写入→执行→只读审计）。
    "doc": ["ledger-steward", "loop-executor", "evidence-auditor"],
}

EXCLUDE_DIRS = {
    ".git", ".hg", ".svn", ".workbuddy", ".codegraph", ".gitnexus",
    "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", "logs", "artifacts",
}
SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".scala", ".sql",
}
DOC_EXTS = {".md", ".rst", ".adoc"}
CONFIG_NAMES = {
    "package.json", "pyproject.toml", "setup.py", "requirements.txt",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "makefile", "dockerfile",
}
TEST_RE = re.compile(r"(^|/)(tests?|specs?)/|(^|/)(test_[^/]+|[^/]+_test\.[^/]+|[^/]+\.(test|spec)\.[^/]+)$")


def _read_json(path: Path) -> tuple[str, dict]:
    if not path.exists():
        return "absent", {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "corrupt", {}
    if not isinstance(data, dict):
        return "corrupt", {}
    return "ok", data


def inspect(target: Path, max_files: int = 2000) -> dict:
    """只读扫描：返回项目状态事实，不写任何文件。"""
    gov = target / "governance"
    ledger_state, ledger = _read_json(gov / "DECISION_LEDGER.json")
    registry_state, registry = _read_json(gov / "registry.json")

    if ledger_state == "ok":
        has_entries = bool(ledger.get("entries"))
        has_model = bool(ledger.get("capability_model"))
        ledger_state = "active" if (has_entries or has_model) else "empty"

    counts = {"source": 0, "test": 0, "doc": 0, "config": 0,
              "scanned": 0, "truncated": False}
    for root, dirs, files in os.walk(target):
        dirs[:] = sorted(d for d in dirs
                         if d not in EXCLUDE_DIRS and not d.startswith(".gitnexus"))
        rel_root = Path(os.path.relpath(root, target))
        for name in sorted(files):
            if counts["scanned"] >= max_files:
                counts["truncated"] = True
                break
            counts["scanned"] += 1
            rel = (rel_root / name).as_posix().lstrip("./")
            low = name.lower()
            ext = Path(name).suffix.lower()
            if TEST_RE.search("/" + rel) or low.startswith("test_"):
                counts["test"] += 1
            elif ext in SOURCE_EXTS:
                counts["source"] += 1
            elif ext in DOC_EXTS:
                counts["doc"] += 1
            elif low in CONFIG_NAMES:
                counts["config"] += 1
        if counts["truncated"]:
            break

    has_git = (target / ".git").exists()
    has_report = (gov / "test_report.json").exists()
    has_board = resolve(gov).exists()
    registry_modules = len(registry.get("modules", [])) if registry_state == "ok" else 0

    if ledger_state == "corrupt":
        mode = "corrupt"
    elif ledger_state in ("active", "empty") and registry_state == "ok":
        mode = "governed"
    elif ledger_state != "absent" or registry_state == "ok":
        mode = "partial"
    elif counts["source"] or counts["test"] or counts["doc"] or counts["config"]:
        mode = "brownfield"
    else:
        mode = "greenfield"

    lifecycle_state = "active"
    if isinstance(ledger.get("lifecycle"), dict):
        candidate = str(ledger["lifecycle"].get("state", "active"))
        if candidate in ("frozen", "archived"):
            lifecycle_state = candidate
            mode = candidate  # 生命周期优先于目录结构：冻结/归档时不进入编码

    return {
        "mode": mode,
        "lifecycle": lifecycle_state,
        "ledger": ledger_state,
        "registry": registry_state,
        "registry_modules": registry_modules,
        "counts": counts,
        "has_git": has_git,
        "has_test_report": has_report,
        "has_board": has_board,
    }


def classify_intent(text: str) -> dict[str, int]:
    low = (text or "").lower()
    return {key: sum(1 for p in pats if p in low)
            for key, pats in INTENT_PATTERNS.items()}


def _intent_summary(scores: dict[str, int]) -> list[str]:
    return [f"{k}({v})" for k, v in sorted(scores.items(), key=lambda x: (-x[1], x[0])) if v]


def _card(expert: str, confidence: str, reason: str, facts: dict,
          next_expert: str | None = None, preconditions: list[str] | None = None,
          open_questions: list[str] | None = None, blocked: bool = False,
          stop_if: list[str] | None = None) -> dict:
    meta = EXPERT_CARDS[expert]
    return {
        "expert": expert,
        "title": meta["title"],
        "duty": meta["duty"],
        "confidence": confidence,
        "blocked": blocked,
        "reason": reason,
        "skills": list(meta["skills"]),
        "writes": list(meta["writes"]),
        "suggested_commands": [],
        "preconditions": preconditions or [],
        "handoff": {
            "facts": [
                f"项目状态={facts['mode']}",
                f"ledger={facts['ledger']} registry={facts['registry']}",
                "源码/测试/文档/配置="
                f"{facts['counts']['source']}/{facts['counts']['test']}/"
                f"{facts['counts']['doc']}/{facts['counts']['config']}",
            ],
            "artifacts": [],
            "open_questions": open_questions or [],
            "next_expert": next_expert,
            "stop_if": stop_if or [],
        },
    }


def decide(facts: dict, scores: dict[str, int], explicit_mode: str) -> dict:
    """返回 route 字典；不访问文件系统。"""
    active = _intent_summary(scores)
    top = max(scores.values())
    strong = [k for k, _ in sorted(scores.items(), key=lambda x: (-x[1], x[0]))
              if scores[k] == top and top > 0]
    primary = strong[0] if strong else None
    clarification = None
    if len(strong) > 1:
        clarification = {
            "question": "检测到多个竞争意图，请先确认本轮目标：" + "、".join(active),
            "options": strong,
        }

    # 文档意图冲突裁决：doc 是跨模式任务链，但写入方只能有一个。
    # doc+code → ledger-steward（文档义务裁决优先于代码执行，输出交接链）；
    # doc+verify → evidence-auditor（只读信任审计优先，不得写文档）；
    # 三者并存 → evidence-auditor + clarification（无唯一解，fail-closed）。
    doc_active = scores.get("doc", 0) > 0
    code_active = scores.get("code", 0) > 0
    verify_active = scores.get("verify", 0) > 0
    doc_route: str | None = None
    if doc_active and verify_active:
        primary = "verify"
        doc_route = "evidence-auditor"
        if not (doc_active and code_active and verify_active):
            clarification = None
    elif doc_active and code_active:
        primary = "doc"
        doc_route = "ledger-steward"
        clarification = None
    elif doc_active:
        primary = "doc"
        doc_route = "ledger-steward"

    mode = facts["mode"]
    follow_up = FOLLOW_UP.get(primary) if primary else None

    if mode == "corrupt":
        route = _card("evidence-auditor", "high",
                      "账本 JSON 无法解析；任何写入都可能污染单一事实源，先审计并修复。",
                      facts, blocked=True,
                      preconditions=["不要运行生成器", "先备份 DECISION_LEDGER.json 再人工修复"],
                      stop_if=["账本恢复为合法 JSON 且 verify 通过前，禁止任何写入"])
    elif mode in ("frozen", "archived"):
        route = _card("release-steward", "high",
                      f"账本生命周期为 {mode}；此状态下只允许只读取证与经批准的状态转换。",
                      facts, blocked=True,
                      preconditions=["先跑 scenario_guard.py 确认阻塞动作"],
                      stop_if=["归档是不可写终态", "解冻必须带 --approved-by（人工批准）"])
        clarification = clarification or {
            "question": "项目处于冻结/归档态，是否需要经批准解冻？",
            "options": ["保持只读", "经批准解冻", "复制出新项目"],
        }
    elif primary == "goal":
        # 目标编排是跨轮监督意图：不能由单条任务卡的 loop-executor 顺手做，
        # 必须由只读监督者在预算内驱动，创建/调整仍回到人批准。
        route = _card("goal-orchestrator", "high",
                      "本轮目标是围绕单一目标做受控自动循环：每轮重路由、强验证、"
                      "方向检查、预算计数；创建与调整目标必须人批准。", facts,
                      preconditions=["goal_loop.py 默认 dry-run，先看轨迹再批准推进",
                                     "goal-orchestrator 角色须由人 register"],
                      stop_if=["verify fail / 方向漂移 / next_queue 空：立即停",
                               "max_loops 用尽未达成：deactivated",
                               "未经 --approved-by 不得 goal-create / goal-approve"],
                      next_expert="evidence-auditor")
    elif primary in ("migrate", "access"):
        # 元层意图优先于项目状态：规则本身变了、或要授予写入权限时，
        # 不能由考古/执行专家顺手完成——批准门与版本七轴需要独立负责人。
        route = _card("platform-steward", "high",
                      "治理骨架升级 / 多 Agent 接入属于元层动作：先只读计划，"
                      "再由人批准应用与注册；完成后必须重新取证与复验。", facts,
                      preconditions=["upgrade.py plan --json 无 block",
                                     "准备人工批准人姓名（AI 不得代填）"],
                      stop_if=["无 --approved-by 不得 apply / rollback / register",
                               "post_upgrade 未跑完不得宣布升级完成"],
                      next_expert="evidence-auditor")
    elif primary == "route":
        # "该找谁"是编排层意图：由专家路由本人回答，不写账本/源码/看板。
        route = _card("expert-router", "high",
                      "本轮只问该找谁：由专家路由给出确定性与交接链，本身不写入。",
                      facts,
                      preconditions=["本结论只读；实际执行需按交接链切换负责人"])
    elif explicit_mode == "greenfield" and mode != "greenfield":
        route = _card("greenfield-architect", "medium",
                      "显式指定新建模式，但目标目录已存在治理或历史资产；需确认是否另起子项目。",
                      facts, open_questions=["是否在新子目录初始化，而不是覆盖现有内容？"],
                      stop_if=["确认前禁止写入现有 governance/"])
        clarification = clarification or {
            "question": "目标目录并非空项目，是否仍要按新建项目处理？",
            "options": ["在子目录新建", "改用存量项目接入", "取消"],
        }
    elif explicit_mode == "brownfield" and mode != "brownfield":
        route = _card("project-archaeologist", "medium",
                      "显式指定存量模式；先只读盘点，事实会决定是否能安全接入。",
                      facts, stop_if=["盘点报告未经确认前禁止覆盖治理文件"])
    elif mode == "governed":
        if doc_route == "evidence-auditor":
            route = _card("evidence-auditor", "high",
                          "文档信任审计优先：只读核对 verified/generated/source_hash/"
                          "stale_after；不得写文档、不得关闭 issue。", facts,
                          preconditions=["doc-lifecycle check --json 只读报告"],
                          stop_if=["不得写 docs/**", "不得关闭任何 issue"])
        elif doc_route == "ledger-steward":
            route = _card("ledger-steward", "high",
                          "文档生命周期任务：裁决 docs.registry、stale/suspect 与 "
                          "declared_no_impact；唯一写入方，按文档任务链交接。", facts,
                          preconditions=["先跑 doc-lifecycle lint 得到结构报告"],
                          stop_if=["骨架不得标 compliant", "declared_no_impact 须人确认"],
                          next_expert="loop-executor")
        elif primary == "verify":
            route = _card("evidence-auditor", "high",
                          "已有可信治理骨架，本轮目标为证据与不变量校验。", facts)
        elif primary == "code":
            route = _card("loop-executor", "high",
                          "已有可消费的 next_queue，进入一条任务卡的证据补齐循环。", facts,
                          preconditions=["先跑 ledger-guard，确认账本没坏"],
                          stop_if=["verify 失败", "任务卡证据路径不存在"],
                          next_expert="evidence-auditor")
        elif primary in ("archive", "retire"):
            route = _card("release-steward", "high",
                          "生命周期变更需要人工批准与状态留痕；不得由编码代理顺手完成。", facts,
                          preconditions=["先跑 scenario_guard.py 确认无阻塞"],
                          stop_if=["unfreeze / archive 缺少 --approved-by"],
                          next_expert="evidence-auditor")
        elif primary == "resume":
            route = _card("loop-executor", "high",
                          "断点续跑先检查任务锁，避免两个执行者写同一份事实源。", facts,
                          preconditions=["scenario_guard.py --json 查看是否有陈旧 claim"],
                          next_expert="evidence-auditor")
        elif primary in ("new", "adopt"):
            route = _card("ledger-steward", "low",
                          "目标已接入治理，新建/接入语义与现状冲突；先由账本确认范围。",
                          facts, open_questions=["是否要在独立子目录新建项目？"],
                          stop_if=["范围裁决前不得覆盖现有账本"])
        else:
            route = _card("ledger-steward", "high" if not primary else "medium",
                          "治理骨架已就绪，默认进入 SCAN→SELECT→PLAN 循环。", facts,
                          next_expert=follow_up)
    elif mode == "brownfield":
        if primary == "new":
            route = _card("greenfield-architect", "medium",
                          "检测到新建意图，但目录已有历史资产；需确认边界。",
                          facts, open_questions=["是否保留现有代码并作为存量项目接入？"],
                          stop_if=["确认前禁止写入现有 governance/"])
            clarification = clarification or {
                "question": "目录已有历史代码，新建项目还是先做存量接入？",
                "options": ["存量接入", "在子目录新建", "取消"],
            }
        else:
            route = _card("project-archaeologist", "high",
                          "发现历史资产但缺少可信账本；先只读发现，再无损接入。", facts,
                          next_expert=follow_up or "greenfield-architect",
                          preconditions=["dry-run 盘点结果需人工确认"],
                          stop_if=["发现报告未经确认前不得覆盖任何既有文件"])
    elif mode == "partial":
        if facts["ledger"] in ("active", "empty"):
            route = _card("ledger-steward", "medium",
                          "账本存在但 registry 缺失或不完整；先补齐唯一手写清单。",
                          facts, preconditions=["保留既有账本，不重建 history"],
                          stop_if=["registry 未补齐前不得声称完成度"])
        else:
            route = _card("project-archaeologist", "medium",
                          "registry 存在但账本缺失；先盘点并与现有 registry 对照。",
                          facts, preconditions=["不得覆盖既有 registry.json"],
                          stop_if=["对照完成前不得生成正式账本"])
    else:
        if primary in ("adopt", "verify", "code", "plan", "lesson"):
            route = _card("greenfield-architect", "medium",
                          "目录为空，没有可盘点或可校验的历史资产；先建立最小治理骨架。",
                          facts, open_questions=[f"意图「{primary}」指向哪个项目路径？"],
                          stop_if=["路径确认前禁止写入"])
        else:
            route = _card("greenfield-architect", "high" if not primary else "medium",
                          "空目录且无冲突信号，从最小 registry 开始新建项目。", facts,
                          next_expert="ledger-steward")

    alternatives = [
        {"expert": name, "why_not": card["duty"]}
        for name, card in EXPERT_CARDS.items()
        if name != route["expert"] and name != "expert-router"
    ][:3]
    route["alternatives"] = alternatives
    doc_hit = any(i.startswith("doc(") for i in active)
    chain_key = "doc" if doc_hit and route["expert"] == "ledger-steward" else route["expert"]
    chain = list(HANDOFF_CHAIN.get(chain_key, [route["expert"]]))
    if doc_hit and route["expert"] == "evidence-auditor":
        chain = ["evidence-auditor", "ledger-steward", "loop-executor"]
    nxt = route["handoff"].get("next_expert")
    if nxt and nxt in EXPERT_CARDS and nxt not in chain:
        chain.insert(1, nxt)
    route["handoff"]["chain"] = chain
    return {"route": route, "clarification": clarification, "intents": active}


def commands_for(expert: str, target_display: str) -> list[str]:
    t = target_display
    return {
        "expert-router": [
            # P0 让 route 意图归位到本人；补齐专属只读命令，避免落到默认 --help。
            f"python3 scripts/route_expert.py --target {t} --check-assets --json",
            f"python3 scripts/route_expert.py --target {t} --intent \"<本轮意图>\" --json",
            f"python3 scripts/expert_run.py --target {t} --intent \"<本轮意图>\" --json",
        ],
        "greenfield-architect": [
            f"python3 scripts/init_project.py --target {t} --code YOURCODE --name \"项目名\"",
            f"cd {t} && python3 governance/build_capability_model.py --root . --dry-run",
            f"python3 scripts/rebuild_docs.py --target {t}",
            f"python3 scripts/file_layout.py --diff --target {t}",
        ],
        "project-archaeologist": [
            f"python3 scripts/discover_project.py --target {t} --dry-run",
            f"python3 scripts/discover_project.py --target {t}",
            f"python3 scripts/init_project.py --target {t} --mode adopt --from-draft {t}/governance/registry.draft.json --code YOURCODE",
            f"python3 scripts/architect_from_docs.py --target {t}",
            f"python3 scripts/compare_graphs.py --target {t}",
            f"python3 scripts/file_layout.py --diff --target {t}",
        ],
        "ledger-steward": [
            f"cd {t} && python3 governance/build_capability_model.py --root . --dry-run",
            f"cd {t} && python3 governance/verify_ledger.py --root . --strict",
            f"python3 scripts/compare_graphs.py --target {t}",
        ],
        "evidence-auditor": [
            "bash scripts/check.sh",
            f"cd {t} && python3 governance/verify_ledger.py --root . --strict --json",
            f"python3 scripts/trace_git.py --target {t} --max-count 50",
            f"python3 scripts/file_layout.py --diff --target {t} --strict",
        ],
        "loop-executor": [
            f"cd {t} && python3 -c \"import json;d=json.load(open('governance/DECISION_LEDGER.json'));print(d['capability_model']['next_queue'][0])\"",
            "bash scripts/check.sh",
            f"python3 scripts/code_index.py --target {t}",
        ],
        "release-steward": [
            f"python3 scripts/scenario_guard.py --target {t} --json",
            f"python3 scripts/lifecycle.py --target {t} status",
            f"python3 scripts/lifecycle.py --target {t} unfreeze --approved-by 审批人姓名",
            f"python3 scripts/file_layout.py --diff --target {t} --strict",
        ],
        "platform-steward": [
            f"python3 scripts/upgrade.py --target {t} plan --json",
            f"python3 scripts/upgrade.py --target {t} apply --approved-by 审批人姓名",
            f"python3 scripts/upgrade.py --target {t} verify --json",
            f"python3 scripts/agent_gateway.py --target {t} status --json",
            f"python3 scripts/agent_gateway.py --target {t} register --agent ci-agent --role loop-executor --approved-by 审批人姓名 --apply",
            f"python3 scripts/file_layout.py --diff --target {t} --strict",
            f"python3 scripts/method_assets.py --check",
            f"python3 scripts/board_contract.py --target {t} check --json",
            f"python3 scripts/scale_budget.py --target {t} --json --check",
            f"python3 scripts/asset_bundle.py --check",
            f"python3 scripts/asset_bundle.py verify --target {t} --json",
            f"python3 scripts/work_panel.py --target {t} check --json",
            f"python3 scripts/work_panel.py --target {t} nodes --json",
            f"python3 scripts/test_modules.py --check",
            f"python3 scripts/route_expert.py --target {t} --check-assets --json",
        ],
        "goal-orchestrator": [
            f"python3 scripts/goal_loop.py --target {t} --goal-id G-001 --json",
            f"python3 scripts/goal_loop.py --target {t} --goal-id G-001 --emit-apply",
            f"python3 scripts/agent_gateway.py --target {t} status --json",
            f"cd {t} && python3 governance/verify_ledger.py --root . --strict --json",
        ],
    }.get(expert, ["python3 scripts/route_expert.py --help"])


def build(target: Path, intent: str, explicit_mode: str,
          target_display: str, max_files: int = 2000,
          assets_root: Path | None = None,
          restate_file: Path | str | None = None) -> dict:
    facts = inspect(target, max_files=max_files)
    scores = classify_intent(intent)
    decision = decide(facts, scores, explicit_mode)
    route = decision["route"]
    # 未识别的非空指令不得静默高置信路由：抛回人复述，并诚实降置信度。
    # 空意图是合法的"按现状给默认路由"调用，保持兼容。
    if intent.strip() and not decision["intents"] \
            and decision["clarification"] is None:
        decision["clarification"] = {
            "question": "未识别本轮意图（" + intent.strip()[:80] +
                        "）：请用 --intent-file 提交 intent.json 结构化复述，"
                        "或直接说明目标。",
            "options": ["提交 intent.json", "改用明确意图", "按现状默认路由"],
        }
        route["confidence"] = "low"
    route["suggested_commands"] = commands_for(route["expert"], target_display)
    root = asset_root(target, assets_root)
    assets = load_assets(root, installed_manifest_paths(root))
    route["asset_binding"] = {
        "root_kind": assets["root_kind"], "digest": assets["digest"][:16],
        "status": assets["status"], "expert_count": assets["expert_count"],
        "skill_count": assets["skill_count"], "scoped": assets["scoped"],
    }
    if assets["status"] != "ok":
        route["preconditions"] = list(route.get("preconditions", [])) + [
            "专家/技能资产不完整：先跑 asset_bundle.py install --apply --approved-by <人>"]

    clarification = decision["clarification"]
    restate_result = None
    if restate_file is not None:
        # 复述门前置：意图未被结构化确认前，不让模糊意图静默进入路由。
        # 延迟 import 保持独立工具可单跑；默认 None 时完全兼容既有调用。
        try:
            import intent_restate
        except ImportError:  # pragma: no cover - 与 route_expert 同目录时必可导入
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import intent_restate
        restate_result = intent_restate.gate(target, Path(restate_file))
        if restate_result["verdict"] != "allow":
            fixes = [c.get("fix") for c in restate_result["checks"]
                     if c.get("fix")]
            question = "复述门未放行（" + restate_result["verdict"] + "）：" + "；".join(fixes)
            if clarification is None:
                clarification = {"question": question, "options": []}
            else:
                clarification = dict(clarification)
                clarification["question"] = clarification["question"] + "；" + question
            route["blocked"] = True
            route["preconditions"] = list(route.get("preconditions", [])) + [
                "复述门未放行：补齐 intent.json 后重新路由"]

    result = {
        "schema": SCHEMA,
        "target": target_display,
        "mode": explicit_mode if explicit_mode != "auto" else facts["mode"],
        "detected_mode": facts["mode"],
        "facts": facts,
        "intents": decision["intents"],
        "needs_clarification": clarification,
        "route": route,
        "assets": {k: v for k, v in assets.items()
                   if k not in ("experts", "skills")},
    }
    if restate_result is not None:
        result["restate_gate"] = restate_result
    return result


def render(result: dict) -> str:
    r = result["route"]
    f = result["facts"]
    lines = []
    if result.get("restate_gate") is not None:
        g = result["restate_gate"]
        lines.append(f"复述门：{g['verdict']}（{len(g['checks'])} 项校验）")
    lines.extend([
        f"路由 → {r['expert']}（{r['title']}，置信度 {r['confidence']}）",
        f"项目状态：{result['detected_mode']} | ledger={f['ledger']} | "
        f"registry={f['registry']} | 源码/测试/文档="
        f"{f['counts']['source']}/{f['counts']['test']}/{f['counts']['doc']}",
        f"理由：{r['reason']}",
    ])
    if r["preconditions"]:
        lines.append("前置条件：" + "；".join(r["preconditions"]))
    if r["handoff"]["open_questions"]:
        lines.append("待澄清：" + "；".join(r["handoff"]["open_questions"]))
    if result["needs_clarification"]:
        q = result["needs_clarification"]
        lines.append("需要你确认：" + q["question"] + " [" + "/".join(q["options"]) + "]")
    lines.append("建议下一步：")
    lines.extend(f"  {c}" for c in r["suggested_commands"])
    if r["handoff"]["next_expert"]:
        lines.append(f"交接给：{r['handoff']['next_expert']}")
    if r["handoff"].get("chain"):
        lines.append("交接链：" + " → ".join(r["handoff"]["chain"]))
    if r["blocked"]:
        lines.append("已冻结：修复阻塞项前不要继续写入。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="目标项目根目录（默认当前目录）")
    ap.add_argument("--intent", default="", help="本轮任务意图的自然语言描述")
    ap.add_argument("--intent-file", default="", help="复述门 intent.json 路径；提供时先跑复述门，未放行则阻断路由")
    ap.add_argument("--mode", choices=("auto", "greenfield", "brownfield"),
                    default="auto", help="显式指定项目模式；与事实冲突时会要求澄清")
    ap.add_argument("--max-files", type=int, default=2000, help="只读扫描的文件数上限")
    ap.add_argument("--assets-root", default="", help="专家/技能资产根（默认优先项目内已安装副本）")
    ap.add_argument("--check-assets", action="store_true", help="只校验资产齐备性与 frontmatter，不路由")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"目标目录不存在：{args.target}", file=sys.stderr)
        return 2
    if args.check_assets:
        root = asset_root(target, Path(args.assets_root) if args.assets_root else None)
        result = check_assets(root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
              if args.json else
              f"资产自检：{'通过' if result['ok'] else '失败'} · "
              f"{result['expert_count']} 专家 / {result['skill_count']} 技能 · "
              f"摘要 {result['digest'][:12]}" +
              ("\n" + "\n".join(result["errors"]) if result["errors"] else ""))
        return 0 if result["ok"] else 1
    result = build(target, args.intent, args.mode, args.target, args.max_files,
                   Path(args.assets_root) if args.assets_root else None,
                   Path(args.intent_file) if args.intent_file else None)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
