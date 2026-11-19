#!/usr/bin/env python3
"""规模预算：把「项目变大之后会先坏在哪里」变成只读、可门禁的数字。

第一性原理
----------
治理层**文件数是固定的**：registry / 账本 / 看板 / 6 个工具副本 / 少量
派生报告，不会因为模块多就每模块生成一个文件（见 file_layout.py）。
所以「需生成的文件数量大」不是本方法的主要风险，真正的增长维度是：

  1. 单文件体积：账本（capability_model + history.events 全量状态快照）
     与看板 EMBED（同一份账本再内联一次）；
  2. 线性增长的结构：entries / history.events / caps / 测试报告 inputs；
  3. 浏览器 DOM：一次 innerHTML 渲染全部卡片；
  4. CPU：生成器按能力逐个扫 docs / tests 目录，接近 O(能力 × 项目文件)。

本脚本不拆账本、不删历史、不新建平行报告（A3 单一事实源）。它只报预算：
超阈值时给出可执行的降级路径，由人决定拆项目还是归档重开。

纪律：全程只读；不写报告文件；路径不泄露机器绝对路径。
输出 schema: scale-budget/1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "scale-budget/1"
TEMPLATE_REL = "templates/index.html.template"
PAGE_RE = re.compile(r"const PAGE_SIZE\s*=\s*(\d+)")
EXCLUDED_PARTS = {".git", "__pycache__", "node_modules", ".venv"}

# 单一事实源：阈值只在这里定义；看板分批上限从模板解析，避免两边漂移。
BUDGETS: list[dict] = [
    dict(id="ledger_bytes", label="账本体积", warn=5 * 1024**2, hard=20 * 1024**2, unit="bytes",
         advice="归档旧项目后复制新项目，不要拆账本；历史事件是 append-only"),
    dict(id="board_bytes", label="看板体积（含内联账本）", warn=5 * 1024**2, hard=20 * 1024**2,
         unit="bytes", advice="离线可看需内联一份账本；体积过大时按项目拆分"),
    dict(id="entries", label="决策条目", warn=2000, hard=10000, unit="条",
         advice="看板按 PAGE_SIZE 分批渲染；决策过密说明应先归档阶段"),
    dict(id="history_events", label="历史事件", warn=500, hard=2000, unit="条",
         advice="每个事件含全量 state_digest；不可删除，只能冻结/归档后开新账本"),
    dict(id="capabilities", label="能力点", warn=2000, hard=10000, unit="个",
         advice="生成器按能力扫文件，接近 O(能力 × 项目文件)；拆分 registry 到独立项目（E7）"),
    dict(id="test_inputs", label="测试报告绑定文件", warn=1000, hard=5000, unit="个",
         advice="绑定摘要逐文件 sha256；按子项目分组跑报告，勿合并成巨型测试目录"),
    dict(id="governance_files", label="治理层文件数", warn=40, hard=80, unit="个",
         advice="正常应为固定集合；超了先查是否出现第二事实源"),
    dict(id="project_files", label="项目文件总数", warn=20000, hard=100000, unit="个",
         advice="全量重算的成本随文件数上升；超过阈值请分仓或分项目"),
    dict(id="render_cards", label="单视图最大卡片数", warn=200, hard=2000, unit="个",
         advice="模板按 PAGE_SIZE 分批；超过硬阈值应拆项目而不是继续加页"),
    dict(id="work_items", label="节点工作项（TODO / issue）", warn=500, hard=2000, unit="条",
         advice="工作台与工作项视图按 PAGE_SIZE 分批；关闭已完成的，不要删历史工作项"),
]


def render_limit(source_root: Path = ROOT) -> int:
    """从权威模板读取分批上限，保证预算与渲染实现不漂移。"""
    p = Path(source_root) / TEMPLATE_REL
    if not p.is_file():
        raise ValueError(f"模板不存在：{TEMPLATE_REL}")
    m = PAGE_RE.search(p.read_text(encoding="utf-8"))
    if not m:
        raise ValueError("模板缺少 const PAGE_SIZE = <n>，无法核对渲染预算")
    return int(m.group(1))


def _size(p: Path) -> int:
    return p.stat().st_size if p.is_file() else 0


def _count_files(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for p in root.rglob("*")
               if p.is_file() and not set(p.parts) & EXCLUDED_PARTS)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def report(target: Path, source_root: Path = ROOT) -> dict:
    """只读统计；任何缺失都按 0 处理，不猜测、不写盘。"""
    target = Path(target)
    gov = target / "governance"
    ledger = read_json(gov / "DECISION_LEDGER.json")
    registry = read_json(gov / "registry.json")
    test_report = read_json(gov / "test_report.json")
    cm = ledger.get("capability_model") if isinstance(ledger.get("capability_model"), dict) else {}
    hist = ledger.get("history") if isinstance(ledger.get("history"), dict) else {}
    events = hist.get("events") if isinstance(hist.get("events"), list) else []
    entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
    mods = registry.get("modules") if isinstance(registry.get("modules"), list) else []
    caps = sum(len(m.get("caps", [])) if isinstance(m.get("caps"), list) else 0 for m in mods)
    summary = cm.get("summary") if isinstance(cm.get("summary"), dict) else {}
    caps = int(summary.get("capabilities") or caps)
    inputs = (test_report.get("evidence_binding") or {}).get("inputs")
    n_inputs = len(inputs) if isinstance(inputs, list) else 0
    last_state = (events[-1].get("state_digest") or {}) if events and isinstance(events[-1], dict) else {}
    derived = [p for p in gov.glob("*.json") if p.name != "DECISION_LEDGER.json"]
    derived += list((target / "docs" / "generated").glob("*")) if (target / "docs" / "generated").is_dir() else []
    page = render_limit(source_root)
    metrics = {
        "ledger_bytes": _size(gov / "DECISION_LEDGER.json"),
        "board_bytes": _size(gov / "index.html"),
        "entries": len(entries),
        "history_events": len(events),
        "capabilities": caps,
        "test_inputs": n_inputs,
        "governance_files": len([p for p in gov.rglob("*") if p.is_file()]),
        "project_files": _count_files(target),
        "render_cards": max(len(entries), len(events), caps),
        "work_items": len(ledger.get("work_items") or []),
        "state_digest_codes": len(last_state) if isinstance(last_state, dict) else 0,
        "derived_files": len(derived),
        "largest_derived_bytes": max((_size(p) for p in derived), default=0),
        "render_page_size": page,
    }
    rows: list[dict] = []
    for b in BUDGETS:
        value = int(metrics[b["id"]])
        state = "exceed" if value > b["hard"] else "warn" if value > b["warn"] else "ok"
        rows.append({**b, "value": value, "status": state})
    status = ("exceed" if any(r["status"] == "exceed" for r in rows) else
              "warn" if any(r["status"] == "warn" for r in rows) else "ok")
    return {
        "schema": SCHEMA,
        "target": ".",
        "status": status,
        "metrics": metrics,
        "budgets": rows,
        "fixed_layout": {
            "note": "治理层文件数固定：模块/能力增长不会按比例新增治理文件",
            "growth": ["账本体积", "看板内联体积", "entries / events / caps", "浏览器 DOM", "生成器全量重算耗时"],
        },
        "advice": [r["advice"] for r in rows if r["status"] != "ok"],
        "limits": [
            "不拆账本、不删 history.events：append-only 是历史可信的前提",
            "超硬阈值时按项目拆分（workspace / monorepo 联合门禁仍是 E7 缺口）",
            "生成器每次全量重算，未做增量索引；大项目建议降频并分组跑门禁",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="目标项目根")
    ap.add_argument("--json", action="store_true", help="输出完整 JSON")
    ap.add_argument("--check", action="store_true", help="超硬阈值时退出码 2（供 CI）")
    ap.add_argument("--strict", action="store_true", help="--check 时 warn 也算失败")
    args = ap.parse_args(argv)
    try:
        r = report(Path(args.target))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"规模预算：{r['status']} · 账本 {r['metrics']['ledger_bytes']/1024:.1f} KiB · "
              f"看板 {r['metrics']['board_bytes']/1024:.1f} KiB · "
              f"{r['metrics']['capabilities']} 能力 / {r['metrics']['entries']} 决策 / "
              f"{r['metrics']['history_events']} 事件 · 治理文件 {r['metrics']['governance_files']} · "
              f"分批上限 {r['metrics']['render_page_size']}")
        for row in r["budgets"]:
            if row["status"] != "ok":
                print(f"  [{row['status']}] {row['label']} = {row['value']}{row['unit']} "
                      f"(warn {row['warn']} / hard {row['hard']})：{row['advice']}")
    if args.check:
        if r["status"] == "exceed" or (args.strict and r["status"] == "warn"):
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
