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
7. verified_tier_traceable：verified 有 test_report_pass 依据、匹配真实单测且绑定为 bound（v2.2.0）
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
22. work_items_valid：节点 TODO / issue 的 id、kind、status、severity、scope 合法；
    且 close_condition 一旦被证据满足，就不允许仍停留在 open/doing（账本不许说谎）
23. work_item_refs_valid：工作项引用的决策 / 能力 / 路径可解析
24. test_results_binding_valid：节点测试结果投影绑定当前测试报告且用例状态合法
25. work_items_owned：未完结（open/doing/blocked）的工作项必须写 owner（人或
    专家名），写不出必须写 owner_note 说明缺口——专家路由不能只当装饰
26. installed_assets_binding：.workbuddy 只读副本逐文件 sha256 与
    ASSET_MANIFEST 一致、整包摘要与账本 installed_assets.digest 一致
    （未安装资产时 na）
27. binding_issues_derived：每个非 bound 能力恰好一条 source=derived 的 open
    issue；已 bound 的派生 issue 不得仍 open（issue 是账本投影，非手工第二源）
28. analytics_maturity_valid：分析层时间序列末点与当前等级一致、健康度子维度
    在 0-100 且加权和自洽、推荐行动与任务卡增益可追溯（旧账本未启用判 na）
29. analytics_d3_projection_valid：D3 消费的追溯树与事件时间轴自证——节点 id
    唯一、决策引用真实、状态节点等于当前能力、时间轴 seq 连续（旧账本判 na）

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
import sys
from pathlib import Path

# v2.0.1：校验器与生成器共用同一 registry codec，避免第二套 code 规则。
try:
    from registry_codec import iter_caps as registry_iter_caps
except ModuleNotFoundError:  # pragma: no cover - 仅在 spec 加载路径触发
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from registry_codec import iter_caps as registry_iter_caps

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


CLOSE_KINDS = ("manual", "capability_verified", "file_exists")


def close_condition_met(cond: dict, caps_by_code: dict, repo_root: Path) -> tuple[bool, str]:
    """判定工作项的关闭条件是否已被证据满足，返回 (满足?, 说明)。

    第一性原理：结构不变量再全绿，也挡不住「事情做完了但工作项还挂着 open」。
    工作项会被看板与 next_queue 喂给下一个执行者，挂着未关等于指挥它去重做。
    因此每条工作项可以声明机器可判定的关闭条件：

      - capability_verified：指定能力已升为 verified；
      - file_exists：指定路径真实存在；
      - manual：只能人工判定（永远不自动满足）。

    无法判定的条件一律视为未满足——宁可漏关，不可误关。
    """
    if not isinstance(cond, dict):
        return False, "close_condition 必须是对象"
    kind = cond.get("kind")
    if kind == "manual":
        return False, "人工判定"
    if kind == "capability_verified":
        code = str(cond.get("capability", "")).strip()
        cap = caps_by_code.get(code)
        if cap is None:
            return False, f"能力不存在 {code}"
        tier = cap.get("evidence_tier", "declared")
        return tier == "verified", f"{code} tier={tier}"
    if kind == "file_exists":
        rel = str(cond.get("path", "")).strip().strip("/")
        exists = bool(rel) and (repo_root / rel).exists()
        return exists, f"{rel} 存在={exists}"
    return False, f"未知 close_condition.kind={kind}"


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

    # 4c. verified 必须有可追溯依据：tier_detail 标记来自测试报告，匹配的单测真实存在，
    #     且 v2.2.0 符号级绑定为 bound（声明权≠伪造权）。
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
            continue
        # v2.2.0：verified 必须带绑定依据且为 bound；缺字段或伪造均拦截
        if c.get("binding_status") != "bound":
            bad_verified.append(f"{c['code']}:unbound_verified")
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
        empty_impl: list[str] = []
        for cap in registry_iter_caps(registry):
            proj_root = repo_root / cap["project_root"]
            globs = cap["impl"]
            hit = any(
                (proj_root / g).exists() or list(proj_root.glob(g))
                for g in globs
            )
            if globs and not hit:
                empty_impl.append(f"{cap['code']}:{globs}")
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
        cond = x.get("close_condition")
        if cond is not None and x.get("status") in ("open", "doing"):
            met, why = close_condition_met(cond, {c.get("code"): c for c in caps}, repo_root)
            if met:
                w_errors.append(
                    f"{x.get('id')}: 关闭条件已满足（{why}）但仍 {x.get('status')}"
                    "——事件已完成，账本不许继续挂账")
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

    # 25. 工作项负责人（v2.1.2）：专家层不能只当装饰。
    # 账本纪律是「AI 不凭空指派 owner，需用户提供」——所以规矩不是让谁去填，
    # 而是让缺口可见：未完结的工作必须有 owner，或以 owner_note 说明为何空。
    # done 条目不追溯：给已完成的工作补负责人既不改变事实也不产生证据。
    if not items:
        add("work_items_owned", True, "未启用工作项", status="na")
    else:
        o_errors = []
        open_n = 0
        for x in items:
            if not isinstance(x, dict) or x.get("status") == "done":
                continue
            open_n += 1
            if (not str(x.get("owner") or "").strip()
                    and not str(x.get("owner_note") or "").strip()):
                o_errors.append(f"{x.get('id')}: 未完结但无 owner 也无 owner_note")
        add("work_items_owned", not o_errors,
            f"未完结 {open_n} 条 · 错误={o_errors[:5]}")

    # 26. 安装资产绑定（v2.1.2）：.workbuddy 的专家/技能副本是仓库里
    # 「看起来最没有后果、最容易被随手改」的角落。清单存在时逐文件比对
    # sha256、整包摘要、账本 installed_assets.digest——任一不符即 fail。
    # 摘要算法与 asset_bundle.py 的 sha256-files-v1 同规范：每行
    # "{path}:{sha256}\n"（path 含 .workbuddy/ 前缀），按 path 排序后拼接。
    # 只查清单登记的路径；清单外的 .workbuddy 文件（用户自有技能）不在此列。
    gov_dir = governance_dir or (board_path.parent if board_path else repo_root / "governance")
    mf_path = Path(gov_dir) / "ASSET_MANIFEST.json"
    if not mf_path.is_file():
        add("installed_assets_binding", True, "未安装专家/技能资产", status="na")
    else:
        # 清单里的 path 相对项目根（.workbuddy 所在目录），不是 --root；
        # demo 夹具的 root 是示例仓库上一层，用 --root 会把路径指错。
        proj_root = Path(gov_dir).parent
        a_errors: list[str] = []
        pairs: list[tuple[str, str]] = []
        mf = None
        try:
            mf = json.loads(mf_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            a_errors.append("ASSET_MANIFEST 不可解析")
        if isinstance(mf, dict):
            for r in mf.get("files") or []:
                if not isinstance(r, dict):
                    continue
                rel = str(r.get("path", ""))
                p = proj_root / rel
                if not p.is_file():
                    a_errors.append(f"{rel}: 副本缺失")
                    continue
                got = hashlib.sha256(p.read_bytes()).hexdigest()
                if got != str(r.get("sha256", "")):
                    a_errors.append(f"{rel}: sha256 与清单不符（副本被改或清单过期）")
                pairs.append((rel, got))
            digest = hashlib.sha256(
                "".join(f"{p}:{s}\n" for p, s in sorted(pairs)).encode("utf-8")
            ).hexdigest()
            if mf.get("digest") != digest:
                a_errors.append("清单整包摘要与实测不符")
            bound = ((ledger.get("governance_meta") or {})
                     .get("installed_assets") or {}).get("digest")
            if bound != digest:
                a_errors.append("账本 installed_assets.digest 与实测摘要不一致")
        add("installed_assets_binding", not a_errors,
            (f"资产 {len(pairs)} 份 · 摘要 {digest[:12]}" if not a_errors
             else f"错误={a_errors[:5]}"))

    # 27. 绑定问题必须有派生 issue（v2.3.0）：issue_set = h(binding_status)。
    #     issue 若是手工维护的第二事实源，就能被删、被改状态——「声明权=伪造权」
    #     原路返回。故要求：每个非 bound 能力恰好一条 source=derived 的 open
    #     issue；已 bound 能力的派生 issue 不得仍 open（关闭条件已满足却说谎）。
    #     旧账本无 binding_status 字段视为未启用（na），不误伤未升级项目。
    from derived_issues import BINDING_TYPES as _BINDING_TYPES
    status_by_code = {
        str(c.get("code", "")): c.get("binding_status")
        for c in caps
    }
    has_binding_field = any(
        c.get("binding_status") is not None for c in caps)
    derived_items = [x for x in items
                     if isinstance(x, dict) and x.get("source") == "derived"]
    derived_codes = [str((x.get("derived_from") or {}).get("code", ""))
                     for x in derived_items]
    b_errors: list[str] = []
    if has_binding_field:
        for code, bstatus in status_by_code.items():
            want = bstatus in _BINDING_TYPES
            open_here = any(
                x.get("status") != "done"
                and str((x.get("derived_from") or {}).get("code", "")) == code
                for x in derived_items)
            if want and not open_here:
                b_errors.append(f"{code}:{bstatus}缺issue")
            if not want and open_here:
                b_errors.append(f"{code}:{bstatus or 'bound'}仍open")
        dupes = {c for c in derived_codes if derived_codes.count(c) > 1}
        if dupes:
            b_errors.append(f"重复issue={sorted(dupes)[:3]}")
        add("binding_issues_derived", not b_errors,
            (f"派生 {len(derived_items)} 条 · 非bound "
             f"{sum(1 for s in status_by_code.values() if s in _BINDING_TYPES)} 个"
             if not b_errors else f"错误={b_errors[:5]}"))
    else:
        add("binding_issues_derived", True, "未启用绑定门禁（旧账本）", status="na")

    # 28. 分析层（v2.11.0）：热力图/趋势/健康度/推荐行动都从这里取数。
    #     若允许手填分数，看板就会变成第二套判定——必须逐字段自证。
    analytics = cm.get("analytics")
    if not isinstance(analytics, dict):
        add("analytics_maturity_valid", True, "未启用分析层（旧账本）", status="na")
    else:
        from build_capability_model import (  # 局部导入：保持旧脚本可单独运行
            ANALYTICS_SCHEMA, HEALTH_DIMENSION_WEIGHTS)

        a_errors: list[str] = []
        cap_by_code = {c.get("code"): c for c in caps}
        if analytics.get("schema") != ANALYTICS_SCHEMA:
            a_errors.append(f"schema={analytics.get('schema')}")
        maturity = analytics.get("maturity") or {}
        for code, row in maturity.items():
            if code not in cap_by_code:
                a_errors.append(f"{code}:未知能力")
                continue
            series = (row or {}).get("series") or []
            if not series:
                a_errors.append(f"{code}:空序列")
                continue
            last = series[-1]
            cap = cap_by_code[code]
            if last.get("level") != cap.get("level") or last.get("tier") != cap.get("evidence_tier"):
                a_errors.append(f"{code}:末点≠当前")
            for pt in series:
                lv = pt.get("level")
                if not isinstance(lv, int) or not 0 <= lv <= 5:
                    a_errors.append(f"{code}:等级越界 {lv}")
                    break
        change = analytics.get("change_summary") or {}
        for key in ("level_transitions", "added", "removed"):
            if key not in change:
                a_errors.append(f"差异缺 {key}")
        for tr in change.get("level_transitions") or []:
            if tr.get("code") not in cap_by_code:
                a_errors.append(f"差异能力未知 {tr.get('code')}")
        health = analytics.get("health") or {}
        dims = health.get("dimensions") or {}
        if set(dims) != set(HEALTH_DIMENSION_WEIGHTS):
            a_errors.append("健康度维度集合不符")
        weighted = 0.0
        for name, row in dims.items():
            score, weight = row.get("score"), row.get("weight")
            if not isinstance(score, (int, float)) or not 0 <= score <= 100:
                a_errors.append(f"{name}:分数越界 {score}")
                continue
            if abs(float(weight) - HEALTH_DIMENSION_WEIGHTS.get(name, -1)) > 1e-9:
                a_errors.append(f"{name}:权重不符")
            weighted += float(score) * float(weight)
        if abs(round(weighted, 1) - float(health.get("overall", -1))) > 0.15:
            a_errors.append(f"overall 不符：记录={health.get('overall')} 实算={round(weighted, 1)}")
        summary_dims = (cm.get("summary") or {}).get("health_dimensions") or {}
        expected_summary = {k: v.get("score") for k, v in dims.items()}
        if summary_dims != expected_summary:
            a_errors.append("summary.health_dimensions 与分析层不一致")
        for action in analytics.get("recommended_actions") or []:
            if action.get("code") not in cap_by_code:
                a_errors.append(f"推荐行动能力未知 {action.get('code')}")
            if float(action.get("health_gain", -1)) < 0:
                a_errors.append(f"推荐增益非法 {action.get('code')}")
        for task in cm.get("next_queue") or []:
            if "health_impact" in task and float(task["health_impact"]) < 0:
                a_errors.append(f"队列增益非法 {task.get('code')}")
        add("analytics_maturity_valid", not a_errors,
            (f"序列 {len(maturity)} 条 · 增益 {len(analytics.get('recommended_actions') or [])} 项"
             if not a_errors else f"错误={a_errors[:5]}"))

    # 29. D3 投影（v2.12.0）：追溯树与时间轴是导航索引，不能被手改成第二事实源。
    #     新字段缺失视为旧账本 na；一旦启用，逐节点与当前账本对照。
    if not isinstance(analytics, dict) or not isinstance(analytics.get("lineage"), dict):
        add("analytics_d3_projection_valid", True,
            "未启用 D3 追溯投影（旧账本）", status="na")
    else:
        from build_capability_model import LINEAGE_SCHEMA  # 局部导入，兼容旧脚本

        d_errors: list[str] = []
        lineage = analytics.get("lineage") or {}
        if lineage.get("schema") != LINEAGE_SCHEMA:
            d_errors.append(f"lineage schema={lineage.get('schema')}")
        trees = lineage.get("trees") or {}
        known_decisions = {e.get("id") for e in entries if e.get("id")}
        node_count = 0
        for code, tree in trees.items():
            cap = cap_by_code.get(code)
            if cap is None:
                d_errors.append(f"{code}:树指向未知能力")
                continue
            if not isinstance(tree, dict) or tree.get("kind") != "capability":
                d_errors.append(f"{code}:根节点类型错误")
                continue
            ids: set[str] = set()
            stack = [tree]
            states = 0
            while stack:
                node = stack.pop()
                if not isinstance(node, dict):
                    d_errors.append(f"{code}:节点非对象")
                    continue
                node_count += 1
                nid = node.get("id")
                if not nid or nid in ids:
                    d_errors.append(f"{code}:节点 id 缺失或重复 {nid}")
                    continue
                ids.add(nid)
                if node.get("kind") not in ("capability", "decision", "evidence", "state"):
                    d_errors.append(f"{code}:节点 kind 非法 {node.get('kind')}")
                if node.get("kind") == "decision":
                    did = node.get("decision_id")
                    if did not in known_decisions:
                        d_errors.append(f"{code}:决策引用未知 {did}")
                if node.get("kind") == "state":
                    states += 1
                    if (node.get("level") != cap.get("level")
                            or node.get("tier") != cap.get("evidence_tier")):
                        d_errors.append(f"{code}:状态节点≠当前能力")
                children = node.get("children")
                if not isinstance(children, list):
                    d_errors.append(f"{code}:children 非数组 {nid}")
                    continue
                stack.extend(children)
            if states != 1:
                d_errors.append(f"{code}:状态节点数={states}")

        timeline = analytics.get("timeline")
        if not isinstance(timeline, list):
            d_errors.append("时间轴缺失")
        else:
            last_seq = 0
            for point in timeline:
                seq = point.get("seq")
                if not isinstance(seq, int) or seq <= last_seq:
                    d_errors.append(f"时间轴 seq 非递增 {seq}")
                    break
                last_seq = seq
                if not isinstance(point.get("change_count"), int):
                    d_errors.append(f"时间轴 change_count 非法 {seq}")
                    break
        add("analytics_d3_projection_valid", not d_errors,
            (f"追溯树 {len(trees)} 棵 / 节点 {node_count} 个 / 时间轴 "
             f"{len(timeline or [])} 点" if not d_errors else f"错误={d_errors[:5]}"))

    # 30. 目标编排（v2.13.0）：目标是新的事实源一等公民，必须自证方向锁、
    #     预算单调与终态纪律。旧账本无 goals 判 na；一旦启用逐条校验，
    #     专家私自改 description/criteria 会因方向锁不匹配被抓到。
    goals = ledger.get("goals")
    if not isinstance(goals, dict) or not goals.get("items"):
        add("goal_loop_valid", True, "未启用目标编排（旧账本）", status="na")
    else:
        import hashlib as _hl
        import json as _json

        def _lock(desc, crit):
            blob = _json.dumps({"description": desc, "success_criteria": crit},
                               ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return _hl.sha256(blob.encode("utf-8")).hexdigest()

        g_errors: list[str] = []
        if goals.get("schema") != "goals/1":
            g_errors.append(f"goals.schema={goals.get('schema')}")
        seen_ids: set[str] = set()
        for goal in goals.get("items", []):
            if not isinstance(goal, dict):
                g_errors.append("goal 非对象")
                continue
            gid = str(goal.get("goal_id", ""))
            if not gid or gid in seen_ids:
                g_errors.append(f"goal_id 缺失或重复：{gid}")
            seen_ids.add(gid)
            status = goal.get("status")
            if status not in ("active", "paused", "achieved", "deactivated"):
                g_errors.append(f"{gid}:状态非法 {status}")
            mx, cur = goal.get("max_loops"), goal.get("current_loop")
            if not isinstance(mx, int) or isinstance(mx, bool) or not 1 <= mx <= 100:
                g_errors.append(f"{gid}:max_loops 非法 {mx}")
                continue
            if not isinstance(cur, int) or isinstance(cur, bool) or not 0 <= cur <= mx:
                g_errors.append(f"{gid}:current_loop 越界 {cur}/{mx}")
            # 终态纪律：已达成的必须停在合法轮次；失活的可未用尽预算（方向/验证失败）
            if status == "achieved" and cur < 1:
                g_errors.append(f"{gid}:achieved 但 current_loop=0")
            if status in ("achieved", "deactivated") and not goal.get("stop_reason"):
                g_errors.append(f"{gid}:终态缺 stop_reason")
            # 方向锁：当前描述/判据的摘要必须与创建时一致（唯一解入口是 goal-approve）
            expected = _lock(goal.get("description", ""), goal.get("success_criteria", []))
            if expected != goal.get("direction_lock"):
                g_errors.append(f"{gid}:方向锁不匹配（疑似专家改目标）")
            crit = goal.get("success_criteria")
            if not isinstance(crit, list) or not crit:
                g_errors.append(f"{gid}:success_criteria 为空")
            else:
                cids = [str(c.get("id", "")) for c in crit if isinstance(c, dict)]
                if len(cids) != len(crit) or any(not x for x in cids):
                    g_errors.append(f"{gid}:判据 id 缺失/重复")
            # 调整提议字段完整；已批准的提议才允许方向锁变化（锁已在上面核对）
            for p in goal.get("proposals", []):
                if not isinstance(p, dict):
                    g_errors.append(f"{gid}:提议非对象")
                    continue
                if p.get("status") not in ("pending", "approved", "rejected"):
                    g_errors.append(f"{gid}:{p.get('id')} 提议状态非法")
                for key in ("original_goal", "proposed_change", "rationale", "impact"):
                    if not str(p.get(key, "")):
                        g_errors.append(f"{gid}:{p.get('id')} 提议缺 {key}")
                if p.get("status") == "approved" and not p.get("approved_by"):
                    g_errors.append(f"{gid}:{p.get('id')} 已批准但无批准人")
        add("goal_loop_valid", not g_errors,
            (f"目标 {len(seen_ids)} 个 · 均锁方向" if not g_errors
             else f"错误={g_errors[:5]}"))

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
