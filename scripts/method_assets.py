#!/usr/bin/env python3
"""方法论资产清单：把「专家 / 技能 / 模板 / 文档」纳入可校验的版本绑定。

第一性原理
----------
`upgrade.py` 原本只把 3 个 `governance/*.py` 工具副本和 method_version 写进
目标账本。可是驱动开发的不只是工具副本：专家卡定义权限与停止条件，技能定义
动作接口，路由卡给出命令，模板决定看板版面，文档定义纪律。它们一起构成
「判定规则」。若目标项目仍由 v1.0 的专家卡指挥，却拿着 v1.1 的工具副本，
`verify` 会全部通过——因为没有任何字段记录过这批资产。

这些资产属于方法论仓库，随 git tag 升级。v1.2.0 起分两层：
  - 本脚本做**整包摘要绑定**：把全部资产压成确定性 sha256，由 `upgrade.py`
    写进账本内 `governance_meta.method_assets`；
  - `asset_bundle.py` 做**只读部署副本**：把专家/技能装到项目级
    `.workbuddy/`，逐字节一致、带逐文件清单、禁止在项目内编辑。
两者共用同一个权威源，副本只是可加载的部署产物，不是第二份规则。
之后
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

# 下游真正消费的资产组：只有这些组变化才需要下游重新批准 method_assets。
# 其余两组只在本仓生效，对下游判定零影响：
#   - scripts/*.py：执行工具，改动经 M3-tool-sync 独立同步 governance/*.py 副本，
#     不改判定规则本身；下游 .workbuddy/ 从不安装 scripts。
#   - method_docs：给人看的说明文档，不参与任何 verify 判定。
# 拆出 installable_digest 后，改上述两组不再触发下游整包重批（虚警）。
INSTALLABLE_GROUPS: tuple[str, ...] = ("experts", "skills", "templates", "standard")

# 契约语义定义在 templates/ 组（build_capability_model / verify_ledger 等模板均归 R），
# scripts/ 是纯执行工具、不定义判定规则；故不做基于关键字的 T→R 升级——
# 那在纯快照下几乎恒真，无法判定，且会把「改脚本注释」误判成契约变更。

# 资产齐备性下限：少一个专家/技能都应被 check 拦下，而不是静默算出新摘要。
MIN_COUNTS = {"experts": 8, "skills": 20, "scripts": 26,
              "templates": 5, "method_docs": 21, "standard": 1}
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
    # 只把下游真正消费的组计入 installable_digest。改 scripts/method_docs
    # 不动这个摘要 → upgrade 不触发 M5 → 下游不必整包重批（消掉虚警）。
    inst_rows = [r for r in rows if r["group"] in INSTALLABLE_GROUPS]
    inst_payload = "".join(f"{r['path']}:{r['sha256']}\n" for r in inst_rows)
    return {
        "schema": SCHEMA,
        "algorithm": ALGORITHM,
        "source": ".",
        "digest": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "installable_digest": hashlib.sha256(inst_payload.encode("utf-8")).hexdigest(),
        "installable_groups": list(INSTALLABLE_GROUPS),
        "file_count": len(rows),
        "counts": counts,
        "groups": sorted(ASSET_GROUPS),
        # 不输出逐文件 sha256 到 CLI 默认视图，但 --json 提供完整清单供取证
        "files": rows,
        "note": "摘要绑定进 governance_meta.method_assets；可安装资产另有只读副本清单 "
                "（asset_bundle.py），权威源仍是方法论仓库 tag",
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
