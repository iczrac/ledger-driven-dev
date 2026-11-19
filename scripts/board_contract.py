#!/usr/bin/env python3
"""看板骨架契约：让「同一套样式与结构」成为可校验事实，而不是靠人记得别改。

问题
----
`templates/index.html.template` 里有完整的 CSS、DOM 骨架与渲染 JS。但
`ledger_io.sync_board()` / 生成器只替换 `const EMBED = {...};\nlet DATA`
这一段数据，**其余字节一律保留**。于是 26 条不变量里的 board_embed_synced
只保证「数据一致」，无法发现：
  - 某个项目手工改了 CSS 或删了 tab，形成差异化版面；
  - 项目初始化用了旧模板，升级了工具副本却没升级看板骨架；
  - 有人往 HTML 里塞了另一份状态（第二事实源）。

定义
----
骨架摘要 = 把 HTML 中的 EMBED 数据段替换为固定占位符后，对**剩余全部字节**
取 sha256。CSS、DOM、JS 任何一处不同都会改变摘要；账本数据变化不会。
`templates/index.html.template` 是唯一权威，摘要写进账本内
`governance_meta.board_skeleton`，不新建项目文件。

纪律
----
1. `check` 全程只读；`--diff` 式报告可以直接进 CI；
2. 归一化必须有人批准，默认 dry-run，写前把原看板存进运行时备份目录；
3. 要换样式就改方法论模板并发版，再由 upgrade 推到所有项目——禁止在项目里改。

输出 schema: board-contract/1 · board-normalize/1。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger_io import EMBED_RE, load_ledger, sha256_bytes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_REL = "templates/index.html.template"
SCHEMA_CHECK = "board-contract/1"
SCHEMA_NORMALIZE = "board-normalize/1"
PLACEHOLDER = "const EMBED = /*LEDGER*/;\nlet DATA"
STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)
REQUIRED_IDS = ("stats", "legend", "list", "foot", "q")
BACKUP_DIR = ".ledger-upgrade/backups"


def skeleton_digest(html: str) -> str:
    """忽略 EMBED 数据内容，对骨架字节取摘要。"""
    if not EMBED_RE.search(html):
        raise ValueError("找不到 const EMBED / let DATA 标记，无法计算骨架摘要")
    normalized = EMBED_RE.sub(lambda _m: PLACEHOLDER, html, count=1)
    return sha256_bytes(normalized.encode("utf-8"))


def template_digest(source_root: Path = ROOT) -> str:
    p = Path(source_root) / TEMPLATE_REL
    if not p.is_file():
        raise ValueError(f"权威模板不存在：{TEMPLATE_REL}")
    return skeleton_digest(p.read_text(encoding="utf-8"))


def board_digest(gov: Path) -> str | None:
    p = Path(gov) / "index.html"
    return skeleton_digest(p.read_text(encoding="utf-8")) if p.is_file() else None


def _layout_facts(html: str) -> dict:
    style = STYLE_RE.search(html)
    css = style.group(1) if style else ""
    return {
        "style_bytes": len(css.encode("utf-8")),
        "style_sha256": sha256_bytes(css.encode("utf-8")),
        "missing_ids": [i for i in REQUIRED_IDS if f'id="{i}"' not in html],
        "tab_count": html.count('class="tab'),
        "has_search": 'id="q"' in html,
    }


def check(target: Path, source_root: Path = ROOT) -> dict:
    """只读对比目标看板与权威模板的骨架。"""
    target = Path(target)
    gov = target / "governance"
    want = template_digest(source_root)
    board = gov / "index.html"
    if not board.is_file():
        return {"schema": SCHEMA_CHECK, "target": ".", "match": False,
                "template_digest": want, "board_digest": None,
                "reason": "看板缺失", "layout": {}, "hint": "由 init_project.py 生成或重跑 upgrade.py"}
    html = board.read_text(encoding="utf-8")
    try:
        got = skeleton_digest(html)
    except ValueError as exc:
        return {"schema": SCHEMA_CHECK, "target": ".", "match": False,
                "template_digest": want, "board_digest": None,
                "reason": str(exc), "layout": {},
                "hint": "用 normalize 从模板重建骨架"}
    facts = _layout_facts(html)
    reasons: list[str] = []
    if got != want:
        reasons.append("CSS / DOM / JS 骨架与权威模板不同")
    if facts["missing_ids"]:
        reasons.append("缺少结构锚点：" + ", ".join(facts["missing_ids"]))
    return {"schema": SCHEMA_CHECK, "target": ".", "match": got == want and not reasons,
            "template_digest": want, "board_digest": got, "layout": facts,
            "reason": "；".join(reasons) or "骨架一致，数据段由账本同步",
            "hint": "" if got == want and not reasons else
                    "python3 scripts/board_contract.py --target P normalize "
                    "--approved-by <人> --apply"}


def normalize_board(gov: Path, ledger: dict, source_root: Path = ROOT,
                    *, approved_by: str = "", apply: bool = False,
                    backup_root: Path | None = None) -> dict:
    """用权威模板骨架 + 当前账本重建 index.html。默认 dry-run。"""
    if not apply:
        return {"schema": SCHEMA_NORMALIZE, "applied": False,
                "message": "dry-run：未写盘。加 --apply --approved-by <人> 才执行"}
    if not approved_by:
        raise ValueError("归一化必须提供 --approved-by（人工批准）")
    gov = Path(gov)
    tpl = (Path(source_root) / TEMPLATE_REL).read_text(encoding="utf-8")
    compact = json.dumps(ledger, ensure_ascii=False, separators=(",", ":"))
    if not EMBED_RE.search(tpl):
        raise ValueError("权威模板缺少 EMBED 标记")
    rebuilt = EMBED_RE.sub(lambda _m: "const EMBED = " + compact + ";\nlet DATA",
                           tpl, count=1)
    board = gov / "index.html"
    before = board_digest(gov) if board.is_file() else None
    backup = None
    if backup_root is not None and board.is_file():
        bdir = Path(backup_root) / BACKUP_DIR
        bdir.mkdir(parents=True, exist_ok=True)
        name = "board-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".html"
        shutil.copyfile(board, bdir / name)
        backup = (Path(BACKUP_DIR) / name).as_posix()
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(rebuilt, encoding="utf-8")
    return {"schema": SCHEMA_NORMALIZE, "applied": True,
            "approved_by": approved_by, "backup": backup,
            "before_digest": before, "after_digest": skeleton_digest(rebuilt),
            "template_digest": template_digest(source_root),
            "message": "已用模板骨架重建看板；数据段仍是当前账本"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="目标项目根")
    ap.add_argument("command", nargs="?", default="check",
                    choices=("check", "normalize", "template-digest"))
    ap.add_argument("--apply", action="store_true", help="normalize 才写盘")
    ap.add_argument("--approved-by", default="", help="人工批准人姓名")
    ap.add_argument("--no-backup", action="store_true",
                    help="调用方已自行备份时使用（例如 upgrade.py 的统一快照）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    target = Path(args.target)
    try:
        if args.command == "template-digest":
            out: dict = {"schema": SCHEMA_CHECK, "template_digest": template_digest()}
            rc = 0
        elif args.command == "check":
            out = check(target)
            rc = 0 if out["match"] else 1
        else:
            ledger = load_ledger(target / "governance")
            out = normalize_board(target / "governance", ledger,
                                  approved_by=args.approved_by, apply=args.apply,
                                  backup_root=None if args.no_backup else target)
            rc = 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.command == "check":
        print(("看板骨架一致 · " if out["match"] else "看板骨架漂移 · ") +
              out["template_digest"][:16] + " / " +
              str(out.get("board_digest") or "∅")[:16] + " · " + out["reason"])
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
