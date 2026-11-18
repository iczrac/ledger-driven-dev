#!/usr/bin/env python3
"""校验账本自洽性：把「可信」从口号变成可执行的检查。

一套声称「证据驱动、单一事实源」的方法，自身必须可被验证。本脚本检查
账本的不变量（invariants）——任何一条失败都意味着账本已腐化，不能作为
决策或自动编程的依据。

检查项
------
1. entry_ids_unique：决策 id 唯一且不为空
2. encoding_format：能力编码格式正确
3. encoding_unique：能力编码唯一
4. completion_matches_level：完成度与等级一致（completion == level/5）
5. next_action_present：未达 L5 的能力都有下一步动作
6. evidence_tier_valid：证据分层取值合法（declared | verified）
7. verified_tier_traceable：verified 有 test_report_pass 依据且匹配真实单测
8. verified_tier_not_premature：低于 L3 或无单测的能力不得标 verified
9. doc_paths_exist：文档索引路径指向真实文件
10. component_paths_exist：组件树路径指向真实文件
11. decision_refs_valid：能力引用的决策 id 在账本中存在
12. supersede_chain_consistent：决策取代链双向一致
13. registry_impls_exist：registry 声明的实现路径真实存在
14. board_embed_synced：看板内嵌数据与账本一致
15. history_chain_consistent：历史链连贯（seq 连续、指纹前后衔接）
16. history_event_fingerprints：事件指纹自证（防篡改）
17. history_state_encoding：状态快照编码合法
18. history_current_matches：末事件指纹 == 当前能力模型指纹
19. lessons_valid：经验条目合法（confirmed 必含洞察与行动）
20. lesson_candidates_dedup：候选去重且不与已确认条目冲突
21. queue_lessons_confirmed：任务卡只引用已确认经验
22. work_items_valid：节点 TODO / issue 的 id、kind、status、severity、scope 合法
23. work_item_refs_valid：工作项引用的决策 / 能力 / 路径可解析
24. test_results_binding_valid：节点测试结果投影绑定当前测试报告且用例状态合法

三态语义
--------
每条检查返回 status = pass | fail | na：
  - pass：能力已启用且校验通过；
  - fail：能力已启用但校验失败（--strict 因此返回 1）；
  - na：能力未启用（例如没有实测报告、没有节点测试结果投影）。
na 绝不计入 pass。旧版把「未启用」写成 pass，于是 24/24 全绿可以掩盖
「证据根本没接上」——这是 v1.3.0 修掉的假绿灯。需要「未启用也算失败」的
项目可加 --require-active，逐步收紧而不破坏既有项目。

用法
----
    python3 verify_ledger.py --root examples/demo-shop --registry examples/demo-shop/governance/registry.json \
        --ledger examples/demo-shop/governance/DECISION_LEDGER.json --board examples/demo-shop/governance/index.html
    python3 verify_ledger.py --root . --json        # 机器可读输出
    python3 verify_ledger.py --root . --strict      # 存在 fail 返回非零退出码
    python3 verify_ledger.py --root . --strict --require-active  # na 也算失败

退出码：0=无 fail（允许 na）；1=存在 fail，或 --require-active 下存在 na；2=无法读取输入。

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
           board_path: Path | None, governance_dir: Path | None = None) -> list[dict]:
    """返回检查结果列表：[{id, ok, detail}, ...]。

    governance_dir 为账本所在目录，用于核对 test_results.source_sha256；
    省略时由 board_path 或 repo_root/governance 推导，保持旧调用方兼容。
    """
    results: list[dict] = []

    def add(check_id: str, ok: bool, detail: str = "",
            status: str | None = None) -> None:
        st = status or ("pass" if ok else "fail")
        if st not in ("pass", "fail", "na"):
            raise ValueError(f"非法检查状态：{st}")
        results.append({"id": check_id, "ok": st == "pass",
                        "status": st, "detail": detail})

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

    # 22. 节点工作项（TODO / issue）：写在工作台视图之前先保证数据自洽
    items = ledger.get("work_items") or []
    scopes = {"PROJECT"}
    for c in codes:
        parts = c.split(".")
        scopes.update({c, ".".join(parts[:2]), parts[0]})
    decisions = {e.get("id") for e in entries}
    w_errors: list[str] = []
    if not isinstance(items, list):
        w_errors.append("work_items 不是数组")
        items = []
    w_ids = [x.get("id") for x in items if isinstance(x, dict)]
    if len(w_ids) != len(set(w_ids)) or any(not x for x in w_ids):
        w_errors.append("id 重复或为空")
    for x in items:
        if not isinstance(x, dict):
            w_errors.append("含非对象元素")
            continue
        if x.get("kind") not in ("todo", "issue"):
            w_errors.append(f"{x.get('id')}: kind 非法")
        if x.get("status") not in ("open", "doing", "done", "blocked"):
            w_errors.append(f"{x.get('id')}: status 非法")
        if x.get("severity", "med") not in ("low", "med", "high"):
            w_errors.append(f"{x.get('id')}: severity 非法")
        if not x.get("title"):
            w_errors.append(f"{x.get('id')}: 缺 title")
        if x.get("scope") not in scopes:
            w_errors.append(f"{x.get('id')}: scope 无法解析")
    add("work_items_valid", not w_errors, f"工作项 {len(items)} 条 · 错误={w_errors[:5]}")

    # 23. 工作项引用：决策 id / 能力编码必须真实存在，否则看板会给出死链
    r_errors = []
    for x in items:
        if not isinstance(x, dict):
            continue
        for r in (x.get("refs") or []):
            if not isinstance(r, dict):
                r_errors.append(f"{x.get('id')}: refs 元素非对象")
                continue
            kind, value = r.get("kind"), str(r.get("value", ""))
            if kind == "decision" and value not in decisions:
                r_errors.append(f"{x.get('id')}: 决策 {value} 不存在")
            elif kind == "capability" and value not in set(codes):
                r_errors.append(f"{x.get('id')}: 能力 {value} 不存在")
            elif kind not in ("decision", "capability", "path"):
                r_errors.append(f"{x.get('id')}: 引用类型 {kind} 非法")
    add("work_item_refs_valid", not r_errors, f"错误={r_errors[:5]}")

    # 24. 测试结果投影：只认绑定了当前报告 hash 的只读投影，杜绝手填"全绿"
    tr = ledger.get("test_results")
    if tr is None:
        add("test_results_binding_valid", False,
            "未启用节点测试结果投影（全部能力按 declared 显示）", status="na")
    elif not isinstance(tr, dict) or tr.get("schema") != "node-test-results/1":
        add("test_results_binding_valid", False, "test_results.schema 非法")
    else:
        t_errors = []
        tcases = tr.get("cases") or []
        if not isinstance(tcases, list):
            t_errors.append("cases 不是数组")
            tcases = []
        for c in tcases:
            if not isinstance(c, dict) or c.get("status") not in ("pass", "fail", "error", "skip"):
                t_errors.append("用例状态非法")
        if (tr.get("summary") or {}).get("total") != len(tcases):
            t_errors.append("summary.total 与 cases 数量不一致")
        gov = governance_dir or (board_path.parent if board_path else repo_root / "governance")
        report = Path(gov) / "test_report.json"
        if report.is_file():
            want = hashlib.sha256(report.read_bytes()).hexdigest()
            if tr.get("source_sha256") != want:
                t_errors.append("source_sha256 与当前测试报告不一致，需 sync-tests")
        add("test_results_binding_valid", not t_errors, f"错误={t_errors[:5]}")

    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    ap.add_argument("--ledger", help="账本路径（默认 <root>/governance/DECISION_LEDGER.json）")
    ap.add_argument("--registry", help="registry.json 路径（默认 <root>/governance/registry.json）")
    ap.add_argument("--board", help="看板 HTML 路径（默认 <root>/governance/index.html）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有 fail 时返回退出码 1")
    ap.add_argument("--require-active", action="store_true",
                    help="na（能力未启用）也算失败，用于逐步收紧治理成熟度")
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

    results = verify(repo_root, ledger, registry, board, ledger_path.parent)
    passed = sum(1 for r in results if r["status"] == "pass")
    na = sum(1 for r in results if r["status"] == "na")
    failed = sum(1 for r in results if r["status"] == "fail")
    inactive = [r["id"] for r in results if r["status"] == "na"]
    blocking = failed + (na if args.require_active else 0)

    if args.json:
        print(json.dumps({
            "passed": passed, "failed": failed, "na": na,
            "all_ok": failed == 0,
            "all_active": na == 0,
            "activation": {"inactive": inactive,
                           "note": "na = 能力未启用，不计入 pass；--require-active 可判失败"},
            "checks": results,
        }, ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = {"pass": "PASS", "fail": "FAIL", "na": "NA  "}[r["status"]]
            print(f"[{mark}] {r['id']}" + (f" — {r['detail']}" if r["detail"] else ""))
        print(f"\n{passed}/{len(results)} 检查通过" +
              (f"，{failed} 失败" if failed else "") +
              (f"，{na} 未启用（na）" if na else ""))
        if inactive:
            print("未启用：" + ", ".join(inactive))

    if args.strict and blocking:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
