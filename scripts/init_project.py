#!/usr/bin/env python3
"""初始化项目治理骨架：支持新建（greenfield）与存量接入（adopt）两种模式。

用法：
    python3 scripts/init_project.py --target /path/to/new --code MYPROJ --name "我的项目"
    python3 scripts/init_project.py --target /path/to/legacy --mode adopt \
        --from-draft /path/to/legacy/governance/registry.draft.json --code LEGACY

会创建（共 7 个文件，全部落在 <target>/governance/）：
    registry.json                 能力注册表（新建为空清单；接入来自草稿）—— 唯一手写清单
    DECISION_LEDGER.json          账本骨架（含接入来源 provenance）
    index.html                    可视化看板（EMBED 由生成器同步）
    build_capability_model.py     生成器副本（来自 templates/）
    binding_advisory.py           证据绑定 advisory 副本（来自 templates/，v2.1.2）
    derived_issues.py             派生 issue 副本（来自 templates/，v2.3.0）
    verify_ledger.py              校验器副本（来自 templates/）
    registry_codec.py             registry schema/2 唯一编码契约副本（来自 templates/）
    run_tests.py                  测试报告生成器副本（来自 scripts/）

后四个是工具副本，可用 --no-generator 一并跳过；不在目标项目里手改它们，
升级方法论时从 templates/ / scripts/ 重新同步。
不会覆盖已存在文件（除非 --force）；草稿、源码与既有账本永不自动改写。
目录含义与所有权见 docs/15-文件架构.md 与 scripts/file_layout.py。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"
# v2.20.0（A 项）：落盘前用唯一 codec 校验草稿，绝不复制第二套编码规则。
sys.path.insert(0, str(TEMPLATES))
from registry_codec import cap_code as codec_cap_code  # noqa: E402
from discover_project import sanitize_code  # noqa: E402


def _source_label(path: Path, target: Path) -> str:
    """只保留相对路径或文件名，绝不把用户绝对路径写进账本。"""
    try:
        return path.relative_to(target).as_posix()
    except ValueError:
        return path.name


def _strip_declarations(registry: dict) -> dict:
    """greenfield 初始化时去掉示例里的 tests/test_records 声明。

    示例声明是为了教写法（精确路径 > 关键词）。但新项目还没有这些文件，
    原样带过去会让生成器每次打印「声明的测试不存在」——那不是教学，是噪声。
    hints 保留，等真实测试落地后再改成显式声明。
    """
    out = json.loads(json.dumps(registry))
    for module in out.get("modules") or []:
        for cap in module.get("caps") or []:
            cap.pop("tests", None)
            cap.pop("test_records", None)
    return out


def load_registry_source(target: Path, gov: Path, mode: str,
                         from_draft: str | None) -> tuple[dict, dict]:
    """返回 (registry, provenance)。adopt 优先草稿，绝不覆盖草稿本身。"""
    template = json.loads((TEMPLATES / "registry.example.json").read_text())
    if not from_draft and mode == "greenfield":
        return _strip_declarations(template), {"source": "template", "discovery": {}}

    if from_draft:
        src = Path(from_draft).expanduser().resolve()
        if not src.is_file():
            raise ValueError(f"registry 草稿不存在：{from_draft}")
    else:
        candidates = [gov / "registry.draft.json", gov / "registry.json"]
        src = next((p for p in candidates if p.is_file()), None)
        if src is None:
            raise ValueError("存量接入需要先运行 discover_project.py，或使用 --from-draft 指定草稿。")

    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 registry 草稿：{exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("modules"), list):
        raise ValueError("registry 草稿格式错误：必须包含 modules 数组。")

    base = json.loads((TEMPLATES / "registry.example.json").read_text())
    merged = dict(base)
    merged.update({k: v for k, v in raw.items() if not k.startswith("_")})
    project = dict(base["project"])
    project.update(raw.get("project") or {})
    merged["project"] = project
    return merged, {"source": _source_label(src, target),
                    "discovery": raw.get("_discovery") or {}}


def validate_registry_codes(reg: dict, source: str) -> None:
    """adopt 落盘前 fail-closed：非法码必须带文件、位置与建议改法。

    生成器在很下游才抛裸 ValueError；接入时提前拦住，才能告诉人「改哪个文件、
    改成什么」。校验复用唯一 codec，不在本脚本复制正则。
    """
    sys.path.insert(0, str(TEMPLATES))
    from registry_codec import CODE_RE  # noqa: PLC0415
    segment = re.compile(r"[A-Z][A-Z0-9]*")
    errors: list[str] = []
    modules = reg.get("modules") or []
    for mi, module in enumerate(modules, 1):
        mcode = str(module.get("code", ""))
        if not segment.fullmatch(mcode):
            errors.append(f"modules[{mi}].code={mcode!r} 建议改为 {sanitize_code(mcode, 'CORE')}")
        for ci, cap in enumerate(module.get("caps") or [], 1):
            domain = str(cap.get("domain", ""))
            explicit = str(cap.get("code", "")).strip()
            try:
                codec_cap_code(str((reg.get("project") or {}).get("code", "")),
                               mcode, domain, ci, explicit or None)
            except ValueError as exc:
                suggestion = sanitize_code(explicit or domain, "ITEM")
                full = (f"{reg['project']['code']}.{sanitize_code(mcode, 'CORE')}."
                        f"{suggestion}.{ci:02d}")
                errors.append(
                    f"modules[{mi}].caps[{ci}].domain={domain!r} "
                    f"（{exc}）→ 请把 domain 改为 {suggestion}，"
                    f"或把 code 显式写为 {full}")
    if errors:
        detail = "\n  - ".join(errors)
        raise ValueError(
            f"registry 草稿 {source} 的能力码违反四段式契约：\n  - {detail}\n"
            "契约：^[A-Z][A-Z0-9]*.[A-Z][A-Z0-9]*.[A-Z][A-Z0-9]*.\\d{2}$；"
            "草稿与源码均未被修改。")


def build_ledger(name: str, code: str, mode: str, provenance: dict,
                 intent: str) -> dict:
    """账本骨架：只记录接入事实，不预填任何能力等级。"""
    now = datetime.now()
    disc = provenance.get("discovery") or {}
    rationale = (
        f"以 {mode} 模式建立治理骨架；registry 来源 {provenance.get('source', 'template')}。"
        + (f"只读发现候选模块 {disc.get('candidate_modules', 0)}、能力点 "
           f"{disc.get('candidate_caps', 0)}，置信度 {disc.get('confidence', 'unknown')}。"
           if disc else "")
    )
    return {
        "ledger_version": "1.0",
        "title": f"{name} 决策与能力账本",
        "purpose": "单一事实源：决策、裁决、待办及能力索引的唯一写入点。",
        "last_updated": now.strftime("%Y-%m-%d %H:%M HKT"),
        "owner": "待定",
        "provenance": {
            "mode": mode,
            "source": provenance.get("source", "template"),
            "intent": intent,
            "discovery": disc,
        },
        "workflow": [
            "所有重大决策/裁决/待办只写入本文件 entries，不再新建独立报告。",
            "新增条目分配稳定 id，状态初始 proposed/decided，填齐字段。",
            "旧决策被取代时设 supersedes/supersedes，用取代链表达演进。",
            "能力等级与完成度由 build_capability_model.py 从证据重算，禁止手填。",
        ],
        "fields": {
            "id": "稳定标识，永不复用",
            "status": "proposed | decided | done | superseded | deferred",
            "evidence": "证据/文档路径",
            "confidence": "high | medium | low",
        },
        "entries": [{
            "id": "D-001",
            "date": now.strftime("%Y-%m-%d"),
            "title": f"{code} · 治理初始化 · 建立账本与能力注册表（{mode}）",
            "category": "治理初始化",
            "scope": code,
            "status": "done",
            "supersedes": None,
            "decision": f"以 {mode} 模式建立账本与能力注册表，等级一律由证据派生。",
            "rationale": rationale,
            "evidence": ["governance/registry.json"],
            "confidence": "high",
        }],
        "history": {"spec": {}, "events": []},
        "lessons": {"spec": {}, "items": [], "candidates": []},
        "module_map": {"modules": [], "pages_path": "artifacts/control_center/pages/"},
        "architecture": {"projects": []},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="目标项目根目录")
    ap.add_argument("--code", required=True, help="项目代码（大写短码，如 MYPROJ）")
    ap.add_argument("--name", help="项目展示名（默认同 code）")
    ap.add_argument("--mode", choices=("greenfield", "adopt"), default="greenfield",
                    help="新建项目 / 存量项目接入")
    ap.add_argument("--from-draft", help="registry 草稿路径（adopt 默认找 governance/registry.draft.json）")
    ap.add_argument("--intent", default="", help="本轮意图，写入账本 provenance 便于追溯")
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件")
    ap.add_argument("--no-generator", action="store_true", help="不复制生成器")
    args = ap.parse_args()

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(f"目标目录不存在：{args.target}", file=sys.stderr)
        return 2
    gov = target / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    name = args.name or args.code
    code = args.code.upper()

    try:
        reg, provenance = load_registry_source(target, gov, args.mode, args.from_draft)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    reg["project"]["code"] = code
    reg["project"]["name"] = name
    reg["project"]["root"] = "."

    if args.mode == "adopt":
        try:
            validate_registry_codes(reg, provenance.get("source", "registry 草稿"))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    files: list[tuple[Path, str]] = [
        (gov / "registry.json", json.dumps(reg, ensure_ascii=False, indent=2)),
    ]

    files.append((
        gov / "DECISION_LEDGER.json",
        json.dumps(build_ledger(name, code, args.mode, provenance, args.intent),
                   ensure_ascii=False, indent=2),
    ))

    # 看板模板
    files.append((gov / "index.html", (TEMPLATES / "index.html.template").read_text()))

    for path, content in files:
        if path.exists() and not args.force:
            print(f"跳过（已存在）: {path}")
            continue
        path.write_text(content)
        print(f"写入: {path}")

    if not args.no_generator:
        for name in ("build_capability_model.py", "binding_advisory.py",
                     "derived_issues.py", "verify_ledger.py", "registry_codec.py"):
            gen = gov / name
            if gen.exists() and not args.force:
                print(f"跳过（已存在）: {gen}")
            else:
                shutil.copy(TEMPLATES / name, gen)
                print(f"写入: {gen}")
        # 证据分层：测试报告生成器（从模板项目的 scripts/ 复制到新项目的 governance/）
        runner = gov / "run_tests.py"
        if runner.exists() and not args.force:
            print(f"跳过（已存在）: {runner}")
        else:
            shutil.copy(HERE / "run_tests.py", runner)
            print(f"写入: {runner}")

    print(f"\n完成（模式 {args.mode}）。下一步：")
    print(f"  1. 核对 {gov / 'registry.json'} 的 modules 清单"
          + ("（来自只读草稿，请人工精简）" if args.mode == "adopt" else ""))
    print(f"  2. cd {target} && python3 governance/build_capability_model.py --root . --dry-run")
    print(f"  3. 确认无误后去掉 --dry-run 正式生成")
    print(f"  4. python3 governance/verify_ledger.py --root . --strict  # 校验账本自洽")
    print(f"  5.（可选）升级证据为 verified —— 从本项目根运行：")
    print(f"     python3 governance/run_tests.py --dir tests --out governance/test_report.json")
    print(f"     python3 governance/build_capability_model.py --root . --test-report governance/test_report.json")
    print(f"  6. 浏览器打开 {gov / 'index.html'} 查看看板（徽章显示声明/实测）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
