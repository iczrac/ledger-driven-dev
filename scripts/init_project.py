#!/usr/bin/env python3
"""从模板初始化一个新项目的治理骨架。

用法：
    python3 scripts/init_project.py --target /path/to/your-project --code MYPROJ --name "我的项目"

会创建：
    <target>/governance/registry.json         能力注册表（按 --code/--name 填好，需编辑模块清单）
    <target>/governance/DECISION_LEDGER.json  空账本骨架
    <target>/governance/index.html            可视化看板
    <target>/governance/build_capability_model.py  生成器副本（可选 --no-generator 跳过）

不会覆盖已存在文件（除非 --force）。
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="目标项目根目录")
    ap.add_argument("--code", required=True, help="项目代码（大写短码，如 MYPROJ）")
    ap.add_argument("--name", help="项目展示名（默认同 code）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件")
    ap.add_argument("--no-generator", action="store_true", help="不复制生成器")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    gov = target / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    name = args.name or args.code

    files: list[tuple[Path, str]] = []

    # registry.json —— 从模板派生并填入 project 信息
    reg = json.loads((TEMPLATES / "registry.example.json").read_text())
    reg["project"]["code"] = args.code.upper()
    reg["project"]["name"] = name
    reg["project"]["root"] = "."
    files.append((gov / "registry.json", json.dumps(reg, ensure_ascii=False, indent=2)))

    # 空账本
    ledger = {
        "ledger_version": "1.0",
        "title": f"{name} 决策与能力账本",
        "purpose": "单一事实源：决策、裁决、待办及能力索引的唯一写入点。",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M HKT"),
        "owner": "待定",
        "workflow": [
            "所有重大决策/裁决/待办只写入本文件 entries，不再新建独立报告。",
            "新增条目分配稳定 id，状态初始 proposed/decided，填齐字段。",
            "旧决策被取代时设 superseded/supersedes，用取代链表达演进。",
            "能力等级与完成度由 build_capability_model.py 从证据重算，禁止手填。",
        ],
        "fields": {
            "id": "稳定标识，永不复用",
            "status": "proposed | decided | done | superseded | deferred",
            "evidence": "证据/文档路径",
            "confidence": "high | medium | low",
        },
        "entries": [],
        "history": {"spec": {}, "events": []},
        "lessons": {"spec": {}, "items": [], "candidates": []},
        "module_map": {"modules": [], "pages_path": "artifacts/control_center/pages/"},
        "architecture": {"projects": []},
    }
    files.append((gov / "DECISION_LEDGER.json", json.dumps(ledger, ensure_ascii=False, indent=2)))

    # 看板模板
    files.append((gov / "index.html", (TEMPLATES / "index.html.template").read_text()))

    for path, content in files:
        if path.exists() and not args.force:
            print(f"跳过（已存在）: {path}")
            continue
        path.write_text(content)
        print(f"写入: {path}")

    if not args.no_generator:
        for name in ("build_capability_model.py", "verify_ledger.py"):
            gen = gov / name
            if gen.exists() and not args.force:
                print(f"跳过（已存在）: {gen}")
            else:
                shutil.copy(TEMPLATES / name, gen)
                print(f"写入: {gen}")
        # 证据分层：测试报告生成器（从模板项目的 scripts/ 复制到新项目的 governance/）
        runner = gov / "run_tests.py"
        if runner.exists() and not args.force:
            print(f"跳过（已存在）: {runner}")
        else:
            shutil.copy(HERE / "run_tests.py", runner)
            print(f"写入: {runner}")

    print(f"\n完成。下一步：")
    print(f"  1. 编辑 {gov / 'registry.json'} 的 modules 清单")
    print(f"  2. cd {target} && python3 governance/build_capability_model.py --root . --dry-run")
    print(f"  3. 确认无误后去掉 --dry-run 正式生成")
    print(f"  4. python3 governance/verify_ledger.py --root . --strict  # 校验账本自洽")
    print(f"  5.（可选）升级证据为 verified —— 从本项目根运行：")
    print(f"     python3 governance/run_tests.py --dir tests --out governance/test_report.json")
    print(f"     python3 governance/build_capability_model.py --root . --test-report governance/test_report.json")
    print(f"  6. 浏览器打开 {gov / 'index.html'} 查看看板（徽章显示声明/实测）")


if __name__ == "__main__":
    main()
