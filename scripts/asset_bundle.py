#!/usr/bin/env python3
"""把专家 / 技能从「仓库里的文本」升级成「目标项目里可直接加载的资产」。

第一性原理
----------
v1.1.0 只把专家、技能、模板、文档压缩成一个 sha256 摘要写进账本。
摘要能证明「资产变没变」，但不能回答「Agent 现在能不能用」：
  - 目标项目里根本没有 EXPERT.md / SKILL.md，只有一份 digest；
  - route_expert.py 用硬编码卡片路由，不读资产正文；
  - 用旧专家卡指挥新骨架，verify 依然全绿。

v1.2.0 的结论：**摘要绑定 + 只读安装 + 内容校验，三者缺一不可**。
安装产物不是第二事实源，而是方法论仓库 tag 的**只读部署副本**：
  1. 唯一权威源仍是方法论仓库；目标项目里的副本逐字节相同、禁止手改；
  2. 每次安装写 `governance/ASSET_MANIFEST.json`（逐文件 sha256 + 整包 digest）；
  3. 账本 `governance_meta.installed_assets` 绑定同一个 digest；
  4. 任一副本被改、被删、多出旧版本，verify 立刻判漂移，必须重新批准安装；
  5. 安装位置就是平台的项目级技能/专家目录 `.workbuddy/skills/` 与
     `.workbuddy/experts/`，SKILL.md 的 frontmatter 可被 Agent 平台直接加载。

纪律
----
- `install` 默认 dry-run；写盘必须 `--apply --approved-by <人>`；
- 幂等：内容一致的文件不重写；旧版本文件只在「未被手改」时才移除；
- 不含时间戳，manifest 与账本字段都是确定性输出；
- 清单外的 `.workbuddy/` 文件不动，避免误删用户自己的技能。

用法
----
    python3 scripts/asset_bundle.py --check
    python3 scripts/asset_bundle.py manifest --json
    python3 scripts/asset_bundle.py install --target P --json
    python3 scripts/asset_bundle.py install --target P --apply --approved-by 张三 --json
    python3 scripts/asset_bundle.py verify --target P --json

退出码：0 成功；1 被拒绝 / 漂移；2 定义自检失败 / 输入错误。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger_io import load_ledger, write_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_BUNDLE = "asset-bundle/1"
SCHEMA_MANIFEST = "installed-assets/1"
SCHEMA_INSTALL = "asset-install/1"
SCHEMA_VERIFY = "asset-install-verify/1"
SCHEMA_CHECK = "asset-install-check/1"
ALGORITHM = "sha256-files-v1"
INSTALL_ROOT = ".workbuddy"
MANIFEST_REL = "governance/ASSET_MANIFEST.json"
NAME_RE = re.compile(r"^name:\s*([A-Za-z0-9._-]+)\s*$", re.M)

# group → (权威源 glob, 目标安装目录)
ASSET_GROUPS: dict[str, tuple[str, str]] = {
    "experts": ("experts/*/EXPERT.md", "experts"),
    "skills": ("skills/*/SKILL.md", "skills"),
}
MIN_COUNTS = {"experts": 8, "skills": 14}


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _frontmatter_name(text: str) -> str:
    head = text.split("---", 2)
    block = head[1] if len(head) >= 3 else ""
    m = NAME_RE.search(block)
    return m.group(1) if m else ""


def bundle_rows(source_root: Path = ROOT) -> list[dict]:
    """权威源 → 安装路径的确定性清单（按路径排序，无时间戳）。"""
    source_root = Path(source_root)
    rows: list[dict] = []
    for group, (pattern, sub) in ASSET_GROUPS.items():
        for p in sorted(source_root.glob(pattern)):
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            name = p.parent.name
            rows.append({
                "group": group,
                "name": name,
                "source": p.relative_to(source_root).as_posix(),
                "path": f"{INSTALL_ROOT}/{sub}/{name}/{p.name}",
                "sha256": _sha256_file(p),
            })
    return sorted(rows, key=lambda r: r["path"])


def bundle(source_root: Path = ROOT) -> dict:
    """整包摘要：与 method_assets.py 同源同算法，但只覆盖可安装资产。"""
    rows = bundle_rows(source_root)
    payload = "".join(f"{r['path']}:{r['sha256']}\n" for r in rows)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    return {
        "schema": SCHEMA_BUNDLE,
        "algorithm": ALGORITHM,
        "digest": _sha256_bytes(payload.encode("utf-8")),
        "file_count": len(rows),
        "counts": counts,
        "install_root": INSTALL_ROOT,
        "manifest": MANIFEST_REL,
        "files": rows,
        "note": "只读部署副本；权威源是方法论仓库 tag，禁止在项目内编辑 SKILL.md / EXPERT.md",
    }


def ledger_binding(source_root: Path = ROOT) -> dict:
    """写进 governance_meta.installed_assets 的最小绑定（不含逐文件内容）。"""
    b = bundle(source_root)
    return {
        "schema": "installed-assets-binding/1",
        "digest": b["digest"],
        "file_count": b["file_count"],
        "counts": b["counts"],
        "install_root": INSTALL_ROOT,
        "manifest": MANIFEST_REL,
        "source": "方法论仓库 tag（只读副本，禁止在目标项目内编辑）",
    }


def read_manifest(target: Path) -> dict:
    p = Path(target) / MANIFEST_REL
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def install_plan(target: Path, source_root: Path = ROOT) -> dict:
    """只读预演：哪些文件缺失、漂移、一致、需要清理。"""
    target, source_root = Path(target), Path(source_root)
    b = bundle(source_root)
    old = read_manifest(target)
    old_rows = {r["path"]: r.get("sha256", "")
                for r in old.get("files", []) if isinstance(r, dict)}
    wanted = {r["path"]: r["sha256"] for r in b["files"]}
    missing, drifted, ok = [], [], []
    for r in b["files"]:
        p = target / r["path"]
        if not p.is_file():
            missing.append(r["path"])
        elif _sha256_file(p) != r["sha256"]:
            drifted.append(r["path"])
        else:
            ok.append(r["path"])
    stale = sorted(set(old_rows) - set(wanted))
    removable, protected = [], []
    for rel in stale:
        p = target / rel
        if not p.is_file():
            continue
        # 只清理「与旧清单记录完全一致」的副本；被人改过的一律保留并报警
        (removable if _sha256_file(p) == old_rows[rel] else protected).append(rel)
    changes = missing + drifted + removable
    return {
        "schema": SCHEMA_INSTALL, "target": ".", "mode": "plan",
        "digest": b["digest"], "file_count": b["file_count"],
        "counts": b["counts"], "missing": missing, "drifted": drifted,
        "unchanged": ok, "stale_removable": removable,
        "stale_protected": protected, "changes": changes,
        "noop": not changes and old.get("digest") == b["digest"],
        "writes": sorted(set(missing + drifted + [MANIFEST_REL])),
        "approval_required": True,
    }


def install(target: Path, *, approved_by: str = "", apply: bool = False,
            source_root: Path = ROOT, bind_ledger: bool = True) -> dict:
    """默认 dry-run；--apply 才写盘，且必须人批准。"""
    target, source_root = Path(target), Path(source_root)
    plan = install_plan(target, source_root)
    if not apply:
        return {**plan, "mode": "dry-run", "applied": False,
                "message": "只读预演；写盘需 --apply --approved-by <人>"}
    if not approved_by:
        raise ValueError("资产安装必须提供 --approved-by（人工批准）；AI 不得自行改写可用资产")
    if not target.is_dir():
        raise ValueError("目标目录不存在")

    b = bundle(source_root)
    for r in b["files"]:
        if r["path"] in plan["unchanged"]:
            continue
        dst = target / r["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((source_root / r["source"]).read_bytes())
    for rel in plan["stale_removable"]:
        p = target / rel
        if p.is_file():
            p.unlink()

    manifest = {
        "schema": SCHEMA_MANIFEST,
        "algorithm": ALGORITHM,
        "digest": b["digest"],
        "file_count": b["file_count"],
        "counts": b["counts"],
        "install_root": INSTALL_ROOT,
        "files": [{"path": r["path"], "sha256": r["sha256"]} for r in b["files"]],
        "note": "由 asset_bundle.py 生成的只读副本清单；手改副本会被 verify 判漂移",
    }
    mp = target / MANIFEST_REL
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    bound = False
    if bind_ledger and (target / "governance" / "DECISION_LEDGER.json").is_file():
        gov = target / "governance"
        ledger = load_ledger(gov)
        meta = ledger.get("governance_meta")
        if not isinstance(meta, dict):
            # 独立安装（未经 upgrade）也要能自证版本：只新增字段，不动既有状态
            meta = {}
            ledger["governance_meta"] = meta
        meta["installed_assets"] = ledger_binding(source_root)
        write_ledger(gov, ledger)
        bound = True
    return {**plan, "mode": "apply", "applied": True, "approved_by": approved_by,
            "installed": plan["missing"] + plan["drifted"],
            "removed": plan["stale_removable"], "ledger_bound": bound,
            "message": "资产已可用；请跑 verify 与 post_upgrade 复验"}


def verify(target: Path, source_root: Path = ROOT) -> dict:
    """只读复验：副本内容、清单、账本绑定三者是否一致。"""
    target, source_root = Path(target), Path(source_root)
    b = bundle(source_root)
    errors: list[dict] = []
    for r in b["files"]:
        p = target / r["path"]
        if not p.is_file():
            errors.append({"id": "missing", "path": r["path"], "reason": "资产副本缺失"})
        elif _sha256_file(p) != r["sha256"]:
            errors.append({"id": "drift", "path": r["path"], "reason": "副本内容与权威源不一致"})

    manifest = read_manifest(target)
    if not manifest:
        errors.append({"id": "manifest_missing", "path": MANIFEST_REL,
                       "reason": "缺少安装清单"})
    else:
        if manifest.get("digest") != b["digest"]:
            errors.append({"id": "manifest_digest", "path": MANIFEST_REL,
                           "reason": "清单整包摘要与权威源不一致"})
        recorded = {r.get("path"): r.get("sha256")
                    for r in manifest.get("files", []) if isinstance(r, dict)}
        if set(recorded) != {r["path"] for r in b["files"]}:
            errors.append({"id": "manifest_files", "path": MANIFEST_REL,
                           "reason": "清单文件集合与权威源不一致"})
        for rel, sha in recorded.items():
            p = target / str(rel)
            if not p.is_file() or _sha256_file(p) != sha:
                errors.append({"id": "manifest_hash", "path": str(rel),
                               "reason": "清单记录的文件哈希与实际不符"})

    bound_digest = None
    ledger_path = target / "governance" / "DECISION_LEDGER.json"
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            meta = ledger.get("governance_meta") or {}
            rec = meta.get("installed_assets") or {}
            bound_digest = rec.get("digest")
            if bound_digest != b["digest"]:
                errors.append({"id": "ledger_binding", "path": "governance_meta.installed_assets",
                               "reason": "账本未绑定当前资产摘要或摘要漂移"})
        except (OSError, json.JSONDecodeError):
            errors.append({"id": "ledger_unreadable", "path": "DECISION_LEDGER.json",
                           "reason": "账本不可解析"})
    return {"schema": SCHEMA_VERIFY, "target": ".", "ok": not errors,
            "digest": b["digest"], "file_count": b["file_count"],
            "counts": b["counts"], "bound_digest": bound_digest,
            "errors": errors,
            "hint": "" if not errors else
                    "python3 scripts/asset_bundle.py install --target P "
                    "--apply --approved-by <人>"}


def check_definitions(source_root: Path = ROOT) -> list[str]:
    """定义自检：数量下限、frontmatter name 与目录名一致、路径安全。"""
    source_root = Path(source_root)
    b = bundle(source_root)
    errs: list[str] = []
    for group, low in MIN_COUNTS.items():
        if b["counts"].get(group, 0) < low:
            errs.append(f"可安装资产组 {group} 只有 {b['counts'].get(group, 0)} 个，少于下限 {low}")
    if b["digest"] != bundle(source_root)["digest"]:
        errs.append("同一仓库连续两次摘要不一致：存在时间戳或不确定遍历")
    seen: set[str] = set()
    for r in b["files"]:
        if Path(r["path"]).is_absolute() or ".." in Path(r["path"]).parts:
            errs.append(f"安装路径非法：{r['path']}")
        key = (r["group"], r["name"])
        if key in seen:
            errs.append(f"资产名重复：{r['group']}/{r['name']}")
        seen.add(key)
        text = (source_root / r["source"]).read_text(encoding="utf-8")
        if _frontmatter_name(text) != r["name"]:
            errs.append(f"frontmatter name 与目录名不一致：{r['source']}")
        if "description:" not in text:
            errs.append(f"缺少 description frontmatter：{r['source']}")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="自检资产定义")
    ap.add_argument("--target", default=".", help="被治理项目根目录")
    ap.add_argument("--source-root", default=str(ROOT), help="方法论仓库根")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--apply", action="store_true", help="install 写盘")
    ap.add_argument("--approved-by", default="", help="人工批准人")
    sub = ap.add_subparsers(dest="command")
    def common(p):
        p.add_argument("--target", default=argparse.SUPPRESS, help="被治理项目根目录")
        p.add_argument("--source-root", default=argparse.SUPPRESS, help="方法论仓库根")
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--apply", action="store_true", default=argparse.SUPPRESS)
        p.add_argument("--approved-by", default=argparse.SUPPRESS)
        return p
    for name in ("manifest", "install", "verify"):
        common(sub.add_parser(name))
    args = ap.parse_args(argv)
    source_root = Path(args.source_root).expanduser().resolve()

    if args.check:
        errs = check_definitions(source_root)
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 2
        b = bundle(source_root)
        print(f"可安装资产自检通过：{b['file_count']} 个文件 · {b['counts']} · "
              f"摘要 {b['digest'][:12]}")
        return 0

    command = args.command or "manifest"
    try:
        if command == "manifest":
            b = bundle(source_root)
            out = {k: v for k, v in b.items() if k != "files"} if not args.json else b
            if args.json:
                print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print(f"可安装资产 {b['file_count']} 个 · {b['counts']} · "
                      f"安装根 {b['install_root']} · 摘要 {b['digest']}")
            return 0
        if command == "install":
            result = install(Path(args.target).expanduser().resolve(),
                             approved_by=args.approved_by, apply=args.apply,
                             source_root=source_root)
            rc = 0
        else:
            result = verify(Path(args.target).expanduser().resolve(), source_root)
            rc = 0 if result["ok"] else 1
    except ValueError as exc:
        print(f"拒绝：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
          if args.json else result.get("message", json.dumps(result, ensure_ascii=False)))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
