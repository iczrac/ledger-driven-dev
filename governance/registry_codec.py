#!/usr/bin/env python3
"""registry schema/2 的唯一编码与容器归一化契约（标准库、只读、确定性）。

职责
----
1. 把两种 registry 输入归一成同一组项目：
   - 旧形状：``project`` + 平坦 ``modules[]``（单项目模板、示例项目仍兼容）；
   - 新形状：``schema: registry/2`` + ``projects[]``（每个项目自带 ``modules[]``）。
2. 把项目码 / 模块码 / 域 / 序号收敛成四段能力码；
3. 为生成器、校验器、可追溯投影器提供同一份展开结果，杜绝第二套 codec；
4. 责任扩张：registry codec ＋ 投影宣告 codec——消费方可在
   ``governance_meta.projection_policy`` 显式宣告 ``test_results: opt-out``，
   唯一判据在这里，生成器 / 校验器 / 升级器 / 工作台共用，不得各写一份。

纪律：本模块只读输入、不写文件、不猜缺失证据。显式 ``caps[].code`` 只要合法
就是稳定身份；否则按列表序号派生。迁移期间不得重排 caps。
"""
from __future__ import annotations

import re
from copy import deepcopy

SCHEMA = "registry/2"
LEGACY_SCHEMA = "registry/1"
PROJECTION_POLICY_SCHEMA = "projection-policy/1"
CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")

PROJECT_DIRS = (
    "contracts_dir", "unit_test_dir", "test_record_dir", "docs_dir", "governance_dir",
)
DIR_DEFAULTS = {
    "contracts_dir": "src/contracts",
    "unit_test_dir": "tests/unit",
    "test_record_dir": "docs/test_records",
    "docs_dir": "docs",
    "governance_dir": "governance",
}


def policy_error(ledger: dict) -> str | None:
    """只读校验投影宣告；没有宣告返回 None（旧账本行为完全不变）。"""
    if not isinstance(ledger, dict):
        return None
    meta = ledger.get("governance_meta")
    if not isinstance(meta, dict) or "projection_policy" not in meta:
        return None
    policy = meta["projection_policy"]
    if not isinstance(policy, dict):
        return "projection_policy 必须是对象"
    if policy.get("schema") != PROJECTION_POLICY_SCHEMA:
        return f"projection_policy.schema 非法：{policy.get('schema')}"
    if policy.get("test_results") not in ("opt-out", "inherit"):
        return "projection_policy.test_results 必须是 opt-out 或 inherit"
    for field in ("reason", "approved_by"):
        if not str(policy.get(field, "")).strip():
            return f"projection_policy.{field} 缺失"
    return None


def projection_opted_out(ledger: dict, key: str = "test_results") -> bool:
    """是否显式宣告不投影该键；宣告存在但非法时 fail-closed 返回 True。"""
    if not isinstance(ledger, dict):
        return False
    meta = ledger.get("governance_meta")
    if not isinstance(meta, dict) or "projection_policy" not in meta:
        return False
    if policy_error(ledger) is not None:
        return True
    return meta["projection_policy"].get(key) == "opt-out"


def code_namespace(project_code: str, module_code: str) -> str:
    """返回四段码的前两段命名空间。

    模块码已含合法大写项目段时直接使用，避免把 monorepo 根码重复拼成五段码；
    否则补项目码前缀，保持单项目模板的双写兼容。
    """
    module_code = str(module_code or "").strip()
    project_code = str(project_code or "").strip()
    if "." in module_code:
        first = module_code.split(".", 1)[0]
        if first.isupper() and re.fullmatch(r"[A-Z][A-Z0-9]*", first):
            return module_code
    return f"{project_code}.{module_code}" if project_code else module_code


def cap_code(project_code: str, module_code: str, domain: str, index: int,
             explicit: str | None = None) -> str:
    """生成/核对四段能力码；合法显式 code 优先，保证迁移期身份稳定。"""
    value = str(explicit or "").strip()
    if value:
        if not CODE_RE.fullmatch(value):
            raise ValueError(f"非法能力码：{value}")
        return value
    value = f"{code_namespace(project_code, module_code)}.{str(domain or '').strip().upper()}.{int(index):02d}"
    if not CODE_RE.fullmatch(value):
        raise ValueError(f"无法生成合法能力码：{value}")
    return value


def _normalize_project(raw: dict, modules: list[dict], legacy: bool) -> dict:
    project = deepcopy(raw) if isinstance(raw, dict) else {}
    code = str(project.get("code", "PROJ") or "PROJ").strip().upper()
    root = str(project.get("root", ".") or ".").strip("/") or "."
    out = {
        # 归一化结果恒为 v2 契约形状；legacy 仅描述输入来源，不泄漏到下游。
        "schema": SCHEMA,
        "code": code,
        "name": project.get("name") or code,
        "root": root,
        "governance_gate": bool(project.get("governance_gate", False)),
    }
    for key in PROJECT_DIRS:
        out[key] = project.get(key, DIR_DEFAULTS[key])
    out["modules"] = deepcopy(modules)
    return out


def normalize_projects(registry: dict) -> list[dict]:
    """把 v1 单项目与 v2 多项目都归一成项目列表；不修改输入。"""
    if not isinstance(registry, dict):
        return []
    modern = registry.get("projects")
    if isinstance(modern, list):
        return [
            _normalize_project(p, list(p.get("modules") or []), legacy=False)
            for p in modern if isinstance(p, dict)
        ]
    legacy_project = registry.get("project")
    if isinstance(legacy_project, dict):
        return [_normalize_project(
            legacy_project, list(registry.get("modules") or []), legacy=True)]
    return []


def iter_caps(registry: dict) -> list[dict]:
    """按 registry 顺序展开所有能力；新旧形状返回同一结构。"""
    out: list[dict] = []
    for project in normalize_projects(registry):
        for module in project["modules"]:
            mcode = str(module.get("code", "CORE") or "CORE").strip().upper()
            for index, raw_cap in enumerate(module.get("caps") or [], 1):
                cap = raw_cap if isinstance(raw_cap, dict) else {}
                domain = str(cap.get("domain", "ITEM") or "ITEM").strip().upper()
                out.append({
                    "code": cap_code(project["code"], mcode, domain, index, cap.get("code")),
                    "schema": project["schema"],
                    "project_code": project["code"],
                    "project_name": project["name"],
                    "project_root": project["root"],
                    "module_code": mcode,
                    "module_name": module.get("name", mcode),
                    "domain": domain,
                    "index": index,
                    "name": cap.get("name", domain.title()),
                    "impl": list(cap.get("impl") or []),
                    "hints": list(cap.get("hints") or []),
                })
    return out
