#!/usr/bin/env python3
"""本体投影层：把散落在代码与文档里的隐式本体收成可机器校验的派生契约。

第一性原理
----------
这套系统早就在回答本体的四个问题（什么东西存在 / 能取什么值 / 怎么连 /
什么必然为真），只是答案散在四段式编码、L0-L5、26 条不变量、9 套状态机里。
问题不是「要不要有本体」，而是「要不要把答案收成一份可复算的元契约」。

本脚本**不产生新事实**：

    ONTOLOGY = f(权威源)      # docs/STANDARD.md + 各脚本枚举 + 校验器不变量 id
    verify 重算 f 并比对      # 可丢弃重建，删光派生文件也能逐字节复原

因此它不是第二事实源，也不写入账本内容；账本里只存一个 `ontology_digest`
（由 `upgrade.py apply` 在 M5 分支写入），由本脚本 `check --target P` 复算校验。

三条漂移
--------
* `polyseme_violation`     裸 `status` 等词跨实体未限定为 `<Type>.field`
* `cardinality_contradiction` registry 声明单项目而能力模型含 1..N 个项目
* `undeclared_entity` / `undeclared_value`  未声明的顶层键或状态取值

漂移可导出为 `ledger-observations/1` 观察（affected_axis=ontology），
走 v1.4.0 已建好的四产物 triage 闭环。

纪律
----
1. 纯标准库、只读权威源、无时间戳 / 绝对路径 / 项目名词；
2. `build` 确定性：同一目录两次输出同一 digest；
3. 写派生文件需 `--apply --approved-by <人>`；`diff --target` 绝不写目标项目；
4. 不引入 OWL / RDF / 图数据库；TBox 是 JSON，推理是确定性 Python 规则。

用法
----
    python3 scripts/ontology.py build --json
    python3 scripts/ontology.py build --apply --approved-by 张三
    python3 scripts/ontology.py check --json
    python3 scripts/ontology.py check --target P --json
    python3 scripts/ontology.py diff --target P --json
    python3 scripts/ontology.py diff --target P --out feedback/observations.jsonl \
        --apply --approved-by 张三
    python3 scripts/ontology.py emit-md --stdout
    python3 scripts/ontology.py digest --json

退出码：0 成功；1 校验失败 / 被拒绝；2 输入错误。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ledger-ontology/1"
SCHEMA_CHECK = "ledger-ontology-check/1"
OUT_JSON = "docs/generated/ONTOLOGY.json"
OUT_MD = "docs/generated/ONTOLOGY.md"

# 直接来源：只列本体定义真正依赖的文件。生成物 / 版本脚本不进来，避免每次
# 改 METHOD_VERSION 都要重算 ontology_digest。
SOURCE_FILES = (
    ("docs/STANDARD.md", "ubiquitous_language"),
    ("scripts/work_panel.py", "value_domains"),
    ("scripts/scenario_matrix.py", "value_domains"),
    ("scripts/ledger_feedback.py", "value_domains"),
    ("scripts/agent_gateway.py", "value_domains"),
    ("templates/build_capability_model.py", "value_domains"),
    ("templates/verify_ledger.py", "axioms"),
)

BOUNDED_CONTEXTS = (
    {"id": "BC-FACT", "name": "账本事实", "responsibility": "决策 / 能力 / 工作项 / 测试投影",
     "relation": "shared-kernel"},
    {"id": "BC-METHOD", "name": "方法论与版本", "responsibility": "版本 / 迁移 / 资产 / 发布",
     "relation": "published-language"},
    {"id": "BC-VERIFY", "name": "校验与证据", "responsibility": "不变量 / 门禁 / 证据分层",
     "relation": "downstream"},
    {"id": "BC-ADOPT", "name": "目标项目落地", "responsibility": "升级 / 只读副本 / 骨架",
     "relation": "conformist+acl"},
    {"id": "BC-FEEDBACK", "name": "观察与回流", "responsibility": "观察 / triage / 基线 diff",
     "relation": "upstream"},
    {"id": "BC-DOMAIN", "name": "业务领域", "responsibility": "被治理项目 1..N",
     "relation": "consumer"},
)

# 状态词按实体分型，绝不归一。key 是 STANDARD.md 第四章表里的 `<Type>.field`。
# value = (来源文件, 顶层符号, 取值抽取规则)；None 表示只在文档中声明。
OBSERVED_BINDINGS: dict[str, tuple[str, str, str]] = {
    "Capability.level": ("templates/build_capability_model.py", "LEVELS", "L-prefix"),
    "Capability.evidence_tier": ("templates/build_capability_model.py", "EVIDENCE_TIER_SPEC", "tiers"),
    "Lesson.status": ("templates/verify_ledger.py", "LESSON_STATUS", "set"),
    "WorkItem.kind": ("scripts/work_panel.py", "KINDS", "set"),
    "WorkItem.status": ("scripts/work_panel.py", "STATUSES", "set"),
    "WorkItem.severity": ("scripts/work_panel.py", "SEVERITIES", "set"),
    "TestResult.case_status": ("scripts/work_panel.py", "CASE_STATUSES", "set"),
    "TestReport.source_adapter": ("scripts/work_panel.py", "ADAPTERS", "set"),
    "Scenario.status": ("scripts/scenario_matrix.py", "STATUSES", "keys"),
    "Observation.affected_axis": ("scripts/ledger_feedback.py", "AXES", "tuple"),
    "Observation.disposition": ("scripts/ledger_feedback.py", "DISPOSITIONS", "tuple"),
    "Agent.role": ("scripts/agent_gateway.py", "ROLE_POLICIES", "keys"),
}

# 实体类型是 TBox 声明（约束），不是事实记录；每条都要指向真实来源。
ENTITY_TYPES = (
    {"id": "Project", "bc": "BC-DOMAIN", "source": "capability_model.projects[]"},
    {"id": "Module", "bc": "BC-DOMAIN", "source": "capability_model.projects[].modules[]"},
    {"id": "Capability", "bc": "BC-DOMAIN", "source": "registry.modules[].caps[]"},
    {"id": "Decision", "bc": "BC-FACT", "source": "entries[]"},
    {"id": "Rationale", "bc": "BC-FACT", "source": "entries[].rationale"},
    {"id": "Evidence", "bc": "BC-VERIFY", "source": "entries[].evidence[] / test_results"},
    {"id": "Claim", "bc": "BC-VERIFY", "source": "entries[].decision"},
    {"id": "Risk", "bc": "BC-FEEDBACK", "source": "work_items[kind=issue] / observations"},
    {"id": "Action", "bc": "BC-FACT", "source": "work_items[] / upgrade_log"},
    {"id": "Outcome", "bc": "BC-VERIFY", "source": "test_results / verify 输出"},
    {"id": "Observation", "bc": "BC-FEEDBACK", "source": "feedback/observations.jsonl"},
    {"id": "Lesson", "bc": "BC-FACT", "source": "lessons.items[]"},
    {"id": "Pattern", "bc": "BC-METHOD", "source": "lessons / 回归用例"},
    {"id": "Agent", "bc": "BC-ADOPT", "source": "access.agents[]"},
    {"id": "Asset", "bc": "BC-METHOD", "source": "governance_meta.method_assets"},
    {"id": "Invariant", "bc": "BC-VERIFY", "source": "verify_ledger.py add() ids"},
)

# 账本允许出现的顶层键（两个真实项目形状合并）。新增键若未登记 → undeclared_entity。
LEDGER_TOP_FIELDS = (
    "ledger_version", "title", "purpose", "last_updated", "owner", "workflow",
    "fields", "entries", "module_map", "architecture", "capability_model",
    "history", "lessons", "test_results", "work_items", "access",
    "governance_meta", "lifecycle", "next_queue", "doc_index", "coding_spec",
    "observations", "registry", "goals", "provenance",
)

RELATIONS = (
    {"id": "contains", "domain": "Project", "range": "Module", "cardinality": "1..N",
     "derivation": "capability_model.projects[].modules[]", "source_ref": "templates/build_capability_model.py"},
    {"id": "supersedes", "domain": "Decision", "range": "Decision", "cardinality": "0..1",
     "derivation": "entries[].supersedes", "source_ref": "templates/verify_ledger.py#supersede_chain_consistent"},
    {"id": "verifiedBy", "domain": "Capability", "range": "Evidence", "cardinality": "0..N",
     "derivation": "test_results / evidence_binding", "source_ref": "templates/verify_ledger.py#test_results_binding_valid"},
    {"id": "decides", "domain": "Decision", "range": "Capability", "cardinality": "0..N",
     "derivation": "capability_model decision refs", "source_ref": "templates/verify_ledger.py#decision_refs_valid"},
    {"id": "actsOn", "domain": "Action", "range": "Capability", "cardinality": "0..N",
     "derivation": "work_items[].scope", "source_ref": "templates/verify_ledger.py#work_item_refs_valid"},
    {"id": "generalizesFrom", "domain": "Lesson", "range": "Outcome", "cardinality": "1..N",
     "derivation": "lessons.candidates[]", "source_ref": "templates/verify_ledger.py#lesson_candidates_dedup"},
    {"id": "detects", "domain": "Observation", "range": "Risk", "cardinality": "0..N",
     "derivation": "feedback/observations.jsonl", "source_ref": "scripts/ledger_feedback.py"},
)

CARDINALITY_AXIOMS = (
    {"id": "A1", "statement": "dependsOn 无环", "check": "acyclicity"},
    {"id": "A2", "statement": "level >= L3 必须有新鲜 verified 证据", "check": "evidence_freshness"},
    {"id": "A3", "statement": "每个能力恰好一个 owner", "check": "ownership_exactly_one"},
    {"id": "A4", "statement": "Project 基数 1..N，能力编码在 project 内唯一", "check": "project_cardinality"},
    {"id": "G1", "statement": "无孤儿边：每条关系可从事实源复算", "check": "no_orphan_edge"},
    {"id": "G3", "statement": "Kleene K3：含 Unknown 不得派生 pass", "check": "three_valued"},
    {"id": "G4", "statement": "append-only：只取代不删除", "check": "append_only"},
)

STANDARD_ROW = re.compile(
    r"^\|\s*([A-Z][A-Za-z]*)\s*\|\s*([a-z_]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$",
    re.M,
)
DOMAIN_ID = re.compile(r"^[A-Z][A-Za-z]*\.[a-z_]+$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_refs(root: Path = ROOT) -> list[dict]:
    out = []
    for rel, role in SOURCE_FILES:
        p = Path(root) / rel
        if not p.is_file():
            raise ValueError(f"本体来源缺失：{rel}")
        out.append({"path": rel, "role": role,
                    "sha256": sha256_bytes(p.read_bytes())})
    return out


def assignments(path: Path) -> dict:
    """抽取顶层常量（含 AnnAssign），只保留可字面求值的定义。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: dict = {}
    for node in tree.body:
        name = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None:
            name, value = node.target.id, node.value
        if name and value is not None:
            try:
                out[name] = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError):
                continue
    return out


def observed_values(obj: object, rule: str) -> list[str]:
    if rule in ("set", "tuple", "list"):
        return sorted(str(x) for x in obj)
    if rule == "keys":
        return sorted(str(k) for k in obj.keys())
    if rule == "L-prefix":
        return sorted("L" + str(k) for k in obj.keys())
    if rule == "tiers":
        return sorted(str(k) for k in obj.get("tiers", {}).keys())
    raise ValueError(f"未知取值规则：{rule}")


def standard_section(root: Path = ROOT) -> str:
    text = (Path(root) / "docs/STANDARD.md").read_text(encoding="utf-8")
    m = re.search(r"^## 四、.*?$(.*?)^## 五、", text, re.M | re.S)
    if not m:
        raise ValueError("STANDARD.md 第四章（词表）缺失或章节标题被改动")
    return m.group(1)


def declared_domains(root: Path = ROOT) -> list[dict]:
    rows = []
    for m in STANDARD_ROW.finditer(standard_section(root)):
        entity, field, values, impl = m.groups()
        rows.append({
            "id": f"{entity}.{field}", "entity": entity, "field": field,
            "values": sorted(v.strip() for v in values.split("·") if v.strip()),
            "declared_ref": "docs/STANDARD.md#四", "implementation": impl.strip(),
        })
    if not rows:
        raise ValueError("STANDARD.md 第四章没有可解析的词表行")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("STANDARD.md 第四章存在重复的 <Type>.field 词表行")
    return sorted(rows, key=lambda r: r["id"])


def invariant_ids(root: Path = ROOT) -> list[str]:
    tree = ast.parse((Path(root) / "templates/verify_ledger.py").read_text(encoding="utf-8"))
    ids = {n.args[0].value for n in ast.walk(tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == "add" and n.args
           and isinstance(n.args[0], ast.Constant)
           and isinstance(n.args[0].value, str)}
    return sorted(ids)


def ubiquitous_language(domains: list[dict]) -> list[dict]:
    by_field: dict[str, dict] = {}
    for d in domains:
        row = by_field.setdefault(d["field"], {
            "term": d["field"], "entities": [], "qualified_form": f"<Type>.{d['field']}",
            "polyseme": False, "definition": "按实体分型的状态词，禁止裸用",
        })
        row["entities"].append(d["entity"])
    out = []
    for field in sorted(by_field):
        row = by_field[field]
        row["entities"] = sorted(row["entities"])
        row["polyseme"] = len(row["entities"]) > 1
        out.append(row)
    for term, definition in (
        ("level", "成熟度序数 L0-L5，完成度恒等于 level/5"),
        ("evidence_tier", "证据层级 declared/verified，与成熟度解耦"),
        ("severity", "风险严重度 low/med/high，与置信度解耦"),
        ("confidence", "断言置信度，必须可回溯至 evidence_binding"),
    ):
        if term not in by_field:
            out.append({"term": term, "entities": [], "qualified_form": f"<Type>.{term}",
                        "polyseme": False, "definition": definition})
    return sorted(out, key=lambda r: r["term"])


def build(root: Path = ROOT) -> dict:
    """从事实源确定性抽取 TBox。无时间戳、无绝对路径，可逐字节复现。"""
    root = Path(root)
    refs = source_refs(root)
    domains = declared_domains(root)
    drift: list[dict] = []
    cache: dict[str, dict] = {}

    for d in domains:
        binding = OBSERVED_BINDINGS.get(d["id"])
        d["observed_values"] = []
        d["observed_ref"] = None
        if not binding:
            continue
        rel, symbol, rule = binding
        if rel not in cache:
            cache[rel] = assignments(root / rel)
        obj = cache[rel].get(symbol)
        if obj is None:
            drift.append({"kind": "missing_enum", "id": d["id"],
                          "detail": f"{rel}#{symbol} 不存在或不可字面求值"})
            continue
        obs = observed_values(obj, rule)
        d["observed_values"] = obs
        d["observed_ref"] = f"{rel}#{symbol}"
        if obs != d["values"]:
            drift.append({"kind": "undeclared_value", "id": d["id"],
                          "declared": d["values"], "observed": obs,
                          "detail": "STANDARD.md 声明取值域与代码枚举不一致"})

    known = {d["id"] for d in domains}
    for did in sorted(OBSERVED_BINDINGS):
        if did not in known:
            drift.append({"kind": "undeclared_entity", "id": did,
                          "detail": "代码里出现枚举但 STANDARD.md 未声明该 <Type>.field"})

    lang = ubiquitous_language(domains)
    for d in domains:
        if not DOMAIN_ID.match(d["id"]):
            drift.append({"kind": "polyseme_violation", "id": d["id"],
                          "detail": "词表 id 未限定为 <Type>.field"})
    for row in lang:
        if row["polyseme"] and not row["qualified_form"]:
            drift.append({"kind": "polyseme_violation", "id": row["term"],
                          "detail": "同形异义词缺少限定形式"})

    inv = invariant_ids(root)
    payload = {
        "schema": SCHEMA,
        "generated_by": "scripts/ontology.py build",
        "source": "方法论仓库权威源（只读投影，不是第二事实源）",
        "source_refs": refs,
        "bounded_contexts": [dict(x) for x in BOUNDED_CONTEXTS],
        "entity_types": [dict(x) for x in ENTITY_TYPES],
        "ledger_top_fields": sorted(LEDGER_TOP_FIELDS),
        "ubiquitous_language": lang,
        "value_domains": domains,
        "relations": [dict(x) for x in RELATIONS],
        "cardinality_axioms": [dict(x) for x in CARDINALITY_AXIOMS],
        "invariant_ids": inv,
        "drift": drift,
        "summary": {
            "bounded_contexts": len(BOUNDED_CONTEXTS),
            "entity_types": len(ENTITY_TYPES),
            "value_domains": len(domains),
            "relations": len(RELATIONS),
            "axioms": len(CARDINALITY_AXIOMS) + len(inv),
            "source_files": len(refs),
            "polyseme_terms": sum(1 for x in lang if x["polyseme"]),
            "drift_count": len(drift),
        },
    }
    payload["ontology_digest"] = sha256_bytes(canonical(payload).encode("utf-8"))
    return payload


def expected_digest(root: Path = ROOT) -> str:
    """供 upgrade.py 在 M5 写入 governance_meta.ontology_digest。"""
    return build(root)["ontology_digest"]


def emit_md(onto: dict) -> str:
    lines = [
        "# 本体投影（generated，只读）",
        "",
        f"schema `{onto['schema']}` · digest `{onto['ontology_digest']}`",
        "",
        "由 `python3 scripts/ontology.py build --apply --approved-by <人>` 从事实源渲染。",
        "**不是人工文档，也不是第二事实源**：删掉本文件后 build 可逐字节复原。",
        "",
        "## 有界上下文",
        "",
        "| 上下文 | 职责 | 关系 |",
        "|---|---|---|",
    ]
    for x in onto["bounded_contexts"]:
        lines.append(f"| {x['id']} · {x['name']} | {x['responsibility']} | {x['relation']} |")
    lines += ["", "## 统一语言（分型，禁止词表归一）", "",
              "| 术语 | 出现实体 | 同形异义 | 限定形式 |", "|---|---|---|---|"]
    for x in onto["ubiquitous_language"]:
        lines.append(f"| {x['term']} | {', '.join(x['entities']) or '序数尺度'} | "
                     f"{'是' if x['polyseme'] else '否'} | `{x['qualified_form']}` |")
    lines += ["", "## 取值域（声明值 ↔ 代码枚举）", "",
              "| 域 id | 声明取值 | 代码来源 | 一致 |", "|---|---|---|---|"]
    for d in onto["value_domains"]:
        ok = "—" if not d["observed_ref"] else ("是" if d["observed_values"] == d["values"] else "否")
        lines.append(f"| `{d['id']}` | {' · '.join(d['values'])} | "
                     f"`{d['observed_ref'] or '仅文档声明'}` | {ok} |")
    lines += ["", "## 实体类型", "", "| 类型 | 上下文 | 事实来源 |", "|---|---|---|"]
    for x in onto["entity_types"]:
        lines.append(f"| {x['id']} | {x['bc']} | `{x['source']}` |")
    lines += ["", "## 关系（domain → range / 基数 / 派生）", "",
              "| 谓词 | domain → range | 基数 | 派生 |", "|---|---|---|---|"]
    for x in onto["relations"]:
        lines.append(f"| `{x['id']}` | {x['domain']} → {x['range']} | "
                     f"{x['cardinality']} | `{x['derivation']}` |")
    lines += ["", "## 公理", "", "| id | 陈述 | 检查 |", "|---|---|---|"]
    for x in onto["cardinality_axioms"]:
        lines.append(f"| {x['id']} | {x['statement']} | `{x['check']}` |")
    lines += ["", f"账本不变量 {len(onto['invariant_ids'])} 条：", "",
              "`" + "` `".join(onto["invariant_ids"]) + "`", "",
              "## 来源绑定", "", "| 文件 | 角色 | sha256 |", "|---|---|---|"]
    for x in onto["source_refs"]:
        lines.append(f"| `{x['path']}` | {x['role']} | `{x['sha256'][:16]}…` |")
    lines += ["", f"漂移条目：{onto['summary']['drift_count']}", ""]
    return "\n".join(lines)


def language_check(onto: dict) -> list[str]:
    errs = []
    for d in onto["value_domains"]:
        if not DOMAIN_ID.match(d["id"]):
            errs.append(f"polyseme_violation: {d['id']} 未限定为 <Type>.field")
    for row in onto["ubiquitous_language"]:
        if row["polyseme"] and not row["qualified_form"]:
            errs.append(f"polyseme_violation: {row['term']} 缺限定形式")
    return errs


def target_violations(root: Path, target: Path, onto: dict) -> list[dict]:
    """只读检查目标项目：三类漂移 + 第七轴绑定。绝不写目标项目。"""
    gov = Path(target) / "governance"
    ledger_path = gov / "DECISION_LEDGER.json"
    if not ledger_path.is_file():
        return [{"kind": "input_error", "severity": "high",
                 "symptom": "目标项目缺少 governance/DECISION_LEDGER.json", "repro": str(ledger_path)}]
    raw = ledger_path.read_bytes()
    ledger = json.loads(raw)
    source_ref = "project:" + sha256_bytes(raw)[:12]
    domains = {d["id"]: set(d["values"]) for d in onto["value_domains"]}
    out: list[dict] = []

    def add(kind: str, severity: str, symptom: str, repro: str, expected: str) -> None:
        out.append({"kind": kind, "severity": severity, "symptom": symptom,
                    "repro": repro, "expected": expected, "source_ref": source_ref,
                    "method_version": str((ledger.get("governance_meta") or {})
                                          .get("method_version", "未标注"))})

    bare_fields = ("status", "level", "tier", "severity", "confidence")
    for key in ledger:
        # 裸序数词由 polyseme 规则单独命名，避免同一个缺陷被记两次。
        if key not in onto["ledger_top_fields"] and key not in bare_fields:
            add("undeclared_entity", "low",
                f"未声明实体：账本顶层键 '{key}' 不在 ONTOLOGY.entity_types/ledger_top_fields",
                f"DECISION_LEDGER.json 顶层键 {key}",
                "在 STANDARD.md 与 scripts/ontology.py 登记该实体后再写入")
    for key in bare_fields:
        if key in ledger:
            add("polyseme_violation", "med",
                f"同形异义未限定：账本顶层出现裸字段 '{key}'",
                f"DECISION_LEDGER.json 顶层键 {key}",
                "改为具体实体内的 <Type>.field，或登记为独立域")

    checks = (
        ("entries", "status", "Decision.status"),
        ("work_items", "status", "WorkItem.status"),
        ("work_items", "kind", "WorkItem.kind"),
    )
    for collection, field, domain_id in checks:
        allowed = domains.get(domain_id, set())
        for row in ledger.get(collection, []) or []:
            if not isinstance(row, dict):
                continue
            val = str(row.get(field, ""))
            if val and val not in allowed:
                add("undeclared_value", "med",
                    f"未声明取值：{domain_id} = '{val}' 不在 ONTOLOGY 声明的取值域",
                    f"{collection}[{row.get('id', '?')}].{field} = {val}",
                    f"修正为 {domain_id} 的合法取值，或走 STANDARD.md 扩词流程")

    registry_path = gov / "registry.json"
    if registry_path.is_file():
        registry = json.loads(registry_path.read_bytes())
        cm = ledger.get("capability_model") or {}
        projects = cm.get("projects") or []
        declared_single = isinstance(registry.get("project"), dict) and "projects" not in registry
        if declared_single and len(projects) > 1:
            add("cardinality_contradiction", "high",
                f"本体基数违例：registry 声明单项目 project，能力模型含 {len(projects)} 个项目；A4 要求 1..N",
                "registry.json#project（单数 dict） 与 capability_model.projects[] 对照",
                "将契约升级为 projects[] 并按 A4 迁移（需人批准数据迁移）")

    meta = ledger.get("governance_meta") or {}
    bound = meta.get("ontology_digest")
    if bound is None:
        out.append({"kind": "binding", "severity": "na", "status": "na",
                    "symptom": "目标项目尚未绑定 ontology_digest（升级后由 M5 写入）",
                    "source_ref": source_ref,
                    "method_version": str(meta.get("method_version", "未标注"))})
    elif bound != onto["ontology_digest"]:
        out.append({"kind": "binding", "severity": "warn", "status": "warn",
                    "symptom": "ontology_digest 与权威源本体投影不一致",
                    "source_ref": source_ref,
                    "method_version": str(meta.get("method_version", "未标注"))})
    else:
        out.append({"kind": "binding", "severity": "pass", "status": "pass",
                    "symptom": "ontology_digest 与权威源一致",
                    "source_ref": source_ref,
                    "method_version": str(meta.get("method_version", "未标注"))})
    return out


def check(root: Path = ROOT, target: Path | None = None) -> dict:
    onto = build(root)
    errors: list[str] = []
    if build(root)["ontology_digest"] != onto["ontology_digest"]:
        errors.append("同一目录连续两次 build 摘要不一致：存在时间戳或不确定遍历")
    for ref in onto["source_refs"]:
        p = Path(root) / ref["path"]
        if not p.is_file() or sha256_bytes(p.read_bytes()) != ref["sha256"]:
            errors.append(f"来源绑定失效：{ref['path']}")
        if Path(ref["path"]).is_absolute() or ".." in Path(ref["path"]).parts:
            errors.append(f"来源路径非法：{ref['path']}")
    for d in onto["drift"]:
        errors.append(f"{d['kind']}: {d['id']} — {d['detail']}")
    errors.extend(language_check(onto))

    json_path = Path(root) / OUT_JSON
    md_path = Path(root) / OUT_MD
    synced = json_path.is_file() and md_path.is_file()
    if synced:
        try:
            stored = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stored = {}
            errors.append("ONTOLOGY.json 不可解析")
        if stored != onto:
            errors.append("docs/generated/ONTOLOGY.json 与权威源 build 结果不一致")
        if md_path.read_text(encoding="utf-8") != emit_md(onto):
            errors.append("docs/generated/ONTOLOGY.md 与权威源渲染结果不一致")
    else:
        errors.append("缺少派生只读文件：先跑 build --apply --approved-by <人>")

    tv = target_violations(root, target, onto) if target else []
    failures = [v for v in tv if v.get("severity") not in ("na", "pass")
                and v["kind"] != "input_error"]
    if any(v["kind"] == "input_error" for v in tv):
        errors.extend(v["symptom"] for v in tv if v["kind"] == "input_error")
    for v in failures:
        errors.append(f"{v['kind']}: {v['symptom']}")
    return {
        "schema": SCHEMA_CHECK, "ok": not errors, "errors": errors,
        "ontology_digest": onto["ontology_digest"],
        "generated_synced": synced and not any("ONTOLOGY." in e for e in errors),
        "drift_count": onto["summary"]["drift_count"],
        "summary": onto["summary"],
        "target": None if target is None else {
            "path": str(target),
            "binding": next((v["status"] for v in tv if v["kind"] == "binding"), "na"),
            "violations": [{k: v[k] for k in ("kind", "severity", "symptom", "repro")
                            if k in v} for v in tv if v["kind"] != "binding"],
        },
    }


def observations_for(violations: list[dict]) -> list[dict]:
    """复用 v1.4.0 观察契约，避免第二套 obs_id / 字段定义。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from ledger_feedback import make_obs  # noqa: E402  延迟导入，保持 expected_digest 轻量
    out = []
    for v in violations:
        if v.get("kind") == "binding" or v.get("severity") in ("na", "pass"):
            continue
        repro = v.get("repro", "")
        expected = v.get("expected", "")
        out.append(make_obs(
            source_ref=v["source_ref"], method_version=v.get("method_version", "未标注"),
            phase="verify", symptom=v["symptom"],
            evidence=canonical(v).encode("utf-8"), severity=v["severity"],
            repro=repro, expected=expected,
            proposed="收敛成四产物之一：新不变量 / 新场景轴 / 新迁移 / 新回归测试",
            axis="ontology"))
    return out


def append_observations(path: Path, rows: list[dict]) -> dict:
    path = Path(path)
    existing = [line for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()] if path.is_file() else []
    seen = {json.loads(line)["obs_id"] for line in existing}
    fresh = [r for r in rows if r["obs_id"] not in seen]
    lines = existing + [json.dumps(r, ensure_ascii=False, sort_keys=True)
                        for r in sorted(fresh, key=lambda x: x["obs_id"])]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"out": str(path), "added": len(fresh), "total": len(lines)}


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=str(ROOT), help="方法论仓库根")
    parser.add_argument("--json", action="store_true", help="输出 JSON")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name, help_text in (("build", "从事实源抽取本体投影"),
                            ("check", "校验投影同步与目标项目漂移"),
                            ("diff", "导出本体漂移为观察"),
                            ("emit-md", "渲染只读 Markdown"),
                            ("digest", "输出 ontology_digest")):
        p = sub.add_parser(name, help=help_text)
        common(p)
        if name in ("build", "emit-md", "diff"):
            p.add_argument("--apply", action="store_true", help="允许写盘")
            p.add_argument("--approved-by", default="", help="批准人（写盘必填）")
        if name == "build":
            p.add_argument("--out-json", default=OUT_JSON)
            p.add_argument("--out-md", default=OUT_MD)
        if name == "emit-md":
            p.add_argument("--out", default=OUT_MD)
            p.add_argument("--stdout", action="store_true", help="只打印，不写盘")
        if name in ("check", "diff"):
            p.add_argument("--target", default="", help="目标项目根（只读）")
        if name == "diff":
            p.add_argument("--out", default="feedback/observations.jsonl")
    args = ap.parse_args(argv)

    try:
        root = Path(args.root).resolve()
        target = Path(args.target).resolve() if getattr(args, "target", "") else None
        if target and not target.is_dir():
            raise ValueError(f"目标项目不存在：{target}")

        if args.command == "digest":
            result: dict = {"mode": "digest", "schema": SCHEMA,
                            "ontology_digest": expected_digest(root)}
        elif args.command == "build":
            onto = build(root)
            result = {"mode": "dry-run", "ontology": onto if args.json else None,
                      "ontology_digest": onto["ontology_digest"],
                      "summary": onto["summary"]}
            if args.apply:
                if not args.approved_by:
                    raise ValueError("写盘必须由人批准：--approved-by <人>")
                jp, mp = root / args.out_json, root / args.out_md
                jp.parent.mkdir(parents=True, exist_ok=True)
                jp.write_text(json.dumps(onto, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
                mp.write_text(emit_md(onto), encoding="utf-8")
                result = {"mode": "applied", "approved_by": args.approved_by,
                          "out_json": str(jp.relative_to(root)),
                          "out_md": str(mp.relative_to(root)),
                          "ontology_digest": onto["ontology_digest"]}
        elif args.command == "emit-md":
            md = emit_md(build(root))
            if args.stdout or not args.apply:
                print(md)
                return 0
            if not args.approved_by:
                raise ValueError("写盘必须由人批准：--approved-by <人>")
            out = root / args.out
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")
            result = {"mode": "applied", "out": str(out.relative_to(root))}
        elif args.command == "check":
            result = check(root, target)
        else:  # diff
            onto = build(root)
            if not target:
                raise ValueError("diff 需要 --target P（只读目标项目）")
            tv = target_violations(root, target, onto)
            rows = observations_for(tv)
            result = {"mode": "dry-run", "count": len(rows),
                      "violations": [{k: v[k] for k in ("kind", "severity", "symptom")
                                      if k in v} for v in tv],
                      "observations": rows}
            if args.apply:
                if not args.approved_by:
                    raise ValueError("写观察包必须由人批准：--approved-by <人>")
                result.update(append_observations(root / args.out, rows))
                result["mode"] = "applied"
                result["approved_by"] = args.approved_by
                result.pop("observations", None)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False) if args.json
              else f"输入错误：{exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if args.command == "check":
            print(f"本体自检 {'通过' if result['ok'] else '失败'}："
                  f"digest {result['ontology_digest'][:16]} · "
                  f"{result['summary']['value_domains']} 个取值域 · "
                  f"漂移 {result['drift_count']}")
            for e in result["errors"]:
                print("  [FAIL] " + e)
        elif args.command == "diff":
            print(f"本体漂移 {result['count']} 条 → 观察（affected_axis=ontology）")
            for v in result["violations"]:
                print(f"  [{v['kind']}] {v['symptom'][:90]}")
        else:
            print(f"[{result['mode']}] ontology_digest={result.get('ontology_digest', '')[:16]}")
    if args.command == "check" and not result["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
