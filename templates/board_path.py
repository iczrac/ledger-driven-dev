#!/usr/bin/env python3
"""看板路径解析层：治理目录 → 看板文件名的唯一契约。

为什么需要它
------------
`governance/index.html` 曾以字面量散落在生成器 / 校验器 / 脚手架 / 契约 /
测试 / check.sh 中。改名若逐点硬替换，任何一处漏改都会造成：
  - verify_ledger 的 --board 指向不存在的文件而静默 pass（假绿）；
  - file_layout 清单外多出一个 HTML，被判第二事实源；
  - 同名 slug 的项目被全局映射到同一块看板（跨项目串味）。

本模块把「文件名」变成一次解析的结果：

  * **键是治理目录的完整路径**（`governance_dir(target_root).resolve()`），
    不是全局 slug 映射。同名目录位于不同路径时各自解析到各自的治理目录，
    不会互相指过去；
  * 顶层 `CapabilityForge/governance/` 没有自己的 DECISION_LEDGER.json，
    但同级存在账本主体 → 判为**系统聚合看板**，规范名 `system.html`；
  * 项目看板规范名 = 该治理目录所属**项目目录名 + .html**
    （目录名 = GitHub slug，是一等身份；`governance/` 已表达"看板区"）。

迁移策略 POLICY（由实施步骤切换，调用端不需要改）
-------------------------------------------------
  legacy     步骤 1-3：所有解析仍返回 index.html —— 回滚安全阀，行为不变；
  compatible 步骤 4-5：优先规范名，文件不存在则回落 index.html —— 原子改名零断链；
  canonical  迁移窗口结束后：只认规范名（本次实施不切换）。

`canonical_filename()` 始终返回规范名（即使当前策略是 legacy），供需要表达
"最终名字"的场景使用；`filename_for()` / `resolve()` 返回当前生效的名字。

输出：命令行 `--json` 给 board-path/1；纯文本模式只给一行路径或文件名，便于
shell 直接 `$(...)` 取值。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GOV_DIR_NAME = "governance"
LEDGER_FILENAME = "DECISION_LEDGER.json"
LEGACY_FILENAME = "index.html"
SYSTEM_FILENAME = "system.html"
PROJECT_SUFFIX = ".html"

POLICIES = ("legacy", "compatible", "canonical")
POLICY = "compatible"
SCHEMA = "board-path/1"


def governance_dir(target_root: str | Path) -> Path:
    """把「项目根」或「治理目录本身」统一成治理目录 Path（保留相对/绝对形态）。

    多个既有调用点手里只有 `gov = target / "governance"`；允许直接传入，
    避免每个调用端都去 `.parent` 而引入新的歧义。
    """
    p = Path(target_root).expanduser()
    return p if p.name == GOV_DIR_NAME else p / GOV_DIR_NAME


def _key(gov: str | Path) -> Path:
    """治理目录完整绝对路径 —— 解析层的唯一键。"""
    return Path(gov).expanduser().resolve()


def is_system_governance(gov: str | Path) -> bool:
    """顶层聚合看板识别：无自有账本，但同级存在账本主体。

    不靠目录名字面量判断，因此把方法仓挪到别处仍然成立；只看路径结构，
    不写任何账本事实。临时目录里既无自有账本也无同级账本时按项目看板处理，
    保证单项目测试夹具不会被误判成系统看板。
    """
    g = _key(governance_dir(gov))
    if (g / LEDGER_FILENAME).is_file():
        return False
    parent = g.parent
    if not parent.is_dir():
        return False
    return any(
        (child / GOV_DIR_NAME / LEDGER_FILENAME).is_file()
        for child in parent.iterdir()
        if child.is_dir() and child != g
    )


def canonical_filename(target_root: str | Path) -> str:
    """规范名（与 POLICY 无关）：系统看板 system.html；项目看板 <目录名>.html。"""
    gov = _key(governance_dir(target_root))
    if is_system_governance(gov):
        return SYSTEM_FILENAME
    return gov.parent.name + PROJECT_SUFFIX


def filename_for(target_root: str | Path) -> str:
    """当前生效的看板文件名。迁移期优先新名、回落旧名，保证工具不断链。"""
    gov = governance_dir(target_root)
    canonical = canonical_filename(gov)
    if POLICY == "legacy":
        return LEGACY_FILENAME
    if POLICY == "canonical":
        return canonical
    if (gov / canonical).is_file():
        return canonical
    if (gov / LEGACY_FILENAME).is_file():
        return LEGACY_FILENAME
    return canonical


def resolve(target_root: str | Path) -> Path:
    """当前生效的看板完整路径（保持调用端的相对/绝对形态）。"""
    gov = governance_dir(target_root)
    return gov / filename_for(gov)


def describe(target_root: str | Path) -> dict:
    """机器可读全量描述，便于门禁取证与人工核对。"""
    gov = governance_dir(target_root)
    key = _key(gov)
    return {
        "schema": SCHEMA,
        "policy": POLICY,
        "target_root": str(Path(target_root)),
        "governance_dir": str(gov),
        "key": str(key),
        "system_board": is_system_governance(gov),
        "canonical_filename": canonical_filename(gov),
        "filename": filename_for(gov),
        "resolved": str(resolve(gov)),
        "legacy_exists": (gov / LEGACY_FILENAME).is_file(),
        "canonical_exists": (gov / canonical_filename(gov)).is_file(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="项目根或治理目录（默认 .）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--filename", action="store_true", help="只输出当前生效文件名")
    g.add_argument("--canonical", action="store_true", help="只输出规范文件名（忽略 POLICY）")
    g.add_argument("--resolved", action="store_true", help="只输出当前生效路径（默认）")
    g.add_argument("--json", action="store_true", help="输出 board-path/1 JSON")
    args = ap.parse_args(argv)
    if args.json:
        print(json.dumps(describe(args.target), ensure_ascii=False, indent=2))
    elif args.filename:
        print(filename_for(args.target))
    elif args.canonical:
        print(canonical_filename(args.target))
    else:
        print(resolve(args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
