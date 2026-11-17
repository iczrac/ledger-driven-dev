#!/usr/bin/env python3
"""方法论资产清单：把「专家 / 技能 / 模板 / 文档」纳入可校验的版本绑定。

第一性原理
----------
`upgrade.py` 原本只把 3 个 `governance/*.py` 工具副本和 method_version 写进
目标账本。可是驱动开发的不只是工具副本：专家卡定义权限与停止条件，技能定义
动作接口，路由卡给出命令，模板决定看板版面，文档定义纪律。它们一起构成
「判定规则」。若目标项目仍由 v1.0 的专家卡指挥，却拿着 v1.1 的工具副本，
`verify` 会全部通过——因为没有任何字段记录过这批资产。

这些资产**不复制进目标项目**（见 file_layout.py 的 NOT_IN_TARGET）：它们属于
方法论仓库，随 git tag 升级。本脚本只做一件事：把整包资产压成一个确定性
sha256，由 `upgrade.py` 写进账本内 `governance_meta.method_assets`。之后
  - 任何专家 / 技能 / 模板 / 文档变动 → digest 变 → plan 要求重新批准升级；
  - 用旧资产指挥新骨架 → verify 的 method_assets 项 warn，upgrade_complete=false。

纪律
----
1. 只读、无时间戳、无绝对路径；相对路径排序后聚合，跨平台一致；
2. 派生生成物（docs/generated/*、*.json 报告）不纳入，避免每次生成都变；
3. 这不是第二事实源：清单本身不落盘成项目文件，摘要是账本内字段。

输出 schema: method-assets/1。
用法：python3 scripts/method_assets.py --json / --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "method-assets/1"
ALGORITHM = "sha256-files-v1"

# 分组 → glob（相对方法论仓库根）。顺序固定，输出稳定。
ASSET_GROUPS: dict[str, str] = {
    "experts": "experts/*/EXPERT.md",
    "skills": "skills/*/SKILL.md",
    "scripts": "scripts/*.py",
    "templates": "templates/*",
    "method_docs": "docs/[0-9][0-9]-*.md",
    "standard": "docs/STANDARD.md",
}

# 资产齐备性下限：少一个专家/技能都应被 check 拦下，而不是静默算出新摘要。
MIN_COUNTS = {"experts": 8, "skills": 14, "scripts": 10,
              "templates": 3, "method_docs": 17, "standard": 1}
EXCLUDED_PARTS = {"__pycache__", ".git"}


def digest(root: Path = ROOT) -> str:
    """按「相对路径 + 内容」聚合，返回全量 hex 摘要。"""
    return manifest(root)["digest"]


def manifest(root: Path = ROOT) -> dict:
    """返回资产清单与摘要；纯函数（同一目录内容 → 同一输出）。"""
    root = Path(root)
    rows: list[dict] = []
    counts: dict[str, int] = {}
    for group, pattern in ASSET_GROUPS.items():
        paths = sorted(p for p in root.glob(pattern)
                       if p.is_file() and not set(p.parts) & EXCLUDED_PARTS)
        counts[group] = len(paths)
        for p in paths:
            rel = p.relative_to(root).as_posix()
            rows.append({"path": rel, "group": group,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    payload = "".join(f"{r['path']}:{r['sha256']}\n" for r in rows)
    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "source": ".",
        "digest": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "file_count": len(rows),
        "counts": counts,
        "groups": sorted(ASSET_GROUPS),
        # 不输出逐文件 sha256 到 CLI 默认视图，但 --json 提供完整清单供取证
        "files": rows,
        "note": "专家/技能/模板/文档不复制进目标项目；本摘要写进账本内 governance_meta",
    }


def check(root: Path = ROOT) -> dict:
    m = manifest(root)
    errors: list[str] = []
    for group, low in MIN_COUNTS.items():
        if m["counts"].get(group, 0) < low:
            errors.append(f"资产组 {group} 只有 {m['counts'].get(group, 0)} 个，少于下限 {low}")
    if m["digest"] != manifest(root)["digest"]:
        errors.append("同一目录连续两次摘要不一致：存在时间戳或不确定遍历")
    for row in m["files"]:
        if Path(row["path"]).is_absolute() or ".." in Path(row["path"]).parts:
            errors.append(f"路径不合规范：{row['path']}")
    return {"schema": "method-assets-check/1", "ok": not errors,
            "errors": errors, "digest": m["digest"], "counts": m["counts"],
            "file_count": m["file_count"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="输出完整清单 JSON")
    ap.add_argument("--check", action="store_true", help="自检资产齐备性与确定性")
    ap.add_argument("--root", default=str(ROOT), help="方法论仓库根（默认脚本所在仓库）")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if args.check:
        r = check(root)
        print(json.dumps(r, ensure_ascii=False, indent=2) if args.json else
              ("资产清单自检通过：" + r["digest"][:16] + " · " +
               str(r["file_count"]) + " 个文件" if r["ok"] else
               "资产清单自检失败：" + "；".join(r["errors"])))
        return 0 if r["ok"] else 2
    m = manifest(root)
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2))
    else:
        print(f"方法论资产 {m['file_count']} 个 · 摘要 {m['digest']}")
        for k, v in m["counts"].items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
