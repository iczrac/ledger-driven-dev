#!/usr/bin/env python3
"""账本读写的共享原语：让所有写入口遵守同一套约束。

为什么需要它
------------
v0.9.0 之前，每个写入脚本各自实现「读 JSON → 改 → 写回」，
看板 EMBED 同步、指纹取值、内容摘要各写一份。任何一个新写入口漏掉
其中一项，就会静默破坏 32 条不变量中的 board_embed_synced。

纪律
----
1. 账本与看板 EMBED 必须一起写，不允许只写账本；
2. 摘要一律 sha256 内容，不用时间戳判断新鲜度；
3. 只依赖标准库；路径全部相对目标项目根，不写机器绝对路径。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from board_path import resolve

EMBED_RE = re.compile(r"const EMBED = \{.*?\};\nlet DATA", re.S)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def load_ledger(gov: Path) -> dict:
    """读取账本；损坏 / 非对象一律抛 ValueError，交由调用方 fail-closed。"""
    p = Path(gov) / "DECISION_LEDGER.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取账本：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("账本必须是 JSON 对象")
    return data


def sync_board(gov: Path, ledger: dict) -> bool:
    """把账本逐字节等价地写回看板 EMBED；返回是否真的改动了看板。"""
    board = resolve(gov)
    if not board.is_file():
        return False
    html = board.read_text(encoding="utf-8")
    if not EMBED_RE.search(html):
        return False
    compact = json.dumps(ledger, ensure_ascii=False, separators=(",", ":"))
    board.write_text(
        EMBED_RE.sub(lambda _m: "const EMBED = " + compact + ";\nlet DATA",
                     html, count=1),
        encoding="utf-8")
    return True


def write_ledger(gov: Path, ledger: dict) -> None:
    """唯一合法的账本落盘入口：账本 + 看板同步，不允许拆开调用。"""
    gov = Path(gov)
    (gov / "DECISION_LEDGER.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    sync_board(gov, ledger)


def current_fingerprint(ledger: dict) -> str | None:
    hist = ledger.get("capability_model", {}).get("history", {})
    return hist.get("current_fingerprint") if isinstance(hist, dict) else None


def registry_sha(gov: Path) -> str | None:
    """registry.json 的内容摘要：手写清单也需要并发检测（F7）。"""
    p = Path(gov) / "registry.json"
    return sha256_file(p) if p.is_file() else None


def board_synced(gov: Path, ledger: dict) -> bool | None:
    """None=没有看板；True/False=EMBED 是否与账本等价。"""
    board = resolve(gov)
    if not board.is_file():
        return None
    m = re.search(r"const EMBED = (\{.*?\});\nlet DATA",
                  board.read_text(encoding="utf-8"), re.S)
    if not m:
        return False
    try:
        return json.loads(m.group(1)) == ledger
    except json.JSONDecodeError:
        return False
