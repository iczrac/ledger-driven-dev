#!/usr/bin/env python3
"""派生 issue（v2.3.0）：把「非 bound 能力」投影成可认领的 issue。

为什么必须是派生的
------------------
v2.2.0 把 verified 收紧到绑定硬门禁，14 个能力诚实降级为 declared。但只报警
不闭环的红灯会退化成红灯疲劳。issue 若靠 work_panel add 手工维护，就又多了
一个可删、可改状态的手工面——「声明权=伪造权」原路返回。

所以 issue_set = h(账本.binding_status)：
* 每个非 bound 能力恰好一条派生 issue，id 固定、source=derived；
* 机器控制存在性 / status / close_condition / severity；
* 人只补充 owner / owner_note / 人工 detail；重算一律保留；
* 能力转 bound 时自动关单（关闭条件由证据满足，账本不说谎）。

close_condition.kind 复用 capability_verified：v2.2.0 起 verified⟺bound，
两者等价，故不新增 kind，work_panel / verifier 的关单判定逻辑无需改动。
"""
from __future__ import annotations

from datetime import datetime

# 非 bound 且需要生成 issue 的绑定状态；bound 与缺字段（旧账本）都不生成。
BINDING_TYPES = ("unbound", "no_impl", "via1", "no_tests")
HIGH_SEVERITY = ("unbound", "no_impl")
DERIVED_SOURCE = "derived"
ID_PREFIX = "W-BIND-"

_STATUS_LABEL = {
    "unbound": "测试与实现无符号绑定关系",
    "no_impl": "声明了测试但实现为空",
    "via1": "测试经一跳编排层间接触达实现",
    "no_tests": "无测试声明",
}


def _issue_id(code: str) -> str:
    """由能力 code 派生稳定 id：W-BIND-<P1>-RS-SECTOR-03。"""
    return ID_PREFIX + code.replace(".", "-")


def _new_issue(cap: dict) -> dict:
    code = str(cap.get("code", ""))
    status = str(cap.get("binding_status", ""))
    return {
        "id": _issue_id(code),
        "kind": "issue",
        "scope": code,
        "status": "open",
        "severity": "high" if status in HIGH_SEVERITY else "med",
        "title": f"绑定未达标：{code}（{status}）",
        "detail": _STATUS_LABEL.get(status, "绑定未达标"),
        "owner": "",
        "owner_note": "绑定门禁自动生成，待认领；修复后自动关闭",
        "refs": [{"kind": "capability", "value": code}],
        "source": DERIVED_SOURCE,
        "derived_from": {
            "code": code,
            "binding_status": status,
            "rule": "verified⟺bound (v2.2.0)",
        },
        "close_condition": {
            "kind": "capability_verified",
            "capability": code,
        },
    }


def caps_of_model(model: dict) -> list[dict]:
    """从 capability_model 展平所有能力节点。"""
    return [c for p in (model or {}).get("projects", [])
            for m in p.get("modules", []) for c in m.get("caps", [])]


def check_issues(ledger: dict, model: dict) -> list[str]:
    """生成器 --check 用：账本派生 issue 相对重算状态的漂移行。"""
    return ["work_items: " + x for x in
            diff_derived_issues(ledger.get("work_items") or [], caps_of_model(model))]


def diff_derived_issues(work_items: list, caps: list[dict]) -> list[str]:
    """可复算比对：账本里的派生 issue 是否与当前绑定状态一致。

    只比对机器控制的字段（存在性 / status / severity / close_condition /
    derived_from.binding_status）；人工字段（owner / owner_note / detail）与
    关单时间戳不参与——它们是人的输入，不是 f(仓库) 的输出。
    """
    current = [x for x in (work_items or []) if isinstance(x, dict)
               and x.get("source") == DERIVED_SOURCE]
    current_by_id = {x.get("id"): x for x in current}
    # 用「当前账本 + 现有 caps」跑一次收敛，得到应然状态：非 bound 存在且 open，
    # bound 则保留但自动关闭。比对机器字段即可覆盖缺 issue / 未关闭 / 状态过期。
    expected = [x for x in sync_derived_issues(work_items, caps)
                if x.get("source") == DERIVED_SOURCE]
    expected_by_id = {x["id"]: x for x in expected}
    drifts: list[str] = []
    for iid, want in expected_by_id.items():
        got = current_by_id.get(iid)
        if got is None:
            drifts.append(f"{iid}: 缺派生 issue（非 bound 能力必须可认领）")
            continue
        for key in ("status", "severity", "scope", "kind"):
            if got.get(key) != want[key]:
                drifts.append(f"{iid}.{key}: 账本={got.get(key)!r} 应为={want[key]!r}")
        if got.get("close_condition") != want["close_condition"]:
            drifts.append(f"{iid}.close_condition 与绑定状态不一致")
        if (got.get("derived_from") or {}).get("binding_status") != \
                want["derived_from"]["binding_status"]:
            drifts.append(f"{iid}.derived_from.binding_status 过期")
    for iid in current_by_id:
        if iid not in expected_by_id:
            drifts.append(f"{iid}: 孤儿派生 issue（引用了不存在的能力）")
    return drifts


def sync_derived_issues(work_items: list, caps: list[dict]) -> list:
    """按当前能力绑定状态，把派生 issue 集合收敛到账本 work_items。

    work_items 是账本既有数组（可能含人工项）。本函数只碰 source=derived
    的条目，人工项原样保留；对每条派生 issue：
      - 非 bound 能力：不存在则新建；存在则刷新机器字段、保留人工字段；
      - bound 能力：存在未关闭的派生 issue 则自动关闭并写依据。

    幂等：同一输入重复调用产出不变（除自动关单的时间戳首次写入后不再变）。
    """
    items = [dict(x) for x in (work_items or []) if isinstance(x, dict)]
    by_code = {str(c.get("code", "")): c for c in (caps or [])}
    derived = [x for x in items if x.get("source") == DERIVED_SOURCE]
    by_id = {x.get("id"): x for x in derived}

    # 1) 收敛：为每个非 bound 能力确保一条派生 issue
    wanted_ids: set[str] = set()
    for code, cap in by_code.items():
        bstatus = str(cap.get("binding_status", ""))
        if bstatus not in BINDING_TYPES or not code:
            continue
        iid = _issue_id(code)
        wanted_ids.add(iid)
        fresh = _new_issue(cap)
        old = by_id.get(iid)
        if old is None:
            items.append(fresh)
            by_id[iid] = fresh
            continue
        # 机器字段刷新；人工字段一律保留
        for key in ("kind", "scope", "status", "severity", "title",
                    "refs", "source", "derived_from", "close_condition"):
            old[key] = fresh[key]
        # detail：机器首写，若人工补充过（与机器文案不同）则保留
        if not str(old.get("detail") or "").strip():
            old["detail"] = fresh["detail"]
        if not str(old.get("owner_note") or "").strip():
            old["owner_note"] = fresh["owner_note"]
        # 若之前被自动关闭但现在又非 bound，重新打开（能力回退）
        if old.get("status") == "done" and str(old.get("auto_closed")) == "yes":
            old["status"] = "open"
            old.pop("resolution", None)
            old.pop("closed_at", None)
            old.pop("closed_by", None)
            old.pop("auto_closed", None)

    # 2) 关单：能力已 bound（或字段消失）时，自动关闭仍 open 的派生 issue
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    for x in items:
        if x.get("source") != DERIVED_SOURCE or x.get("status") == "done":
            continue
        code = str((x.get("derived_from") or {}).get("code", ""))
        cap = by_code.get(code)
        bstatus = str(cap.get("binding_status", "")) if cap else ""
        if bstatus in BINDING_TYPES:
            continue  # 仍未达标，保持 open
        x["status"] = "done"
        x["closed_by"] = "system:binding-gate"
        x["closed_at"] = ts
        x["auto_closed"] = "yes"
        x["resolution"] = f"能力 {code} 绑定状态为 {bstatus or '已升级'}，关闭条件 capability_verified 已满足"

    return items
