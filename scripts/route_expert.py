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
import json
import os
import re
import sys
from pathlib import Path

SCHEMA = "expert-route/1"

EXPERT_CARDS = {
    "expert-router": {
        "title": "专家路由",
        "duty": "识别状态与意图，选唯一负责人；冲突时要求澄清。",
        "skills": ["expert-route"],
        "writes": [],
    },
    "greenfield-architect": {
        "title": "新建项目架构师",
        "duty": "从最小意图生成项目治理骨架，只声明必要能力，不替人排业务优先级。",
        "skills": ["project-bootstrap", "ledger-scan", "ledger-verify"],
        "writes": ["governance/registry.json", "governance/DECISION_LEDGER.json"],
    },
    "project-archaeologist": {
        "title": "存量项目考古专家",
        "duty": "只读盘点历史项目，产出 registry 草稿与接入报告，绝不覆盖既有治理文件。",
        "skills": ["project-discover", "ledger-scan", "ledger-verify"],
        "writes": ["governance/registry.draft.json", "governance/ADOPTION_REPORT.md"],
    },
    "ledger-steward": {
        "title": "账本治理专家",
        "duty": "维护决策取代链、确认经验、从 next_queue 产出可执行任务卡。",
        "skills": ["ledger-scan", "ledger-verify", "ledger-decide", "ledger-lesson"],
        "writes": ["entries", "lessons.items"],
    },
    "evidence-auditor": {
        "title": "证据审计专家",
        "duty": "跑不变量与实测报告，识别假绿灯；失败时冻结后续写入。",
        "skills": ["ledger-guard", "ledger-verify"],
        "writes": [],
    },
    "loop-executor": {
        "title": "循环执行专家",
        "duty": "从一条任务卡补齐契约/实现/单测/测试记录；不得改等级、历史或看板。",
        "skills": ["ledger-scan", "ledger-verify"],
        "writes": ["src/**", "tests/**", "docs/test_records/**"],
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
}

FOLLOW_UP = {
    "verify": "evidence-auditor",
    "plan": "ledger-steward",
    "code": "loop-executor",
    "lesson": "ledger-steward",
    "adopt": "project-archaeologist",
    "new": "greenfield-architect",
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
    has_board = (gov / "index.html").exists()
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

    return {
        "mode": mode,
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
              if k != "route" and scores[k] == top and top > 0]
    primary = strong[0] if strong else None
    clarification = None
    if len(strong) > 1:
        clarification = {
            "question": "检测到多个竞争意图，请先确认本轮目标：" + "、".join(active),
            "options": strong,
        }

    mode = facts["mode"]
    follow_up = FOLLOW_UP.get(primary) if primary else None

    if mode == "corrupt":
        route = _card("evidence-auditor", "high",
                      "账本 JSON 无法解析；任何写入都可能污染单一事实源，先审计并修复。",
                      facts, blocked=True,
                      preconditions=["不要运行生成器", "先备份 DECISION_LEDGER.json 再人工修复"],
                      stop_if=["账本恢复为合法 JSON 且 verify 通过前，禁止任何写入"])
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
        if primary == "verify":
            route = _card("evidence-auditor", "high",
                          "已有可信治理骨架，本轮目标为证据与不变量校验。", facts)
        elif primary == "code":
            route = _card("loop-executor", "high",
                          "已有可消费的 next_queue，进入一条任务卡的证据补齐循环。", facts,
                          preconditions=["先跑 ledger-guard，确认账本没坏"],
                          stop_if=["verify 失败", "任务卡证据路径不存在"],
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
    return {"route": route, "clarification": clarification, "intents": active}


def commands_for(expert: str, target_display: str) -> list[str]:
    t = target_display
    return {
        "greenfield-architect": [
            f"python3 scripts/init_project.py --target {t} --code YOURCODE --name \"项目名\"",
            f"cd {t} && python3 governance/build_capability_model.py --root . --dry-run",
        ],
        "project-archaeologist": [
            f"python3 scripts/discover_project.py --target {t} --dry-run",
            f"python3 scripts/discover_project.py --target {t}",
            f"python3 scripts/init_project.py --target {t} --mode adopt --from-draft {t}/governance/registry.draft.json --code YOURCODE",
        ],
        "ledger-steward": [
            f"cd {t} && python3 governance/build_capability_model.py --root . --dry-run",
            f"cd {t} && python3 governance/verify_ledger.py --root . --strict",
        ],
        "evidence-auditor": [
            "bash scripts/check.sh",
            f"cd {t} && python3 governance/verify_ledger.py --root . --strict --json",
        ],
        "loop-executor": [
            f"cd {t} && python3 -c \"import json;d=json.load(open('governance/DECISION_LEDGER.json'));print(d['capability_model']['next_queue'][0])\"",
            "bash scripts/check.sh",
        ],
    }.get(expert, ["python3 scripts/route_expert.py --help"])


def build(target: Path, intent: str, explicit_mode: str,
          target_display: str, max_files: int = 2000) -> dict:
    facts = inspect(target, max_files=max_files)
    scores = classify_intent(intent)
    decision = decide(facts, scores, explicit_mode)
    route = decision["route"]
    route["suggested_commands"] = commands_for(route["expert"], target_display)
    return {
        "schema": SCHEMA,
        "target": target_display,
        "mode": explicit_mode if explicit_mode != "auto" else facts["mode"],
        "detected_mode": facts["mode"],
        "facts": facts,
        "intents": decision["intents"],
        "needs_clarification": decision["clarification"],
        "route": route,
    }


def render(result: dict) -> str:
    r = result["route"]
    f = result["facts"]
    lines = [
        f"路由 → {r['expert']}（{r['title']}，置信度 {r['confidence']}）",
        f"项目状态：{result['detected_mode']} | ledger={f['ledger']} | "
        f"registry={f['registry']} | 源码/测试/文档="
        f"{f['counts']['source']}/{f['counts']['test']}/{f['counts']['doc']}",
        f"理由：{r['reason']}",
    ]
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
    if r["blocked"]:
        lines.append("已冻结：修复阻塞项前不要继续写入。")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="目标项目根目录（默认当前目录）")
    ap.add_argument("--intent", default="", help="本轮任务意图的自然语言描述")
    ap.add_argument("--mode", choices=("auto", "greenfield", "brownfield"),
                    default="auto", help="显式指定项目模式；与事实冲突时会要求澄清")
    ap.add_argument("--max-files", type=int, default=2000, help="只读扫描的文件数上限")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"目标目录不存在：{args.target}", file=sys.stderr)
        return 2
    result = build(target, args.intent, args.mode, args.target, args.max_files)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
