#!/usr/bin/env python3
"""生命周期状态机：冻结 / 归档 / 能力退役 / 任务领用的唯一写入口。

设计纪律
--------
1. 不新建第二事实源：所有状态写进 DECISION_LEDGER.json 的
   lifecycle / retired_caps / execution 字段，并同步看板 EMBED。
2. 不碰 history.events：状态操作写**账本内** append-only 的 lifecycle.log 数组字段，
   避免污染由生成器维护的能力指纹链；governance/ 下没有独立的 lifecycle.log 文件。
3. 人工批准门：unfreeze / archive 必须给 --approved-by，AI 不得自行解冻。
4. 归档是不可写终态：需要继续开发就复制出新项目，而不是复活旧账本。
5. 编码不复用：retire 记录稳定的四段式编码与取代关系，restore 只撤销登记，
   不把序号分配给新能力。

用法
----
    python3 scripts/lifecycle.py --target . status
    python3 scripts/lifecycle.py --target . freeze --reason "发布窗口" --actor "release-bot"
    python3 scripts/lifecycle.py --target . unfreeze --approved-by "张三"
    python3 scripts/lifecycle.py --target . archive --approved-by "张三" --reason "交付完成"
    python3 scripts/lifecycle.py --target . retire --code DEMO.CORE.ORDER.01 \
        --reason "被统一订单服务取代" --superseded-by DEMO.CORE.ORDER.02
    python3 scripts/lifecycle.py --target . claim --code DEMO.API.QUERY.01 --actor "agent-1"
    python3 scripts/lifecycle.py --target . release --code DEMO.API.QUERY.01 --actor "agent-1"

退出码：0 成功；1 状态不合法/参数缺失；2 无法读取账本。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from board_path import resolve

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")
EMBED_RE = re.compile(r"const EMBED = \{.*?\};\nlet DATA", re.S)
MUTATIONS = {"freeze", "unfreeze", "archive", "retire", "restore", "claim", "release"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load(gov: Path) -> tuple[dict, Path]:
    p = gov / "DECISION_LEDGER.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取账本：{exc}") from exc
    if not isinstance(d, dict):
        raise SystemExit("账本必须是 JSON 对象")
    return d, p


def _sync_board(gov: Path, ledger: dict) -> None:
    """状态变更后同步看板 EMBED，维持 31 条不变量中的 board_embed_synced。"""
    board = resolve(gov)
    if not board.exists():
        return
    compact = json.dumps(ledger, ensure_ascii=False, separators=(",", ":"))
    html = board.read_text(encoding="utf-8")
    if not EMBED_RE.search(html):
        return
    board.write_text(EMBED_RE.sub(lambda _m: "const EMBED = " + compact + ";\nlet DATA",
                                  html, count=1), encoding="utf-8")


def _init(ledger: dict) -> tuple[dict, dict, list, list]:
    lc = ledger.setdefault("lifecycle", {})
    lc.setdefault("state", "active")
    lc.setdefault("reason", "")
    lc.setdefault("approved_by", "")
    lc.setdefault("since", _now())
    log = lc.setdefault("log", [])
    retired = ledger.setdefault("retired_caps", [])
    claims = ledger.setdefault("execution", {}).setdefault("claims", [])
    return lc, {}, retired, claims


def _append_log(lc: dict, action: str, actor: str, reason: str) -> None:
    log = lc.setdefault("log", [])
    log.append({"seq": len(log) + 1, "at": _now(), "action": action,
                "actor": actor, "reason": reason})


def _check_writable(lc: dict, action: str) -> str | None:
    state = lc.get("state", "active")
    if state == "archived":
        return "项目已归档，是不可写终态；请复制出新项目"
    if state == "frozen" and action not in ("unfreeze", "status", "release"):
        return "项目已冻结；先 unfreeze --approved-by <人> 解冻"
    return None


def apply(ledger: dict, action: str, *, reason: str = "", actor: str = "",
          approved_by: str = "", code: str = "", superseded_by: str = "") -> tuple[dict, str]:
    """纯状态转换；返回 (账本, 人类可读消息)。失败抛 ValueError。"""
    lc, _, retired, claims = _init(ledger)
    state = lc.get("state", "active")

    if action not in MUTATIONS:
        raise ValueError(f"未知动作：{action}")
    err = _check_writable(lc, action)
    if err:
        raise ValueError(err)

    if action == "freeze":
        if state != "active":
            raise ValueError("只有 active 可以冻结")
        lc.update(state="frozen", reason=reason or "未注明原因",
                  approved_by=approved_by, since=_now())
        _append_log(lc, action, actor or "unspecified", reason)
        return ledger, "已冻结：写入类动作会被 scenario_guard 阻止"

    if action == "unfreeze":
        if state != "frozen":
            raise ValueError("只有 frozen 可以解冻")
        if not approved_by:
            raise ValueError("解冻必须提供 --approved-by（人工批准），AI 不得自行解冻")
        lc.update(state="active", reason="", approved_by=approved_by, since=_now())
        _append_log(lc, action, approved_by, reason or "批准解冻")
        return ledger, "已解冻，批准人已记入 lifecycle.approved_by"

    if action == "archive":
        if not approved_by:
            raise ValueError("归档必须提供 --approved-by（人工批准）")
        lc.update(state="archived", reason=reason or "交付完成",
                  approved_by=approved_by, since=_now())
        _append_log(lc, action, approved_by, reason)
        return ledger, "已归档：账本转为不可写终态"

    if action in ("retire", "restore", "claim", "release"):
        if not code:
            raise ValueError("需要 --code")
        if action in ("retire", "restore") and not CODE_RE.match(code):
            raise ValueError(f"编码格式非法：{code}（应为 PROJ.MOD.DOMAIN.NN）")
        if superseded_by and not CODE_RE.match(superseded_by):
            raise ValueError(f"取代编码格式非法：{superseded_by}")

        if action == "retire":
            if any(x.get("code") == code for x in retired):
                raise ValueError(f"{code} 已登记退役，不可重复")
            retired.append({"code": code, "reason": reason or "未注明原因",
                            "superseded_by": superseded_by, "at": _now(),
                            "actor": actor or "unspecified"})
            _append_log(lc, action, actor or "unspecified", f"{code}: {reason}")
            return ledger, f"{code} 已登记退役；请同步从 registry.json 移除后重跑生成器"

        if action == "restore":
            before = len(retired)
            ledger["retired_caps"] = [x for x in retired if x.get("code") != code]
            if len(ledger["retired_caps"]) == before:
                raise ValueError(f"{code} 未在退役登记中")
            _append_log(lc, action, actor or "unspecified", f"{code}: {reason}")
            return ledger, f"{code} 退役登记已撤销（序号仍不得分配给新能力）"

        if action == "claim":
            held = next((c for c in claims if c.get("code") == code), None)
            if held and held.get("actor") != (actor or "unspecified"):
                raise ValueError(f"{code} 已被 {held.get('actor')} 领用；并发执行会写同一份事实源")
            if held:
                return ledger, f"{code} 已由 {held['actor']} 领用（幂等）"
            claims.append({"code": code, "actor": actor or "unspecified",
                           "at": _now(), "note": reason})
            _append_log(lc, action, actor or "unspecified", f"{code}: {reason}")
            return ledger, f"{code} 已领用；中断后由 release 或超时回收"

        before = len(claims)
        ledger["execution"]["claims"] = [c for c in claims if c.get("code") != code]
        if len(ledger["execution"]["claims"]) == before:
            raise ValueError(f"{code} 没有在执行的领用")
        _append_log(lc, action, actor or "unspecified", f"{code}: {reason}")
        return ledger, f"{code} 已释放"
    raise ValueError(f"未实现：{action}")


def status(ledger: dict) -> dict:
    lc = ledger.get("lifecycle", {}) if isinstance(ledger.get("lifecycle"), dict) else {}
    return {
        "state": lc.get("state", "active"),
        "reason": lc.get("reason", ""),
        "approved_by": lc.get("approved_by", ""),
        "since": lc.get("since", ""),
        "log_entries": len(lc.get("log", []) or []),
        "retired_caps": [x.get("code") for x in ledger.get("retired_caps", [])
                         if isinstance(x, dict)],
        "claims": [{"code": c.get("code"), "actor": c.get("actor"), "at": c.get("at")}
                   for c in ledger.get("execution", {}).get("claims", [])
                   if isinstance(c, dict)],
        "writable": lc.get("state", "active") == "active",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="目标项目根目录")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    for name in sorted(MUTATIONS):
        p = sub.add_parser(name)
        p.add_argument("--reason", default="")
        p.add_argument("--actor", default="")
        p.add_argument("--approved-by", default="")
        p.add_argument("--code", default="")
        p.add_argument("--superseded-by", default="")
    args = ap.parse_args(argv)

    gov = Path(args.target).expanduser().resolve() / "governance"
    ledger, path = _load(gov)
    if args.action == "status":
        out = status(ledger)
        print(json.dumps(out, ensure_ascii=False, indent=2) if args.json
              else "\n".join(f"{k}: {v}" for k, v in out.items()))
        return 0

    try:
        ledger, message = apply(
            ledger, args.action, reason=args.reason, actor=args.actor,
            approved_by=args.approved_by, code=args.code,
            superseded_by=args.superseded_by)
    except ValueError as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 1

    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    _sync_board(gov, ledger)
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
