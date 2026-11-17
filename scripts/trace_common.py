#!/usr/bin/env python3
"""可追溯性脚本的共享只读工具：加载注册表/账本、展开能力编码、路径相对化。

本模块不写文件、不调用网络、不依赖第三方库。
"""
from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path, label: str = "文件") -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取{label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{label}必须是 JSON 对象：{path}")
    return data


def rel_path(path: str | Path, root: Path) -> str:
    """输出相对路径；无法相对化时只取文件名，绝不泄露机器绝对路径。"""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.name


def write_if_absent(path: Path, content: str, force: bool = False) -> str:
    """返回 written | skipped，非破坏性默认。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return "skipped"
    path.write_text(content, encoding="utf-8")
    return "written"


def iter_caps(registry: dict, ledger: dict) -> list[dict]:
    """按 registry 顺序展开能力，附账本实际状态（若已生成）。"""
    project = registry.get("project", {})
    code = str(project.get("code", "PROJ")).upper()
    proj_root = str(project.get("root", ".")).strip("/")
    cm = ledger.get("capability_model", {})
    actual: dict[str, dict] = {}
    for p in cm.get("projects", []):
        for m in p.get("modules", []):
            for c in m.get("caps", []):
                if c.get("code"):
                    actual[c["code"]] = c

    def norm(path: str) -> str:
        """账本路径相对仓库根；统一归一到项目根，便于与 git 路径对齐。"""
        val = str(path)
        if proj_root in ("", "."):
            return val
        if val == proj_root:
            return "."
        prefix = proj_root + "/"
        return val[len(prefix):] if val.startswith(prefix) else val

    out: list[dict] = []
    for mod in registry.get("modules", []):
        mcode = str(mod.get("code", "CORE")).upper()
        for idx, cap in enumerate(mod.get("caps", []), start=1):
            domain = str(cap.get("domain", "ITEM")).upper()
            cap_code = f"{code}.{mcode}.{domain}.{idx:02d}"
            live = actual.get(cap_code, {})
            raw_di = live.get("doc_index", {}) or {}
            raw_ev = live.get("evidence", {}) or {}
            di = {k: [{**x, "path": norm(x["path"])} if isinstance(x, dict) and x.get("path") else x
                      for x in (v or [])] for k, v in raw_di.items()}
            ev = {k: [norm(x) if isinstance(x, str) else x for x in (v or [])]
                  for k, v in raw_ev.items()}
            out.append({
                "code": cap_code,
                "module_code": mcode,
                "module_name": mod.get("name", mcode),
                "domain": domain,
                "name": cap.get("name", domain.title()),
                "impl": list(cap.get("impl", []) or []),
                "hints": list(cap.get("hints", []) or []),
                "level": int(live.get("level", 0) or 0),
                "tier": live.get("evidence_tier", "declared"),
                "doc_index": di,
                "evidence": ev,
                "entry_ids": sorted({x.get("id") for x in di.get("decisions", [])
                                     if isinstance(x, dict) and x.get("id")}),
                "next_action": live.get("next_action", ""),
            })
    return out


def artifact_paths(cap: dict) -> dict[str, list[str]]:
    """从账本能力点抽出可对齐的四类证据路径。"""
    di, ev = cap.get("doc_index", {}), cap.get("evidence", {})
    def vals(key: str) -> list[str]:
        return sorted({x.get("path", "") for x in (di.get(key) or [])
                       if isinstance(x, dict) and x.get("path")})
    return {
        "docs": sorted(set(vals("plans") + vals("related_docs") + vals("module_docs"))),
        "tests": sorted(set(vals("unit_tests") + vals("test_records"))),
        "code": sorted(set(vals("impl") + vals("contracts"))),
        "impl_declared": sorted(set(cap.get("impl", []) or [])),
    }
