#!/usr/bin/env python3
"""可追溯性脚本的共享只读工具：加载注册表/账本、展开能力编码、路径相对化。

本模块不写文件、不调用网络、不依赖第三方库。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# v2.0.1：可追溯投影器只消费唯一 registry codec，不再裸拼五段码。
_TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
sys.path.insert(0, str(_TEMPLATES))
from registry_codec import CODE_RE as STRICT_CODE_RE  # noqa: E402
from registry_codec import iter_caps as registry_iter_caps  # noqa: E402

# 候选码比严格 codec 宽：允许段内下划线/连字符和一位序号，供 fail-closed 提示与
# shadow 对齐使用；真正落盘的合法码仍以 registry_codec.CODE_RE 为唯一判据。
CODE_CANDIDATE_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"([A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z][A-Za-z0-9_-]*){2}\.\d{1,2})"
    r"(?![A-Za-z0-9_])"
)


def load_json(path: Path, label: str = "文件") -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取{label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{label}必须是 JSON 对象：{path}")
    return data


def iter_code_candidates(text: str):
    """逐行产出 (行号, 候选码)；候选合法与否由 STRICT_CODE_RE 决定。"""
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in CODE_CANDIDATE_RE.finditer(line):
            yield lineno, match.group(1)


def canonical_code(code: str) -> str | None:
    """把同义异码归一成用于 shadow 对齐的键，不用于落盘、不替代严格 codec。

    只做两件确定性的事：段内去掉非字母数字（``PRICE_02`` → ``PRICE02``），
    序号补零（``.2`` → ``.02``）。返回 None 表示无法安全归一。
    """
    parts = str(code or "").strip().split(".")
    if len(parts) != 4:
        return None
    cleaned: list[str] = []
    for index, part in enumerate(parts):
        value = re.sub(r"[^A-Za-z0-9]", "", part).upper()
        if not value:
            return None
        if index == 3:
            if not value.isdigit():
                return None
            value = f"{int(value):02d}"
        cleaned.append(value)
    candidate = ".".join(cleaned)
    return candidate if STRICT_CODE_RE.fullmatch(candidate) else None


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
    cm = ledger.get("capability_model", {})
    actual: dict[str, dict] = {}
    for p in cm.get("projects", []):
        for m in p.get("modules", []):
            for c in m.get("caps", []):
                if c.get("code"):
                    actual[c["code"]] = c

    def norm(path: str, proj_root: str) -> str:
        """账本路径相对仓库根；统一归一到项目根，便于与 git 路径对齐。"""
        val = str(path)
        if proj_root in ("", "."):
            return val
        if val == proj_root:
            return "."
        prefix = proj_root + "/"
        return val[len(prefix):] if val.startswith(prefix) else val

    out: list[dict] = []
    for rcap in registry_iter_caps(registry):
        proj_root = rcap["project_root"]
        cap_code = rcap["code"]
        live = actual.get(cap_code, {})
        raw_di = live.get("doc_index", {}) or {}
        raw_ev = live.get("evidence", {}) or {}
        di = {k: [{**x, "path": norm(x["path"], proj_root)}
                  if isinstance(x, dict) and x.get("path") else x
                  for x in (v or [])] for k, v in raw_di.items()}
        ev = {k: [norm(x, proj_root) if isinstance(x, str) else x for x in (v or [])]
              for k, v in raw_ev.items()}
        out.append({
            "code": cap_code,
            "project_code": rcap["project_code"],
            "project_root": proj_root,
            "module_code": rcap["module_code"],
            "module_name": rcap["module_name"],
            "domain": rcap["domain"],
            "name": rcap["name"],
            "impl": rcap["impl"],
            "hints": rcap["hints"],
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
