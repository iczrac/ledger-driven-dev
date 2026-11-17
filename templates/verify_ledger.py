#!/usr/bin/env python3
"""校验账本自洽性：把「可信」从口号变成可执行的检查。

一套声称「证据驱动、单一事实源」的方法，自身必须可被验证。本脚本检查
账本的不变量（invariants）——任何一条失败都意味着账本已腐化，不能作为
决策或自动编程的依据。

检查项
------
1. 决策 id 唯一且不为空
2. 能力编码格式正确且唯一
3. 完成度与等级一致（completion == level/5）
4. 每个能力点都有下一步动作（未达 L5 时）
5. 文档索引路径指向真实文件
6. 组件树路径指向真实文件
7. 能力引用的决策 id 在账本中存在
8. 决策取代链双向一致
9. registry 中声明的实现路径真实存在（来源真实性）
10. 看板内嵌数据与账本一致
11. 历史链连贯（seq 连续、fingerprint 前后衔接、首事件 before 为空）
12. 历史事件指纹自证（state_digest 重算 == fingerprint_after，防篡改）
13. 历史末事件指纹 == 当前能力模型指纹（账本状态与历史一致）
14. 经验条目合法（id 唯一、状态合法、confirmed 必含洞察与行动、事件引用有效）
15. 经验候选去重且与已确认条目不冲突
16. 任务卡引用的经验均为已确认条目
17. 证据分层取值合法（declared | verified）
18. verified 可追溯（tier_detail 有 test_report_pass 依据，匹配单测真实存在）
19. verified 不越级（低于 L3、无单测的能力不得标 verified）

用法
----
    python3 verify_ledger.py --root examples/demo-shop --registry examples/demo-shop/governance/registry.json \
        --ledger examples/demo-shop/governance/DECISION_LEDGER.json --board examples/demo-shop/governance/index.html
    python3 verify_ledger.py --root . --json        # 机器可读输出
    python3 verify_ledger.py --root . --strict      # 任何失败返回非零退出码

退出码：0=全部通过；1=存在失败（仅 --strict）；2=无法读取输入。

依赖：仅标准库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

# 四段式：项目.模块.域均以大写字母开头；序号段为两位数字
CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")
DOC_INDEX_PATH_KEYS = (
    "plans", "related_docs", "module_docs",
    "contracts", "impl", "unit_tests", "test_records",
)
EVIDENCE_KEYS = ("impl", "contract", "unit_test", "test_record")
LESSON_STATUS = {"draft", "confirmed", "retired"}


# 以下两个函数是与生成器一致的独立实现：双实现交叉验证，能发现任一方的规范漂移。
def _path_list(values) -> list[str]:
    out: list[str] = []
    for v in values or []:
        if isinstance(v, dict):
            v = v.get("path")
        if v:
            out.append(str(v))
    return out


def snapshot_state(cm: dict) -> dict[str, dict]:
    snap: dict[str, dict] = {}
    for p in cm.get("projects", []):
        for m in p.get("modules", []):
            for c in m.get("caps", []):
                ev, di = c.get("evidence", {}), c.get("doc_index", {})
                snap[c.get("code", "")] = {
                    "l": c.get("level", 0),
                    "c": c.get("completion", 0),
                    "t": c.get("evidence_tier", "declared"),
                    "e": sorted({x for k in EVIDENCE_KEYS for x in _path_list(ev.get(k))}),
                    "d": sorted({x for k in DOC_INDEX_PATH_KEYS for x in _path_list(di.get(k))}),
                    "dec": sorted({x.get("id") for x in di.get("decisions", [])
                                   if isinstance(x, dict) and x.get("id")}),
                }
    return snap


def fingerprint_state(snap: dict) -> str:
    payload = json.dumps(snap, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def verify(repo_root: Path, ledger: dict, registry: dict | None,
           board_path: Path | None) -> list[dict]:
    """返回检查结果列表：[{id, ok, detail}, ...]。"""
    results: list[dict] = []

    def add(check_id: str, ok: bool, detail: str = "") -> None:
        results.append({"id": check_id, "ok": bool(ok), "detail": detail})

    entries = ledger.get("entries", [])
    cm = ledger.get("capability_model", {})
    projects = cm.get("projects", [])
    caps = [c for p in projects for m in p.get("modules", []) for c in m.get("caps", [])]

    # 1. 决策 id 唯一
    eids = [e.get("id") for e in entries]
    dup_eids = sorted({x for x in eids if eids.count(x) > 1})
    bad_eids = [x for x in eids if not x]
    add("entry_ids_unique", not dup_eids and not bad_eids,
        f"重复={dup_eids} 空值={len(bad_eids)}")

    # 2. 编码格式与唯一性
    codes = [c.get("code", "") for c in caps]
    bad_codes = [c for c in codes if not CODE_RE.match(c)]
    dup_codes = sorted({c for c in codes if codes.count(c) > 1})
    add("encoding_format", not bad_codes, f"非法={bad_codes[:5]}")
    add("encoding_unique", not dup_codes, f"重复={dup_codes[:5]}")

    # 3. 完成度与等级一致
    mismatch = [
        c["code"] for c in caps
        if abs(c.get("completion", -1) - round(c.get("level", -1) / 5, 2)) > 1e-9
    ]
    add("completion_matches_level", not mismatch, f"不一致={mismatch[:5]}")

    # 4. 未达 L5 的能力都有下一步动作
    no_action = [c["code"] for c in caps if c.get("level", 5) < 5 and not c.get("next_action")]
    add("next_action_present", not no_action, f"缺失={no_action[:5]}")

    # 4b. 证据分层：tier 取值合法
    valid_tiers = {"declared", "verified"}
    bad_tiers = [c["code"] for c in caps if c.get("evidence_tier", "declared") not in valid_tiers]
    add("evidence_tier_valid", not bad_tiers, f"非法={bad_tiers[:5]}")

    # 4c. verified 必须有可追溯依据：tier_detail 标记来自测试报告，且匹配的单测文件真实存在
    bad_verified: list[str] = []
    for c in caps:
        if c.get("evidence_tier") != "verified":
            continue
        td = c.get("tier_detail") or {}
        matched = td.get("matched_tests") or []
        if td.get("basis") != "test_report_pass" or not matched:
            bad_verified.append(f"{c['code']}:no_basis")
            continue
        # 匹配的单测文件必须在账本记录的 unit_test 证据中真实存在
        unit_names = {Path(x).name for x in _path_list(c.get("evidence", {}).get("unit_test"))}
        if not set(matched) & unit_names:
            bad_verified.append(f"{c['code']}:orphan_match")
    add("verified_tier_traceable", not bad_verified, f"不可追溯={bad_verified[:5]}")

    # 4d. 低于 L3 的能力不得标 verified（没有单测却声称实测通过）
    premature = [c["code"] for c in caps
                 if c.get("evidence_tier") == "verified" and c.get("level", 0) < 3]
    add("verified_tier_not_premature", not premature, f"越级={premature[:5]}")

    # 5. 文档索引路径存在
    missing_docs: list[str] = []
    for c in caps:
        di = c.get("doc_index", {})
        for key in DOC_INDEX_PATH_KEYS:
            for item in di.get(key, []):
                p = item.get("path")
                if p and not (repo_root / p).exists():
                    missing_docs.append(f"{c['code']}:{p}")
    add("doc_paths_exist", not missing_docs,
        f"缺失 {len(missing_docs)} 条: {missing_docs[:3]}")

    # 6. 组件树路径存在（文件节点；目录节点同样校验）
    missing_components: list[str] = []
    for p in projects:
        for m in p.get("modules", []):
            def walk(nodes: list[dict]) -> None:
                for n in nodes:
                    path = n.get("path")
                    if path and not (repo_root / path).exists():
                        missing_components.append(path)
                    walk(n.get("children", []))
            walk(m.get("component_tree", []))
    add("component_paths_exist", not missing_components,
        f"缺失 {len(missing_components)}: {missing_components[:3]}")

    # 7. 能力引用的决策 id 存在
    entry_ids = set(eids)
    bad_refs = [
        f"{c['code']}:{d.get('id')}"
        for c in caps for d in c.get("doc_index", {}).get("decisions", [])
        if d.get("id") not in entry_ids
    ]
    add("decision_refs_valid", not bad_refs, f"悬空={bad_refs[:5]}")

    # 8. 取代链双向一致
    by_id = {e.get("id"): e for e in entries}
    chain_errors: list[str] = []
    for e in entries:
        other = e.get("superseded_by")
        if other:
            if other not in by_id:
                chain_errors.append(f"{e['id']}→不存在:{other}")
            elif by_id[other].get("supersedes") != e["id"]:
                chain_errors.append(f"{e['id']}→{other} 未回填 supersedes")
        prev = e.get("supersedes")
        if prev:
            if prev not in by_id:
                chain_errors.append(f"{e['id']}←不存在:{prev}")
            elif by_id[prev].get("superseded_by") != e["id"]:
                chain_errors.append(f"{e['id']}←{prev} 未回填 superseded_by")
    add("supersede_chain_consistent", not chain_errors, f"错误={chain_errors[:5]}")

    # 9. registry 声明的实现路径真实存在
    if registry:
        proj_rel = registry.get("project", {}).get("root", "").strip("/")
        proj_root = repo_root / proj_rel
        empty_impl: list[str] = []
        for mod in registry.get("modules", []):
            for cap in mod.get("caps", []):
                globs = cap.get("impl", [])
                hit = any(
                    (proj_root / g).exists() or list(proj_root.glob(g))
                    for g in globs
                )
                if globs and not hit:
                    empty_impl.append(f"{mod['code']}.{cap.get('domain')}:{globs}")
        add("registry_impls_exist", not empty_impl, f"空实现={empty_impl[:5]}")
    else:
        add("registry_impls_exist", True, "未提供 registry，跳过")

    # 10. 看板内嵌数据与账本一致
    if board_path and board_path.exists():
        text = board_path.read_text()
        m = re.search(r"const EMBED = (\{.*?\});\nlet DATA", text, re.S)
        if not m:
            add("board_embed_synced", False, "未找到 EMBED 标记")
        else:
            try:
                embedded = json.loads(m.group(1))
                d1 = json.dumps(embedded, ensure_ascii=False, sort_keys=True)
                d2 = json.dumps(ledger, ensure_ascii=False, sort_keys=True)
                add("board_embed_synced", d1 == d2,
                    "一致" if d1 == d2 else "不一致，请重跑生成器")
            except json.JSONDecodeError as exc:
                add("board_embed_synced", False, f"EMBED 解析失败: {exc}")
    else:
        add("board_embed_synced", True, "未提供看板，跳过")

    # 11. 历史链连贯：seq 连续 + 指纹前后衔接（可检出删改中间事件）
    hist = ledger.get("history") or {}
    events = hist.get("events")
    chain_errors: list[str] = []
    if not isinstance(events, list) or not events:
        chain_errors.append("history.events 缺失或为空，请先重跑生成器")
    else:
        for i, ev in enumerate(events):
            seq = ev.get("seq")
            if seq != i + 1:
                chain_errors.append(f"#{i + 1} seq={seq} 不连续")
            if i == 0:
                if ev.get("fingerprint_before") is not None:
                    chain_errors.append(f"#{seq} 首事件 before 应为 null")
            elif ev.get("fingerprint_before") != events[i - 1].get("fingerprint_after"):
                chain_errors.append(f"#{seq} 链断裂：before != 上一事件 after")
            if not ev.get("fingerprint_after"):
                chain_errors.append(f"#{seq} 缺 fingerprint_after")
            if not isinstance(ev.get("state_digest"), dict):
                chain_errors.append(f"#{seq} 缺 state_digest")
    add("history_chain_consistent", not chain_errors, f"错误={chain_errors[:5]}")

    # 12. 历史事件指纹自证：state_digest 重算必须等于记录的 after
    fp_errors: list[str] = []
    for ev in events or []:
        sd = ev.get("state_digest")
        if isinstance(sd, dict):
            calc = fingerprint_state(sd)
            if calc != ev.get("fingerprint_after"):
                fp_errors.append(f"#{ev.get('seq')}: 记录={ev.get('fingerprint_after')} 实算={calc}")
    add("history_event_fingerprints", not fp_errors, f"不一致={fp_errors[:5]}")

    # 13. 历史末事件 == 当前能力模型（账本状态就是历史最新状态）
    bad_sd_codes = sorted({
        code for ev in events or [] for code in (ev.get("state_digest") or {})
        if not CODE_RE.match(code)
    })
    add("history_state_encoding", not bad_sd_codes, f"非法={bad_sd_codes[:5]}")
    current_fp = fingerprint_state(snapshot_state(cm))
    latest_fp = events[-1].get("fingerprint_after") if events else None
    add("history_current_matches", current_fp == latest_fp,
        f"当前={current_fp} 末事件={latest_fp}（不一致请重跑生成器）")

    # 14/15. 经验层合法性与去重
    lessons = ledger.get("lessons") or {}
    items, candidates = lessons.get("items") or [], lessons.get("candidates") or []
    lesson_errors: list[str] = []
    if not isinstance(lessons, dict) or not lessons:
        lesson_errors.append("lessons 缺失，请先重跑生成器")
    lids = [x.get("id") for x in items]
    dup_lids = sorted({x for x in lids if lids.count(x) > 1})
    if dup_lids:
        lesson_errors.append(f"重复 id={dup_lids}")
    seqs = {ev.get("seq") for ev in events or []}
    for x in items:
        st = x.get("status")
        if st not in LESSON_STATUS:
            lesson_errors.append(f"{x.get('id')}: 非法状态 {st}")
        if st == "confirmed" and (not x.get("insight") or not x.get("action")):
            lesson_errors.append(f"{x.get('id')}: confirmed 缺 insight/action")
        for s in x.get("source_events") or []:
            if s not in seqs:
                lesson_errors.append(f"{x.get('id')}: 事件 {s} 不存在")
    add("lessons_valid", not lesson_errors, f"错误={lesson_errors[:5]}")

    cand_errors: list[str] = []
    cids = [c.get("id") for c in candidates]
    dup_cids = sorted({x for x in cids if cids.count(x) > 1})
    if dup_cids:
        cand_errors.append(f"重复候选={dup_cids}")
    overlap = sorted(set(cids) & set(lids))
    if overlap:
        cand_errors.append(f"候选与条目冲突={overlap}")
    for c in candidates:
        for s in c.get("source_events") or []:
            if s not in seqs:
                cand_errors.append(f"{c.get('id')}: 事件 {s} 不存在")
    add("lesson_candidates_dedup", not cand_errors, f"错误={cand_errors[:5]}")

    # 16. 任务卡引用的经验必须是已确认条目（否则 AI 会消费草稿结论）
    confirmed = {x.get("id") for x in items if x.get("status") == "confirmed"}
    q_errors = [
        f"{t.get('code')}→{ref.get('id')}"
        for t in (cm.get("next_queue") or [])
        for ref in (t.get("lessons") or [])
        if ref.get("id") not in confirmed
    ]
    add("queue_lessons_confirmed", not q_errors, f"未确认引用={q_errors[:5]}")

    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    ap.add_argument("--ledger", help="账本路径（默认 <root>/governance/DECISION_LEDGER.json）")
    ap.add_argument("--registry", help="registry.json 路径（默认 <root>/governance/registry.json）")
    ap.add_argument("--board", help="看板 HTML 路径（默认 <root>/governance/index.html）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有失败时返回退出码 1")
    args = ap.parse_args()

    repo_root = Path(args.root).resolve()
    ledger_path = Path(args.ledger) if args.ledger else repo_root / "governance" / "DECISION_LEDGER.json"
    reg_path = Path(args.registry) if args.registry else repo_root / "governance" / "registry.json"
    board_path = Path(args.board) if args.board else repo_root / "governance" / "index.html"

    try:
        ledger = json.loads(Path(ledger_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"无法读取账本: {exc}")
        raise SystemExit(2)
    registry = json.loads(reg_path.read_text()) if reg_path.exists() else None
    board = board_path if board_path.exists() else None

    results = verify(repo_root, ledger, registry, board)
    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed

    if args.json:
        print(json.dumps({
            "passed": passed, "failed": failed,
            "all_ok": failed == 0, "checks": results,
        }, ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"[{mark}] {r['id']}" + (f" — {r['detail']}" if r["detail"] else ""))
        print(f"\n{passed}/{len(results)} 检查通过" + (f"，{failed} 失败" if failed else ""))

    if args.strict and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
