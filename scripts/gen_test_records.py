#!/usr/bin/env python3
"""L4 测试记录生成器：从真实测试报告派生 docs/test_records/<CAP>_TEST_RECORD.md。

第一性原理
----------
L4 的判定规则是「docs/test_records/ 有测试记录」。这条规则**不检查记录是不是真的**——
手写一份三行 Markdown 就能永久撑住一个 L4，等级于是空壳，还会随时间越来越空。

本脚本把 L4 证据换成机器生成、可复算、不形式主义的东西：

1. 记录内容只来自 ``governance/test_report.json``（真实运行结果：逐例状态 +
   源码摘要绑定）。**不手写任何用例名**——用例名一律从报告里取。
2. 每个 cap 的 ``cases`` 只取该 cap 声明的 ``tests`` 文件里**状态为 pass** 的真实用例；
   声明了但报告里没有通过用例的文件，显式列进「声明未覆盖」，不假装覆盖。
3. 记录带 ``source_sha256``（报告文件的 sha256），护栏可与磁盘上的报告逐字节对账。
4. ``generated_at`` 取**证据报告的生成时刻**（``time_basis: evidence_report``）：
   派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果（幂等）；
   报告一旦更新，记录随证据一起刷新，不会出现「时间戳漂移但内容没变」的假 diff。
   这不是谎报时间——它声明的是「本记录对应哪一刻的证据」，而不是「谁在几点写的」。

用法
----
    python3 scripts/gen_test_records.py                    # 生成/刷新 docs/test_records/*.md
    python3 scripts/gen_test_records.py --check            # 只核对漂移，不写盘（有漂移 exit 1）
    python3 scripts/gen_test_records.py --update-registry  # 同步 registry 的 test_records 声明
    python3 scripts/gen_test_records.py --json             # 机器可读汇总

纪律
----
1. 零第三方依赖（只用标准库）；
2. **不放宽 L4 判定规则**：本脚本只补真实证据 + 补声明，判定逻辑一字不改；
3. 不臆造证据：报告里没有通过用例 → 不出记录（并明确报出来）；
4. 生成与核对是同一个纯函数（报告字节 + registry 声明 → 记录正文），
   所以「重跑 diff 为空」是可复算的幂等证明，而不是口头承诺。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "templates"))
# 编码契约只有一份：registry_codec 是唯一 codec（见 governance/registry_codec.py 头注）。
from registry_codec import cap_code as codec_cap_code  # noqa: E402
from registry_codec import normalize_projects  # noqa: E402

RECORD_SCHEMA = "ledger-test-record/1"
REPORT_SCHEMA = "ledger-test-report/1"
RECORD_SUFFIX = "_TEST_RECORD.md"
HKT = timezone(timedelta(hours=8), "HKT")
# 报告时间戳格式（见 scripts/run_tests.py）："YYYY-MM-DD HH:MM HKT"
REPORT_TIME_FORMATS = ("%Y-%m-%d %H:%M HKT", "%Y-%m-%d %H:%M:%S HKT")


# --------------------------------------------------------------- 证据读取

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_report_time(raw: str) -> datetime:
    """把报告的 generated_at 解析成带时区的 datetime；无法解析即 fail-closed。"""
    text = str(raw or "").strip()
    if not text:
        raise ValueError("报告缺 generated_at，无法给记录打时间戳")
    for fmt in REPORT_TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=HKT)
        except ValueError:
            continue
    try:  # 已经是 ISO 8601（含偏移）就直接用
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"无法解析报告 generated_at：{text!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=HKT)


def load_report(path: Path) -> tuple[dict, str]:
    """读测试报告与其文件摘要。返回 (报告, 报告文件 sha256)。"""
    if not path.is_file():
        raise SystemExit(f"测试报告不存在：{path}")
    raw = path.read_bytes()
    report = json.loads(raw.decode("utf-8"))
    if report.get("schema") != REPORT_SCHEMA:
        raise SystemExit(f"测试报告 schema 不是 {REPORT_SCHEMA}：{report.get('schema')!r}")
    if report.get("overall") != "pass":
        raise SystemExit(f"测试报告整体未通过（overall={report.get('overall')!r}），"
                         "不得据此派生 L4 证据")
    return report, sha256_bytes(raw)


def passed_cases_by_file(report: dict) -> dict[str, list[str]]:
    """按测试文件归集**状态为 pass** 的真实用例名（按报告原序，稳定可复算）。"""
    out: dict[str, list[str]] = {}
    for case in report.get("cases") or []:
        if not isinstance(case, dict):
            continue
        if str(case.get("status")) != "pass":
            continue
        path = str(case.get("file") or "")
        cid = str(case.get("id") or "")
        if not path or not cid:
            continue
        out.setdefault(path, []).append(cid)
    return out


def case_counts_by_file(report: dict) -> dict[str, dict[str, int]]:
    """按测试文件统计各状态用例数（用于覆盖明细表）。"""
    out: dict[str, dict[str, int]] = {}
    for case in report.get("cases") or []:
        if not isinstance(case, dict):
            continue
        path = str(case.get("file") or "")
        if not path:
            continue
        bucket = out.setdefault(path, {"total": 0, "pass": 0, "not_pass": 0})
        bucket["total"] += 1
        if str(case.get("status")) == "pass":
            bucket["pass"] += 1
        else:
            bucket["not_pass"] += 1
    return out


# --------------------------------------------------------------- registry 展开

def iter_registry_caps(registry: dict) -> list[dict]:
    """按 registry 顺序展开能力点（含 code / tests / test_records 原始声明）。

    编码只用 registry_codec.cap_code——不写第二套 codec，避免迁移期身份漂移。
    """
    caps: list[dict] = []
    for project in normalize_projects(registry):
        for module in project.get("modules") or []:
            mcode = str(module.get("code", "CORE") or "CORE").strip().upper()
            for index, cap in enumerate(module.get("caps") or [], 1):
                if not isinstance(cap, dict):
                    continue
                domain = str(cap.get("domain", "ITEM") or "ITEM").strip().upper()
                code = codec_cap_code(project["code"], mcode, domain, index,
                                     cap.get("code"))
                caps.append({
                    "code": code,
                    "name": str(cap.get("name") or domain.title()),
                    "domain": domain,
                    "project_code": project["code"],
                    "project_root": project["root"],
                    "test_record_dir": project.get("test_record_dir", "docs/test_records"),
                    "tests": [str(t) for t in (cap.get("tests") or [])],
                    "declared_records": [str(t) for t in (cap.get("test_records") or [])],
                })
    return caps


# --------------------------------------------------------------- 记录渲染

def render_record(cap: dict, cases_by_file: dict[str, list[str]],
                  counts_by_file: dict[str, dict[str, int]],
                  report_meta: dict, report_rel: str) -> str:
    """把一个能力点的真实通过用例渲染成机器可解析的测试记录。

    字段口径（护栏按此解析）：
      source_sha256  报告文件字节的 sha256 —— 可与磁盘上的报告逐字节对账
      generated_at    ISO 8601；取自报告生成时刻（time_basis: evidence_report）
      cases           真实通过用例名（JSON 数组，逐字取自报告）
      覆盖             该 cap 声明的测试文件（JSON 数组）
      结果             真实通过用例数 + "passed"
    """
    covered = list(cap["tests"])
    cases: list[str] = []
    for path in covered:
        cases.extend(cases_by_file.get(path, []))
    uncovered = [p for p in covered if not cases_by_file.get(p)]

    lines: list[str] = []
    lines.append(f"# {cap['name']} 测试记录")
    lines.append("")
    lines.append(f"- schema: {RECORD_SCHEMA}")
    lines.append(f"- cap_code: {cap['code']}")
    lines.append(f"- cap_name: {cap['name']}")
    lines.append(f"- source_report: {report_rel}")
    lines.append(f"- source_sha256: {report_meta['sha256']}")
    lines.append(f"- report_generated_at: {report_meta['generated_at_raw']}")
    lines.append(f"- generated_at: {report_meta['generated_at']}")
    lines.append("- time_basis: evidence_report")
    lines.append(f"- 覆盖: {json.dumps(covered, ensure_ascii=False)}")
    lines.append(f"- 声明未覆盖: {json.dumps(uncovered, ensure_ascii=False)}")
    lines.append(f"- 结果: {len(cases)} passed")
    lines.append(f"- cases: {json.dumps(cases, ensure_ascii=False)}")
    lines.append("")
    lines.append("## 覆盖明细")
    lines.append("")
    lines.append("| 测试文件 | 用例数 | 通过 | 未通过 |")
    lines.append("| --- | --- | --- | --- |")
    for path in covered:
        stat = counts_by_file.get(path, {"total": 0, "pass": 0, "not_pass": 0})
        lines.append(f"| {path} | {stat['total']} | {stat['pass']} | {stat['not_pass']} |")
    lines.append("")
    lines.append("## 复算说明")
    lines.append("")
    lines.append("本文件由 `scripts/gen_test_records.py` 从 "
                 f"`{report_rel}` 派生，**不要手改**。")
    lines.append("")
    lines.append("- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；")
    lines.append("- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）："
                 "派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；")
    lines.append("- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，"
                 "用例名逐字取自报告；")
    lines.append("- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。")
    lines.append("")
    lines.append("复核命令：")
    lines.append("")
    lines.append("    python3 scripts/gen_test_records.py --check")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------- registry 声明同步

_KEY_RE = re.compile(r'^(\s*)"(tests|test_records)"\s*:\s*')


def _array_span(lines: list[str], key_line: int) -> tuple[int, int]:
    """返回数组值跨越的行区间 [start, end]（含）。"""
    start = key_line
    text = lines[key_line]
    depth = text.count("[") - text.count("]")
    end = key_line
    while depth > 0 and end + 1 < len(lines):
        end += 1
        depth += lines[end].count("[") - lines[end].count("]")
    return start, end


def _cap_line_span(lines: list[str], start: int) -> int:
    """从 start 行起找到该 cap 对象的结束行（"      }" 或 "      },"）。"""
    depth = 0
    for idx in range(start, len(lines)):
        depth += lines[idx].count("{") - lines[idx].count("}")
        if depth <= 0:
            return idx
    raise ValueError("registry 结构异常：找不到 cap 对象结尾")


def _find_cap_spans(text: str) -> list[tuple[int, int]]:
    """定位每个 cap 对象在文本中的行区间（按出现顺序）。"""
    lines = text.splitlines()
    spans: list[tuple[int, int]] = []
    for idx, line in enumerate(lines):
        if not re.match(r'^\s*"domain"\s*:', line):
            continue
        start = idx
        while start >= 0 and lines[start].strip() != "{":
            start -= 1
        if start < 0:
            raise ValueError("registry 结构异常：domain 行找不到所属对象")
        spans.append((start, _cap_line_span(lines, start)))
    return spans


def update_registry_text(text: str, wanted: dict[str, list[str]]) -> tuple[str, list[str]]:
    """把 test_records 声明写进 registry 文本（外科式替换，不重排、不重排版）。

    wanted: {cap_code: [声明路径, ...]}；cap_code 需与 registry 中 cap 的顺序一致。
    返回 (新文本, 变更说明列表)。
    """
    lines = text.splitlines()
    spans = _find_cap_spans(text)
    if len(spans) != len(wanted):
        raise ValueError(
            f"registry 中 cap 数量（{len(spans)}）与待同步数量（{len(wanted)}）不一致")
    notes: list[str] = []
    out: list[str] = []
    cursor = 0
    for (start, end), (code, paths) in zip(spans, wanted.items()):
        out.extend(lines[cursor:start])
        block = lines[start:end + 1]
        new_block, note = _patch_cap_block(block, paths, code)
        out.extend(new_block)
        notes.append(note)
        cursor = end + 1
    out.extend(lines[cursor:])
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), notes


def _patch_cap_block(block: list[str], paths: list[str], code: str) -> tuple[list[str], str]:
    """在单个 cap 块内写入/更新 test_records 声明。paths 为空 = 撤销声明。"""
    value = json.dumps(paths, ensure_ascii=False)
    existing = None
    for idx, line in enumerate(block):
        m = _KEY_RE.match(line)
        if m and m.group(2) == "test_records":
            existing = idx
            break
    if existing is not None:
        start, end = _array_span(block, existing)
        indent = _KEY_RE.match(block[existing]).group(1)
        if not paths:
            # 撤销声明：把该行整行删掉，并把上一行的尾逗号去掉
            head = block[:start]
            if head:
                last = head[-1].rstrip()
                if last.endswith(","):
                    head[-1] = last[:-1]
            new_block = head + block[end + 1:]
            return new_block, f"{code}: 撤销 test_records 声明"
        new_block = block[:start] + [f'{indent}"test_records": {value}'] + block[end + 1:]
        return new_block, f"{code}: 更新 test_records 声明"
    if not paths:
        return block, f"{code}: 无 test_records 声明（保持原样）"
    # 没有则插在 tests 之后（tests 永远是已有声明里的最后一个键，插在它后面最贴近语义）
    tests_idx = None
    for idx, line in enumerate(block):
        m = _KEY_RE.match(line)
        if m and m.group(2) == "tests":
            tests_idx = idx
            break
    if tests_idx is None:
        raise ValueError(f"{code}: cap 块里没有 tests 键，无法定位插入点")
    _, t_end = _array_span(block, tests_idx)
    indent = _KEY_RE.match(block[tests_idx]).group(1)
    tail = block[t_end]
    if not tail.rstrip().endswith(","):
        block = block[:t_end] + [tail.rstrip() + ","] + block[t_end + 1:]
    insert_at = t_end + 1
    new_block = (block[:insert_at]
                 + [f'{indent}"test_records": {value}']
                 + block[insert_at:])
    return new_block, f"{code}: 新增 test_records 声明"


# --------------------------------------------------------------- 主流程

def build_plan(root: Path, registry_path: Path, report_path: Path) -> dict:
    """算出「应该有哪些记录、每个记录长什么样」。纯函数，不写盘。"""
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    report, report_sha = load_report(report_path)
    try:
        report_rel = report_path.relative_to(root).as_posix()
    except ValueError:  # 报告在项目根之外：只记绝对路径，不猜相对关系
        report_rel = report_path.as_posix()
    generated = parse_report_time(report.get("generated_at", ""))
    report_meta = {
        "sha256": report_sha,
        "generated_at": generated.isoformat(),
        "generated_at_raw": str(report.get("generated_at")),
    }
    cases_by_file = passed_cases_by_file(report)
    counts_by_file = case_counts_by_file(report)

    plan: list[dict] = []
    skipped: list[dict] = []
    caps = iter_registry_caps(registry)
    for cap in caps:
        proj_root = (root / cap["project_root"]).resolve()
        rel_path = Path(cap["test_record_dir"]) / f"{cap['code']}{RECORD_SUFFIX}"
        abs_path = proj_root / rel_path
        entry = {
            "code": cap["code"],
            "name": cap["name"],
            "path": abs_path,
            "rel_path": rel_path.as_posix(),
            "declared_records": cap["declared_records"],
        }
        if not cap["tests"]:
            entry["has_record"] = False
            entry["cases"] = []
            skipped.append({"code": cap["code"],
                            "reason": "未声明 tests（缺的是 L1/L2 证据，不是测试记录）"})
            plan.append(entry)
            continue
        cases = []
        for path in cap["tests"]:
            cases.extend(cases_by_file.get(path, []))
        if not cases:
            entry["has_record"] = False
            entry["cases"] = []
            skipped.append({"code": cap["code"],
                            "reason": "声明的测试文件在报告里没有任何通过用例，不出记录（不臆造证据）"})
            plan.append(entry)
            continue
        entry["has_record"] = True
        entry["cases"] = cases
        entry["content"] = render_record(cap, cases_by_file, counts_by_file,
                                         report_meta, report_rel)
        plan.append(entry)
    return {"plan": plan, "skipped": skipped,
            "report_meta": report_meta, "report_rel": report_rel}


def registry_declarations(plan: list[dict]) -> dict[str, list[str]]:
    """每个 cap 的 test_records 声明（无记录者声明为空列表 = 明确不声明）。"""
    return {item["code"]: ([item["rel_path"]] if item["has_record"] else [])
            for item in plan}


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    registry_path = Path(args.registry) if args.registry else root / "governance/registry.json"
    report_path = Path(args.report) if args.report else root / "governance/test_report.json"
    if not registry_path.is_absolute():
        registry_path = root / registry_path
    if not report_path.is_absolute():
        report_path = root / report_path

    built = build_plan(root, registry_path, report_path)
    plan = built["plan"]
    skipped = built["skipped"]

    problems: list[str] = []
    changed: list[str] = []
    registry_notes: list[str] = []

    if args.check:
        for item in plan:
            if not item["has_record"]:
                continue
            if not item["path"].is_file():
                problems.append(f"缺记录文件：{item['rel_path']}")
                continue
            actual = item["path"].read_text(encoding="utf-8")
            if actual != item["content"]:
                problems.append(f"记录与证据不一致（需重跑生成器）：{item['rel_path']}")
        out_dirs = {item["path"].parent for item in plan if item["has_record"]}
        for out_dir in out_dirs:
            if not out_dir.is_dir():
                continue
            expected = {item["path"].name for item in plan if item["has_record"]}
            for extra in sorted(out_dir.glob("*" + RECORD_SUFFIX)):
                if extra.name not in expected:
                    problems.append(f"多余记录文件（没有任何能力点声明它）：{extra.name}")
        wanted = registry_declarations(plan)
        for item in plan:
            declared = item["declared_records"]
            if declared != wanted[item["code"]]:
                problems.append(
                    f"{item['code']} 的 test_records 声明应为 {wanted[item['code']]}，"
                    f"实为 {declared or '（未声明）'}")
    else:
        for item in plan:
            if not item["has_record"]:
                continue
            item["path"].parent.mkdir(parents=True, exist_ok=True)
            old = item["path"].read_text(encoding="utf-8") if item["path"].is_file() else None
            if old == item["content"]:
                continue
            item["path"].write_text(item["content"], encoding="utf-8")
            changed.append(item["rel_path"])

    if args.update_registry:
        wanted = registry_declarations(plan)
        text = registry_path.read_text(encoding="utf-8")
        new_text, registry_notes = update_registry_text(text, wanted)
        if new_text != text:
            registry_path.write_text(new_text, encoding="utf-8")
            changed.append(registry_path.relative_to(root).as_posix())
        else:
            changed.append(f"{registry_path.relative_to(root).as_posix()}（已是最新）")

    records = [item for item in plan if item["has_record"]]
    summary = {
        "schema": "ledger-test-records/1",
        "mode": "check" if args.check else "generate",
        "report": built["report_rel"],
        "source_sha256": built["report_meta"]["sha256"],
        "generated_at": built["report_meta"]["generated_at"],
        "records": len(records),
        "changed": changed,
        "registry_notes": registry_notes,
        "skipped": skipped,
        "problems": problems,
        "records_detail": [
            {"code": item["code"], "path": item["rel_path"],
             "cases": len(item["cases"])} for item in records
        ],
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        mode = "核对" if args.check else "生成"
        print(f"{mode} {len(records)} 份 L4 测试记录 · 证据 {built['report_rel']} "
              f"· sha256 {built['report_meta']['sha256'][:16]}")
        if changed:
            print("  变更：")
            for path in changed:
                print(f"    - {path}")
        else:
            print("  变更：无（幂等：重跑不产生 diff）")
        for item in skipped:
            print(f"  跳过 {item['code']}：{item['reason']}")
        for problem in problems:
            print(f"  [不一致] {problem}")

    if problems:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT), help="项目根（默认本仓库根）")
    ap.add_argument("--registry", help="registry.json 路径（默认 <root>/governance/registry.json）")
    ap.add_argument("--report", help="测试报告路径（默认 <root>/governance/test_report.json）")
    ap.add_argument("--check", action="store_true",
                    help="只核对记录/声明与证据是否一致，不写盘（有漂移 exit 1）")
    ap.add_argument("--update-registry", action="store_true",
                    help="把 test_records 声明同步进 registry（外科式改写，不重排版）")
    ap.add_argument("--json", action="store_true", help="机器可读汇总")
    args = ap.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
