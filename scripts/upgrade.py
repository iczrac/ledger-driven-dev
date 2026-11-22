#!/usr/bin/env python3
"""治理骨架升级器：把「方法论自身变了」也变成可判定、可回滚的一次动作。

第一性原理
----------
系统的一句话定义是「把项目状态压缩成一份可复算的事实源，并让任何一次动作
都能被判定是否安全」。这句话隐含一个前提：**判定所用的规则本身是不变的**。
现实里规则会变：生成器、校验器、测试报告脚本、账本字段都会升级。
v0.9.0 只做了 `ledger_version` 的 fail-closed，于是已有项目面临三难：
  - 工具副本悄悄落后于模板，账本却仍然自称可信；
  - 升级动作没有计划、备份与回滚，只能手工覆盖文件；
  - 升级改了工具源码 → `evidence_binding` 失效 → `verified` 静默回落 `declared`，
    而没有任何流程提醒重新取证。

本脚本把升级拆成六个阶段，全部可只读预演：

    PLAN → SNAPSHOT → APPLY → VERIFY → RE-BASELINE → AUDIT

版本七轴（缺一不可）
--------------------
    method_version   方法论/工具链版本（本文件 METHOD_VERSION），写进账本
    ledger_version   账本数据契约版本（1.0）；不兼容时只 fail-closed，不猜迁移
    tool hashes      6 个工具副本的 sha256，与 templates/ scripts/ 逐一比对
    method_assets    专家/技能/路由/模板/文档整包摘要；资产升级必须重新批准
    board_skeleton   去 EMBED 后的看板骨架 sha256；统一 CSS/DOM/JS，禁止项目改版
    installed_assets 项目级 .workbuddy/ 内已安装副本的逐文件摘要；缺失/手改即判不可用
    ontology_digest  本体投影的只读摘要；权威源字节变了就必须重新绑定

正文里的计数以本文件的常量为准，由 scripts/acceptance.py 的验收契约门禁校验，
不要在文档里凭记忆手抄数字。

v1.2.0 的边界变化
------------------
v1.1.0 刻意「不把资产复制进项目」，只绑摘要；结果 Agent 在项目里没有可用技能。
v1.2.0 改为**只读部署副本**：权威源仍是方法论仓库 tag，安装产物逐字节一致、
由 manifest + 账本字段双重校验、禁止在项目内编辑，因此不产生第二事实源。

v1.7.0 的可适配性收敛
----------------------
升级后流程里的取证命令对无 tests/ 目录、无实测报告的项目降级为显式 na 与
可审计 skip 记录，绝不生成报告；M8 在这类项目上写入
``governance_meta.activation`` 占位（非 null），把「证据能力未激活」从缺失字段
变成可判定的账本事实。迁移集合与升级后流程的长度保持不变，验收由
``scripts/acceptance.py`` 的第四层机器断言判定。

纪律
----
1. plan 只读、确定性，不产生时间戳；apply 才允许写，且必须人批准；
2. 迁移只允许**加字段**，不改写 entries / history / capability_model；
3. 每次 apply 先做带清单的备份，可 rollback；账本内 upgrade_log append-only；
4. 升级不是「结束」：必须按 post_upgrade 重新绑定证据并跑全套门禁；
5. 不新建第二事实源：版本、迁移记录、备份索引都在账本内 governance_meta。

用法
----
    python3 scripts/upgrade.py --target P plan --json
    python3 scripts/upgrade.py --target P apply --approved-by 张三
    python3 scripts/upgrade.py --target P verify --json
    python3 scripts/upgrade.py --target P rollback --backup-id <id> --approved-by 张三
    python3 scripts/upgrade.py check

输出 schema: upgrade-plan/1 · upgrade-apply/1 · upgrade-verify/1。
退出码：0 成功；1 被拒绝；2 输入错误 / 定义自检失败 / verify 有 block。
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

from ledger_io import (board_synced, load_ledger, sha256_bytes, sha256_file,
                       write_ledger)  # noqa: E402
from scenario_guard import _binding_fresh  # noqa: E402
from board_contract import check as board_check  # noqa: E402
from board_contract import normalize_board, template_digest  # noqa: E402
from method_assets import check as assets_check  # noqa: E402
from method_assets import manifest as assets_manifest  # noqa: E402
from asset_bundle import (bundle as installed_bundle,  # noqa: E402
                          check_definitions as installed_check,
                          install as install_assets,
                          install_plan as installed_plan,
                          ledger_binding as installed_binding,
                          verify as installed_verify)
from work_panel import check as work_panel_check  # noqa: E402
from work_panel import test_results_from_report  # noqa: E402
from test_modules import validate as test_modules_validate  # noqa: E402
from ontology import expected_digest  # noqa: E402

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PLAN = "upgrade-plan/1"
SCHEMA_APPLY = "upgrade-apply/1"
SCHEMA_VERIFY = "upgrade-verify/1"
METHOD_VERSION = "2.19.0"


def _version_tuple(value) -> tuple[int, ...]:
    """语义版本比较：避免把 2.10.0 当成「小于」2.9.0 的字符串比较。"""
    parts = tuple(int(x) for x in re.findall(r"\d+", str(value))[:3])
    return parts or (0,)
LEDGER_SCHEMA_VERSION = "1.0"
SUPPORTED_LEDGER_VERSIONS = {"1.0"}
ACCESS_SCHEMA = "access/1"
BACKUP_ROOT = ".ledger-upgrade/backups"

# 目标项目内的相对路径 → 方法论仓库内的权威来源
TOOLING: dict[str, str] = {
    "governance/build_capability_model.py": "templates/build_capability_model.py",
    "governance/binding_advisory.py": "templates/binding_advisory.py",
    "governance/derived_issues.py": "templates/derived_issues.py",
    "governance/verify_ledger.py": "templates/verify_ledger.py",
    "governance/registry_codec.py": "templates/registry_codec.py",
    "governance/run_tests.py": "scripts/run_tests.py",
    # v2.12.0：本地 D3 随方法版本下发，file:// 下不访问 CDN。
    "governance/vendor/d3.v7.min.js": "templates/vendor/d3.v7.min.js",
}

# 迁移只允许新增字段。任何需要改写历史/条目的迁移都必须另写人工方案。
MIGRATIONS: list[dict] = [
    dict(id="M1-governance-meta", field="governance_meta", kind="ledger-field",
         name="写入版本与迁移元数据", approval=True,
         note="纯新增字段，不改 entries / history / capability_model"),
    dict(id="M2-access-registry", field="access", kind="ledger-field",
         name="建立默认拒绝的 Agent 接入登记", approval=True,
         note="agents=[] / leases=[] / audit=[] / revision=0；升级是接入控制的前置条件"),
    dict(id="M3-tool-sync", field="", kind="tool-sync",
         name="同步 6 个工具副本到权威模板", approval=False,
         note="先备份；副本内容变化会让 evidence_binding 过期，必须重新取证"),
    dict(id="M4-method-version", field="", kind="meta-refresh",
         name="刷新 method_version 与工具摘要", approval=False,
         note="只在 M1 之后运行；记录本次升级后的 3 个 sha256"),
    dict(id="M5-method-assets", field="governance_meta.method_assets", kind="meta-refresh",
         name="绑定整包方法论资产摘要（专家/技能/模板/文档/路由）", approval=False,
         note="整包摘要随仓库 tag 升级、权威源不复制；专家/技能可用副本由 M7 安装"),
    dict(id="M6-board-skeleton", field="governance_meta.board_skeleton", kind="board-normalize",
         name="用权威模板重建看板骨架（CSS/DOM/JS）", approval=True,
         note="只换骨架，数据段仍是当前账本；禁止项目自定义版面"),
    dict(id="M7-asset-install", field="governance_meta.installed_assets", kind="asset-install",
         name="安装专家/技能到项目级 .workbuddy/ 并绑定逐文件摘要", approval=True,
         note="只读部署副本，权威源仍是方法论仓库；项目内手改副本会被 verify 判漂移"),
    dict(id="M8-work-panel", field="work_items / test_results", kind="ledger-field",
         name="初始化节点工作台字段（TODO / issue / 测试结果投影）", approval=False,
         note="只新增空数组与可验证投影；无实测报告时不写 test_results（v1.3.0 起不再永久 pending）；"
              "v1.7.0 起同时写 governance_meta.activation 占位，明示证据能力未激活"),
    dict(id="M9-goals", field="goals", kind="ledger-field",
         name="初始化目标编排字段（goals/1：目标对象 + 方向锁 + 预算）", approval=False,
         note="只新增空 items 数组；目标由人经 agent_gateway goal-create 创建，"
              "AI 不得自批准；第 30 条不变量 goal_loop_valid 负责方向锁与预算纪律"),
]

# v1.4.0：基线不可后补。升级动作之前先导出一次观察包，才能 diff 出升级带来的改善。
# 这条是「反向回流」闭环的入口，不属于升级后流程。
PRE_UPGRADE: list[str] = [
    "python3 scripts/ledger_feedback.py export --target P "
    "--out feedback/baseline.jsonl --phase baseline --apply --approved-by <人>",
]

POST_UPGRADE: list[str] = [
    # v1.3.0：报告必须在「目标项目」侧生成，方法论仓库自测由仓库 CI 负责。
    # 非 unittest 技术栈改用 work_panel.py import-report 产出同一份规范报告。
    # v1.7.0：无 tests/ 或无报告的项目降级为显式 na 与可审计 skip 记录，
    # 不得为了让流程继续而伪造报告；skip 输出由 acceptance.py 的负向回归断言。
    "cd P && if [ -d tests ]; then python3 governance/run_tests.py --dir tests --top . "
    "--out governance/test_report.json --label project; "
    "else echo 'SKIP step=1 status=na reason=no-tests-dir'; fi",
    "cd P && if [ -f governance/test_report.json ]; then "
    "python3 governance/build_capability_model.py --root . "
    "--test-report governance/test_report.json --strict-evidence; "
    "else echo 'SKIP step=2 status=na reason=no-report'; fi",
    "cd P && python3 governance/verify_ledger.py --root . --strict",
    "python3 scripts/upgrade.py --target P verify --json",
    "python3 scripts/board_contract.py --target P check --json",
    "python3 scripts/scale_budget.py --target P --json --check",
    "python3 scripts/method_assets.py --check",
    "python3 scripts/scenario_guard.py --target P --strict",
    "python3 scripts/file_layout.py --diff --target P --strict",
    "python3 scripts/agent_gateway.py --target P status --json",
    "python3 scripts/route_expert.py --target P --intent 校验账本 --json",
    "python3 scripts/asset_bundle.py --check",
    "python3 scripts/asset_bundle.py verify --target P --json",
    "python3 scripts/work_panel.py --target P check --json",
    "if [ -f P/governance/test_report.json ]; then "
    "python3 scripts/work_panel.py --target P sync-tests --apply --approved-by '<人>'; "
    "else echo 'SKIP step=15 status=na reason=no-report'; fi",
    "python3 scripts/work_panel.py --target P nodes --json",
    "python3 scripts/test_modules.py --check",
    "python3 scripts/route_expert.py --target P --check-assets --json",
    # v1.4.0：第 19 步把本次升级的真实摩擦回流到方法论仓库，供 triage 成四产物。
    "python3 scripts/ledger_feedback.py export --target P "
    "--out feedback/observations.jsonl --phase after-upgrade --apply --approved-by <人>",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tool_rows(target: Path, source_root: Path = SOURCE_ROOT) -> list[dict]:
    rows = []
    for rel, src_rel in TOOLING.items():
        src = source_root / src_rel
        dst = target / rel
        expected = sha256_file(src) if src.is_file() else None
        current = sha256_file(dst) if dst.is_file() else None
        state = ("in-sync" if current == expected and current is not None else
                 "missing" if current is None else "drifted")
        rows.append({"path": rel, "source": src_rel, "state": state,
                     "current_sha256": current, "expected_sha256": expected})
    return rows


def _meta_template(from_method: str) -> dict:
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "upgraded_from": from_method,
        "ledger_version": LEDGER_SCHEMA_VERSION,
        "migrations_applied": [],
        "upgrade_log": [],
        "tools": {},
    }


def _access_template() -> dict:
    return {"schema": ACCESS_SCHEMA, "revision": 0,
            "agents": [], "leases": [], "audit": []}


def _projection_stale(gov: Path, ledger: dict) -> bool:
    """判 M8 的理由之一：报告存在但投影缺失 / 过期。

    另两个理由在 plan() 里：work_items 键缺失、governance_meta.activation
    占位缺失。无报告本身不是待办：旧判定把 test_results 键缺失当作待办，
    而 apply 在没有报告时又不写该键，于是每次 plan 都判 M8、noop 永假。
    无报告是合法的 declared 状态（E2），证据未激活由校验器的 na 态与
    activation 占位共同明示。
    """
    report = gov / "test_report.json"
    if not report.is_file():
        return False
    tr = ledger.get("test_results")
    if not isinstance(tr, dict):
        return True
    return tr.get("source_sha256") != sha256_file(report)


def plan(target: Path, source_root: Path = SOURCE_ROOT) -> dict:
    """只读、确定性的升级计划。不写任何文件，不含时间戳。"""
    target = Path(target)
    gov = target / "governance"
    blocks: list[dict] = []
    ledger: dict = {}
    try:
        ledger = load_ledger(gov)
    except ValueError as exc:
        blocks.append(dict(id="ledger_unreadable", reason=str(exc),
                           fix="先备份并人工修复账本；损坏状态下禁止升级"))
        ledger = {}

    meta = ledger.get("governance_meta") if isinstance(ledger.get("governance_meta"), dict) else {}
    from_method = str(meta.get("method_version") or "pre-1.0.0")
    ledger_version = str(ledger.get("ledger_version", LEDGER_SCHEMA_VERSION))
    lifecycle = ledger.get("lifecycle") if isinstance(ledger.get("lifecycle"), dict) else {}
    lc_state = str(lifecycle.get("state", "active"))

    if ledger and ledger_version not in SUPPORTED_LEDGER_VERSIONS:
        blocks.append(dict(id="unsupported_ledger_version",
                           reason=f"账本数据契约 {ledger_version} 不在支持集合 "
                                  f"{sorted(SUPPORTED_LEDGER_VERSIONS)}",
                           fix="fail-closed：先导出快照，写专用数据迁移并人工确认，本脚本不猜结构"))
    if ledger and lc_state != "active":
        blocks.append(dict(id="lifecycle_not_writable",
                           reason=f"生命周期为 {lc_state}，升级属于写入动作",
                           fix="由人批准 unfreeze 后再升级；归档项目请复制出新项目"))
    if ledger and _version_tuple(meta.get("method_version", METHOD_VERSION)) > _version_tuple(METHOD_VERSION):
        blocks.append(dict(id="future_method_version",
                           reason=f"账本由更新的方法论 {meta['method_version']} 写入",
                           fix="升级方法论仓库本身，不要用旧工具降级写新账本"))

    rows = tool_rows(target, source_root)
    assets = assets_manifest(source_root)
    bcheck = board_check(target, source_root)
    inst = installed_plan(target, source_root)
    recorded_assets = (meta.get("method_assets")
                       if isinstance(meta.get("method_assets"), dict) else {})
    needed: list[dict] = []
    if ledger:
        if "governance_meta" not in ledger:
            needed.append(MIGRATIONS[0])
        if "access" not in ledger:
            needed.append(MIGRATIONS[1])
        if any(r["state"] != "in-sync" for r in rows):
            needed.append(MIGRATIONS[2])
        if meta.get("method_version") != METHOD_VERSION:
            needed.append(MIGRATIONS[3])
        if recorded_assets.get("digest") != assets["digest"]:
            needed.append(MIGRATIONS[4])
        if not bcheck["match"]:
            needed.append(MIGRATIONS[5])
        if not inst["noop"]:
            needed.append(MIGRATIONS[6])
        activation = meta.get("activation") if isinstance(meta, dict) else None
        if ("work_items" not in ledger or _projection_stale(gov, ledger)
                or not isinstance(activation, dict)):
            needed.append(MIGRATIONS[7])
        goals = ledger.get("goals")
        if not isinstance(goals, dict) or goals.get("schema") != "goals/1":
            needed.append(MIGRATIONS[8])

    noop = bool(ledger) and not needed and not blocks
    risk = ("blocked" if blocks else
            "none" if noop else
            "medium" if any(m["kind"] in ("tool-sync", "board-normalize", "asset-install")
                            for m in needed) else "low")
    writes = ["governance/DECISION_LEDGER.json", "governance/index.html"]
    if any(m["kind"] == "tool-sync" for m in needed):
        writes += [r["path"] for r in rows if r["state"] != "in-sync"]
    if any(m["kind"] == "asset-install" for m in needed):
        writes += inst["changes"] + ["governance/ASSET_MANIFEST.json"]
    return {
        "schema": SCHEMA_PLAN,
        "target": ".",
        "from_method": from_method,
        "to_method": METHOD_VERSION,
        "ledger_version": ledger_version,
        "lifecycle": lc_state,
        "migrations": [{"id": m["id"], "name": m["name"], "kind": m["kind"],
                        "requires_approval": m["approval"], "note": m["note"]}
                       for m in needed],
        "tools": rows,
        "assets": {"digest": assets["digest"], "file_count": assets["file_count"],
                   "counts": assets["counts"], "recorded_digest": recorded_assets.get("digest")},
        "board": {"match": bcheck["match"], "template_digest": bcheck["template_digest"],
                  "board_digest": bcheck["board_digest"], "reason": bcheck["reason"]},
        "installed": {"noop": inst["noop"], "digest": inst["digest"],
                      "file_count": inst["file_count"], "counts": inst["counts"],
                      "missing": inst["missing"], "drifted": inst["drifted"],
                      "stale_protected": inst["stale_protected"]},
        "blocks": blocks,
        "noop": noop,
        "risk": risk,
        "backup": {"root": BACKUP_ROOT,
                   "files": ["governance/DECISION_LEDGER.json", "governance/index.html",
                             "governance/registry.json", *TOOLING,
                             "governance/ASSET_MANIFEST.json",
                             *[r["path"] for r in installed_bundle(source_root)["files"]]],
                   "manifest": "manifest.json"},
        "writes": writes,
        "pre_upgrade": [] if noop else list(PRE_UPGRADE),
        "post_upgrade": [] if noop else list(POST_UPGRADE),
        "approval_required": True,
    }


def _safe_rel(rel: str, target: Path) -> Path:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"备份清单含不安全路径：{rel}")
    return target / p


def _snapshot(target: Path, ledger_bytes: bytes, p: dict) -> str:
    """落盘备份；返回不含绝对路径的备份 id。"""
    bid = _now().replace("-", "").replace(":", "") + "-" + sha256_bytes(ledger_bytes)[:8]
    dest = target / BACKUP_ROOT / bid
    dest.mkdir(parents=True, exist_ok=False)
    manifest: dict = {"schema": "upgrade-backup/1", "backup_id": bid,
                      "from_method": p["from_method"], "to_method": p["to_method"],
                      "created_at": _now(), "files": [], "created": []}
    for rel in p["backup"]["files"]:
        src = _safe_rel(rel, target)
        if not src.is_file():
            manifest["created"].append(rel)  # 升级前不存在；回滚时按白名单移除
            continue
        out = _safe_rel(rel, dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
        manifest["files"].append({"path": rel, "sha256": sha256_file(src)})
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return bid


def apply(target: Path, approved_by: str, *,
          source_root: Path = SOURCE_ROOT, p: dict | None = None) -> dict:
    """应用升级：人批准 → 备份 → 加字段 → 同步工具 → 记录 append-only 日志。"""
    if not approved_by:
        raise ValueError("升级必须提供 --approved-by（人工批准）；AI 不得自行升级治理骨架")
    target = Path(target)
    p = p or plan(target, source_root)
    if p["blocks"]:
        raise ValueError("升级被前置条件阻止：" + "；".join(b["id"] for b in p["blocks"]))
    if p["noop"]:
        return {"schema": SCHEMA_APPLY, "noop": True,
                "message": f"已是 v{METHOD_VERSION} 且工具/资产/骨架一致，无需写入"}

    gov = target / "governance"
    ledger = load_ledger(gov)
    raw = (gov / "DECISION_LEDGER.json").read_bytes()
    bid = _snapshot(target, raw, p)
    ids = [m["id"] for m in p["migrations"]]

    meta = ledger.get("governance_meta") if isinstance(ledger.get("governance_meta"), dict) else None
    if "M1-governance-meta" in ids:
        meta = _meta_template(p["from_method"])
        ledger["governance_meta"] = meta
    if meta is None:
        meta = ledger["governance_meta"] = _meta_template(p["from_method"])
    if "M2-access-registry" in ids:
        ledger["access"] = _access_template()

    for row in p["tools"]:
        if row["state"] == "in-sync":
            continue
        src = source_root / row["source"]
        dst = target / row["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    # 骨架归一：统一快照已备份 index.html，这里不再重复备份；
    # 只换 CSS/DOM/JS 骨架，数据段随后由 write_ledger 用最终账本同步。
    if "M6-board-skeleton" in ids:
        normalize_board(gov, ledger, source_root,
                        approved_by=approved_by, apply=True, backup_root=None)

    # M7：把专家/技能安装成项目内可直接加载的只读副本，再绑定摘要。
    # 统一快照已包含安装清单与副本路径，这里不重复备份、也不单独改账本。
    if "M7-asset-install" in ids:
        install_assets(target, approved_by=approved_by, apply=True,
                       source_root=source_root, bind_ledger=False)
    if "M8-work-panel" in ids:
        ledger.setdefault("work_items", [])
        if "test_results" not in ledger:
            projection = test_results_from_report(gov)
            if projection is not None:
                ledger["test_results"] = projection
        # v1.7.0：无报告不写 test_results，但必须写显式 activation 占位；
        # null 会把「证据能力未激活」与「字段尚未升级」混为一谈。
        if not isinstance(meta.get("activation"), dict):
            meta["activation"] = {
                "schema": "evidence-activation/1",
                "state": "unbound",
                "reason": "目标项目无 governance/test_report.json，证据能力未激活",
                "all_active": False,
            }
    if "M9-goals" in ids:
        # 只建空容器；目标由人经网关 goal-create 创建，升级本身不替人定目标。
        goals = ledger.get("goals")
        if not isinstance(goals, dict):
            goals = {}
        goals["schema"] = "goals/1"
        goals.setdefault("items", [])
        ledger["goals"] = goals

    assets = assets_manifest(source_root)
    meta["method_version"] = METHOD_VERSION
    meta["ledger_version"] = str(ledger.get("ledger_version", LEDGER_SCHEMA_VERSION))
    meta["schema_version"] = LEDGER_SCHEMA_VERSION
    meta["tools"] = {r["path"]: r["expected_sha256"] for r in p["tools"]}
    meta["method_assets"] = {
        "algorithm": assets["algorithm"], "digest": assets["digest"],
        "file_count": assets["file_count"], "counts": assets["counts"],
        "source": "方法论仓库 tag（权威源，不复制；只读副本由 M7 安装）",
    }
    # 第七轴：本体投影摘要。只存可复算的 digest，不复制本体内容；
    # ontology.py check --target P 会重算比对，删光派生文件也能复原。
    meta["ontology_digest"] = expected_digest(source_root)
    meta["board_skeleton"] = {
        "digest": template_digest(source_root),
        "source": "templates/index.html.template",
        "note": "去 EMBED 后的骨架 sha256；禁止在项目内自定义版面",
    }
    meta["installed_assets"] = installed_binding(source_root)
    applied = list(dict.fromkeys((meta.get("migrations_applied") or []) + ids))
    meta["migrations_applied"] = applied
    log = meta.setdefault("upgrade_log", [])
    log.append({"seq": len(log) + 1, "at": _now(), "action": "apply",
                "from": p["from_method"], "to": METHOD_VERSION,
                "approved_by": approved_by, "migrations": ids,
                "backup": bid, "risk": p["risk"],
                "assets_digest": assets["digest"][:16],
                "board_skeleton": meta["board_skeleton"]["digest"][:16]})
    write_ledger(gov, ledger)
    return {"schema": SCHEMA_APPLY, "noop": False, "backup": bid,
            "from": p["from_method"], "to": METHOD_VERSION,
            "migrations": ids, "approved_by": approved_by,
            "message": "升级完成；必须继续跑 post_upgrade 重新绑定证据并复验"}


def verify(target: Path, source_root: Path = SOURCE_ROOT) -> dict:
    """升级后只读复验：回答「现在能不能声明升级成功」。"""
    target = Path(target)
    gov = target / "governance"
    checks: list[dict] = []

    def add(cid: str, status: str, detail: str, fix: str = "") -> None:
        checks.append({"id": cid, "status": status, "detail": detail, "fix": fix})

    try:
        ledger = load_ledger(gov)
    except ValueError as exc:
        add("ledger_readable", "block", str(exc), "从备份 rollback 或人工修复")
        ledger = {}
    else:
        add("ledger_readable", "pass", "账本可解析")
        ver = str(ledger.get("ledger_version", LEDGER_SCHEMA_VERSION))
        add("ledger_version", "pass" if ver in SUPPORTED_LEDGER_VERSIONS else "block",
            f"数据契约 {ver}",
            "" if ver in SUPPORTED_LEDGER_VERSIONS else "fail-closed，禁止写入")

        meta = ledger.get("governance_meta") or {}
        mv = str(meta.get("method_version", "未标注"))
        add("method_version", "pass" if mv == METHOD_VERSION else "warn",
            f"方法论版本 {mv}",
            "" if mv == METHOD_VERSION else "运行 upgrade.py apply --approved-by <人>")

        rows = tool_rows(target, source_root)
        bad = [r["path"] for r in rows if r["state"] != "in-sync"]
        add("tool_hashes", "pass" if not bad else "warn",
            f"{len(TOOLING)} 个工具副本与权威模板一致" if not bad else "副本漂移：" + ", ".join(bad),
            "" if not bad else "重新运行 upgrade.py apply 同步副本")

        bs = board_synced(gov, ledger)
        add("board_synced", "pass" if bs is not False else "block",
            "看板 EMBED 与账本一致" if bs else "看板缺失或与账本不一致",
            "" if bs is not False else "重跑生成器或 write_ledger 同步")

        acc = ledger.get("access") or {}
        add("access_schema", "pass" if acc.get("schema") == ACCESS_SCHEMA else "warn",
            f"接入登记 {acc.get('schema', '缺失')}",
            "" if acc.get("schema") == ACCESS_SCHEMA else "升级会建立默认拒绝的 access 登记")

        want_assets = assets_manifest(source_root)["digest"]
        rec = meta.get("method_assets") if isinstance(meta.get("method_assets"), dict) else {}
        got_assets = rec.get("digest")
        add("method_assets", "pass" if got_assets == want_assets else "warn",
            "专家/技能/模板/文档资产摘要一致" if got_assets == want_assets else
            f"资产漂移：项目记录 {str(got_assets)[:12] or '缺失'} / 仓库 {want_assets[:12]}",
            "" if got_assets == want_assets else
            "方法论资产已升级；重新 plan → 人批准 apply → 复验")

        bcheck = board_check(target, source_root)
        add("board_skeleton", "pass" if bcheck["match"] else "warn",
            "看板骨架与权威模板一致" if bcheck["match"] else bcheck["reason"],
            "" if bcheck["match"] else
            "board_contract.py normalize 或 upgrade.py apply（禁止手改 CSS/DOM）")

        iv = installed_verify(target, source_root)
        add("installed_assets", "pass" if iv["ok"] else "warn",
            f"项目级专家/技能副本 {iv['file_count']} 个，摘要 {iv['digest'][:12]}"
            if iv["ok"] else
            "资产不可用：" + "；".join(e["reason"] for e in iv["errors"][:3]),
            "" if iv["ok"] else iv["hint"])

        # 第七轴：本体是可丢弃重建的派生投影，账本只存 digest，校验靠复算。
        want_ontology = expected_digest(source_root)
        got_ontology = meta.get("ontology_digest")
        if got_ontology is None:
            add("ontology_binding", "na",
                "目标项目尚未绑定 ontology_digest（升级后由 M5 写入）",
                "python3 scripts/upgrade.py --target P apply --approved-by <人>")
        elif got_ontology == want_ontology:
            add("ontology_binding", "pass", "本体投影摘要与权威源一致")
        else:
            add("ontology_binding", "warn",
                f"本体投影漂移：项目 {str(got_ontology)[:12]} / 权威源 {want_ontology[:12]}",
                "重新 plan → 人批准 apply → 复验")

        wp = work_panel_check(target)
        add("work_panel", "pass" if wp["ok"] else "warn",
            f"节点工作态自洽（{wp.get('work_items', 0)} 工作项 / "
            f"{wp.get('test_cases', 0)} 用例）" if wp["ok"] else
            "工作台字段不自洽：" + "；".join(wp["errors"][:3]),
            "" if wp["ok"] else "python3 scripts/work_panel.py --target P check --json")

        report_path = gov / "test_report.json"
        if report_path.is_file():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                report = {}
            fresh, why = _binding_fresh(report, target, "")
            if report.get("overall") != "pass":
                add("evidence_rebaseline", "warn", "实测报告未通过", "修复用例后重跑报告")
            elif fresh is False:
                add("evidence_rebaseline", "warn", f"证据摘要已过期（{why}）",
                    "重跑 run_tests.py 后用 --strict-evidence 重新生成账本")
            elif fresh is None:
                add("evidence_rebaseline", "warn", "报告未绑定源码摘要", "用当前 run_tests.py 重跑")
            else:
                add("evidence_rebaseline", "pass", "证据与当前源码一致")
        else:
            # 无报告 = 证据能力未激活，不是「升级完成且证据已验证」。
            # 用 na 明示，避免把全部 declared 的项目算进「证据复验通过」。
            add("evidence_rebaseline", "na",
                "无实测报告：能力仍为 declared，证据复验未启用",
                "接上项目侧测试报告后重跑本项；可用 work_panel.py import-report")

    blocked = any(c["status"] == "block" for c in checks)
    return {"schema": SCHEMA_VERIFY, "target": ".", "checks": checks,
            "summary": {"pass": sum(c["status"] == "pass" for c in checks),
                        "warn": sum(c["status"] == "warn" for c in checks),
                        "na": sum(c["status"] == "na" for c in checks),
                        "block": sum(c["status"] == "block" for c in checks)},
            "upgrade_complete": not blocked and all(
                # na 表示能力未启用，不阻止「升级动作已完成」的判定；
                # 但 upgrade_complete 不等于「证据已激活」。
                c["status"] in ("pass", "na") for c in checks
                if c["id"] in ("method_version", "tool_hashes", "access_schema",
                               "method_assets", "board_skeleton", "ontology_binding",
                               "installed_assets", "work_panel",
                               "evidence_rebaseline")),
            "post_upgrade_required": list(POST_UPGRADE),
            "overall": "block" if blocked else "pass"}


def rollback(target: Path, backup_id: str, approved_by: str) -> dict:
    if not approved_by:
        raise ValueError("回滚必须提供 --approved-by（人工批准）")
    if not re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", backup_id or ""):
        raise ValueError("备份 id 格式非法")
    target = Path(target)
    bdir = target / BACKUP_ROOT / backup_id
    manifest_path = bdir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"找不到备份 {backup_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("files", []):
        src = _safe_rel(str(item["path"]), bdir)
        dst = _safe_rel(str(item["path"]), target)
        if not src.is_file():
            raise ValueError(f"备份缺文件：{item['path']}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    # 升级前不存在的安装产物，回滚时按白名单移除；不碰用户自己的 .workbuddy 文件
    for rel in manifest.get("created", []):
        if not (str(rel).startswith(".workbuddy/") or
                str(rel) == "governance/ASSET_MANIFEST.json"):
            continue
        p = _safe_rel(str(rel), target)
        if p.is_file():
            p.unlink()
    gov = target / "governance"
    # 回滚回执写在备份目录（运行时层），不进 governance/；
    # 它记录「谁批准了这次恢复」，但不含项目状态，因此不是第二事实源。
    (bdir / "rollback-receipt.json").write_text(json.dumps(
        {"schema": "upgrade-rollback-receipt/1", "backup_id": backup_id,
         "at": _now(), "approved_by": approved_by,
         "restored": [str(i["path"]) for i in manifest.get("files", [])]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    # 备份账本若本来就有 governance_meta（升级到一半再回滚），补记一条日志；
    # 若备份是升级前状态，则账本严格恢复原样，不为了留痕而改写历史。
    try:
        ledger = load_ledger(gov)
        meta = ledger.get("governance_meta")
        if isinstance(meta, dict):
            log = meta.setdefault("upgrade_log", [])
            log.append({"seq": len(log) + 1, "at": _now(), "action": "rollback",
                        "backup": backup_id, "approved_by": approved_by})
            write_ledger(gov, ledger)
    except ValueError:
        pass
    return {"schema": SCHEMA_APPLY, "action": "rollback", "backup": backup_id,
            "restored": [str(i["path"]) for i in manifest.get("files", [])],
            "approved_by": approved_by,
            "message": "已回滚（回执写入备份目录）；请重新跑 verify 与 post_upgrade"}


def check_definitions(source_root: Path = SOURCE_ROOT) -> list[str]:
    errs: list[str] = []
    if not re.fullmatch(r"\d+\.\d+\.\d+", METHOD_VERSION):
        errs.append("METHOD_VERSION 不符合 SemVer")
    ids = [m["id"] for m in MIGRATIONS]
    if len(ids) != len(set(ids)):
        errs.append("迁移 id 重复")
    for rel, src in TOOLING.items():
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            errs.append(f"工具路径非法：{rel}")
        if not (source_root / src).is_file():
            errs.append(f"权威模板不存在：{src}")
    if not PRE_UPGRADE or "ledger_feedback.py export" not in PRE_UPGRADE[0]:
        errs.append("PRE_UPGRADE 首步必须是基线观察导出")
    for cmd in (*PRE_UPGRADE, *POST_UPGRADE):
        m = re.search(r"scripts/([\w_]+\.py)", cmd)
        if m and not (source_root / "scripts" / m.group(1)).is_file():
            errs.append(f"升级流程引用了不存在的脚本：{m.group(1)}")
    if "ledger_feedback.py export" not in POST_UPGRADE[-1]:
        errs.append("POST_UPGRADE 末步必须导出升级后观察包")
    if not (source_root / "templates" / "index.html.template").is_file():
        errs.append("看板权威模板不存在：templates/index.html.template")
    errs.extend(assets_check(source_root)["errors"])
    errs.extend(installed_check(source_root))
    errs.extend(test_modules_validate(source_root))
    return errs


def _render(result: dict) -> str:
    if result["schema"] == SCHEMA_PLAN:
        lines = [f"升级计划：{result['from_method']} → {result['to_method']} "
                 f"| 风险={result['risk']} | 生命周期={result['lifecycle']}",
                 f"迁移 {len(result['migrations'])} 项：" +
                 (", ".join(m["id"] for m in result["migrations"]) or "无（noop）")]
        for r in result["tools"]:
            lines.append(f"  工具 {r['path']}: {r['state']}")
        lines.append(f"  资产 {result['assets']['file_count']} 个 · 摘要 "
                     f"{result['assets']['digest'][:12]}（项目记录 "
                     f"{str(result['assets']['recorded_digest'])[:12] or '缺失'}）")
        lines.append("  看板骨架 " + ("一致" if result["board"]["match"] else
                                    "漂移 → " + result["board"]["reason"]))
        inst = result["installed"]
        lines.append(f"  可用资产 {inst['file_count']} 个 · 摘要 {inst['digest'][:12]} · "
                     + ("齐备" if inst["noop"] else
                        f"缺 {len(inst['missing'])} / 漂移 {len(inst['drifted'])} → M7"))
        for b in result["blocks"]:
            lines.append(f"  [BLOCK] {b['id']}：{b['reason']} → {b['fix']}")
        if result["post_upgrade"]:
            lines.append("升级后必须依次执行：")
            lines += ["  " + c for c in result["post_upgrade"]]
        return "\n".join(lines)
    if result["schema"] == SCHEMA_VERIFY:
        lines = [f"升级复验：{result['overall']} | upgrade_complete="
                 f"{result['upgrade_complete']}"]
        for c in result["checks"]:
            if c["status"] != "pass":
                lines.append(f"  [{c['status'].upper()}] {c['id']}：{c['detail']}"
                             + (f" → {c['fix']}" if c["fix"] else ""))
        return "\n".join(lines)
    return json.dumps(result, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="被治理项目根目录")
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply", "verify", "rollback", "check"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
        p.add_argument("--approved-by", default="", help="人工批准人（apply/rollback 必需）")
        p.add_argument("--backup-id", default="", help="rollback 的备份 id")
        p.add_argument("--source-root", default=str(SOURCE_ROOT),
                       help="方法论仓库根（测试可指向副本）")
    args = ap.parse_args(argv)

    if args.command == "check":
        errs = check_definitions(Path(args.source_root))
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 2
        print(f"升级定义自检通过：{len(TOOLING)} 个工具 / {len(MIGRATIONS)} 条迁移 / "
              f"{len(PRE_UPGRADE)} 步升级前基线 / {len(POST_UPGRADE)} 步升级后流程")
        return 0

    target = Path(args.target).expanduser().resolve()
    source_root = Path(args.source_root).expanduser().resolve()
    if not target.is_dir():
        print("目标目录不存在", file=sys.stderr)
        return 2
    try:
        if args.command == "plan":
            result = plan(target, source_root)
            rc = 2 if result["blocks"] else 0
        elif args.command == "apply":
            result = apply(target, args.approved_by, source_root=source_root)
            rc = 0
        elif args.command == "verify":
            result = verify(target, source_root)
            rc = 2 if result["overall"] == "block" else 0
        else:
            result = rollback(target, args.backup_id, args.approved_by)
            rc = 0
    except ValueError as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
          if args.json else _render(result))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
