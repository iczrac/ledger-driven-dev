#!/usr/bin/env python3
"""S2 验收契约：先定义「什么算修好」，再改实现。

第一性原理
----------
v1.5.0 发版只批量更新了资产 frontmatter 的 ``version``，正文里的计数仍是
上一版的字面量。门禁里没有任何断言把「人写的数字」和「代码里的常量」绑在
一起，所以 13 阶段全绿也发现不了这类漂移。升级现场还发现：升级后复导使用
覆盖写，会销毁观察包里已收敛的 triage 证据——本质是观察包缺 append-only
写入契约。

本脚本是**只读的验收定义**，分三层，全部不写权威文件：

  L1 literal_drift        手写源与派生文件里的计数 == upgrade.py 的代码常量
  L2 derived_reproducible 派生文件可由生成器复算（禁止手改派生文件绕过 L1）
  L3 append_only          观察包重复导出不销毁既有证据、按 obs_id 去重、幂等

S2 阶段 L1 / L3 预期为红灯；S3 改权威源后三层同时转绿。本脚本自身不改任何
实现，探针只在临时目录运行。它不新增第二事实源：期望值全部由 ``upgrade.py``
的 AST 抽取，派生层复用三个既有 ``--emit-md`` 生成器。

纪律
----
1. 只读、无时间戳、无绝对路径、输出确定性；
2. 检测器自身豁免字面量扫描，避免自指级联；
3. 历史演进陈述（版本对比 / 扩到 / 新增的）归入 review，不阻断，供人工复核；
4. 派生文件同时受 L1 与 L2 约束：S3 必须改生成器源文本再重算，不能手改派生文件。

输出 schema: acceptance/1。
用法：
    python3 scripts/acceptance.py --check --json
    python3 scripts/acceptance.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "acceptance/1"
UPGRADE = "scripts/upgrade.py"

# governance_meta 的七个版本轴。这是「契约声明」，由 constants() 自检每个键
# 确实被 upgrade.py 消费，避免变成凭空手写的第二份清单。
AXIS_KEYS = (
    "method_version", "ledger_version", "tools", "method_assets",
    "board_skeleton", "installed_assets", "ontology_digest",
)

# 扫描范围：描述当前状态的人写源 + 机器渲染的派生文件 + 生成器里的说明文本。
# CHANGELOG / RELEASE_CHECKLIST / feedback/ 是发布历史与现场证据，天然不在范围内。
SCAN_GLOBS = (
    "README.md",
    "docs/[0-9][0-9]-*.md",
    "docs/STANDARD.md",
    "docs/generated/*.md",
    "experts/*/EXPERT.md",
    "skills/*/SKILL.md",
    "scripts/*.py",
)
# 检测器自身含期望数字，豁免以避免自指。
EXEMPT_FILES = {"scripts/acceptance.py"}

# 三个派生文件由既有生成器重算；这里只做编排，不定义新的渲染口径。
DERIVED = (
    ("docs/generated/FILE_LAYOUT.md", "scripts/file_layout.py"),
    ("docs/generated/SCENARIO_MATRIX.md", "scripts/scenario_matrix.py"),
    ("docs/generated/TEST_MODULES.md", "scripts/test_modules.py"),
)

CN = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
      "六": 6, "七": 7, "八": 8, "九": 9}
TOKEN = re.compile(r"([0-9]+|[一二三四五六七八九十]+)\s*(轴|步|项)")
VERSION_RE = re.compile(r"v?\d+\.\d+\.\d+")
EVOLVE_RE = re.compile(
    r"扩到|起[一二三四五六七八九十0-9]+轴|新增的|从版本|曾为|旧版"
    r"|(?:[0-9]+)\s*(?:→|->)\s*(?:\*\*)?(?:[0-9]+)")
RANGE_RE = re.compile(r"第\s*[0-9]+\s*[–\-~]\s*[0-9]+\s*步")


def to_int(s: str) -> int | None:
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not s:
        return None
    if "十" in s:
        a, _, b = s.partition("十")
        tens = CN.get(a, 1) if a else 1
        ones = CN.get(b, 0) if b else 0
        return tens * 10 + ones if (not a or a in CN) and (not b or b in CN) else None
    return CN[s] if len(s) == 1 and s in CN else None


def constants(root: Path = ROOT) -> dict:
    """从 upgrade.py 的 AST 抽取期望计数，不 import、不执行升级器。"""
    src = (root / UPGRADE).read_text(encoding="utf-8")
    tree = ast.parse(src)
    version = None
    pre_steps = post_steps = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            val = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
            val = node.value
        else:
            continue
        if val is None:
            continue
        for name in names:
            if name == "METHOD_VERSION" and isinstance(val, ast.Constant):
                version = str(val.value)
            if name in ("PRE_UPGRADE", "POST_UPGRADE") and isinstance(val, (ast.List, ast.Tuple)):
                if name == "PRE_UPGRADE":
                    pre_steps = len(val.elts)
                else:
                    post_steps = len(val.elts)

    verify_ids: set[str] = set()
    gate_ids: set[str] = set()
    verify_fn = next((n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == "verify"), None)
    if verify_fn is not None:
        for sub in ast.walk(verify_fn):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "add" and sub.args
                    and isinstance(sub.args[0], ast.Constant)
                    and isinstance(sub.args[0].value, str)):
                verify_ids.add(sub.args[0].value)
            if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Subscript):
                sl = sub.left.slice
                if isinstance(sl, ast.Constant) and sl.value == "id":
                    for comp in sub.comparators:
                        if isinstance(comp, (ast.Tuple, ast.List, ast.Set)):
                            gate_ids |= {e.value for e in comp.elts
                                         if isinstance(e, ast.Constant)
                                         and isinstance(e.value, str)}

    basis_errors = []
    for key in AXIS_KEYS:
        if key not in src:
            basis_errors.append(f"轴 {key} 未被 upgrade.py 消费，契约声明失效")
    for label, val in (("version", version), ("pre_steps", pre_steps),
                       ("post_steps", post_steps), ("verify_checks", len(verify_ids) or None),
                       ("gate_criteria", len(gate_ids) or None)):
        if val is None:
            basis_errors.append(f"无法从 AST 抽取 {label}")

    return {
        "version": version,
        "expect": {"axis": len(AXIS_KEYS), "pre_steps": pre_steps,
                   "post_steps": post_steps, "verify_checks": len(verify_ids),
                   "gate_criteria": len(gate_ids)},
        "verify_ids": sorted(verify_ids), "gate_ids": sorted(gate_ids),
        "basis": f"{UPGRADE} AST：METHOD_VERSION / PRE_UPGRADE / POST_UPGRADE 长度 / "
                 f"verify() 内 add() 去重 id / c['id'] in (...) 判据元组",
        "basis_errors": basis_errors,
    }


def historical(line: str) -> bool:
    """历史演进陈述（版本对比 / 扩到 / 新增的）不参与硬失败，归入 review。"""
    if EVOLVE_RE.search(line):
        return True
    return bool(VERSION_RE.search(line) and re.search(r"新增|起|扩|→|曾", line))


def classify(line: str, m: re.Match) -> tuple[str, int] | None:
    n = to_int(m.group(1))
    if n is None:
        return None
    unit = m.group(2)
    local = line[max(0, m.start() - 26): min(len(line), m.end() + 26)]
    # 轴：只认「版本 N 轴 / governance_meta 的 N 轴」这类当前定义陈述。
    # 不能把「场景矩阵十轴」等其他维度的轴算进来。
    if unit == "轴" and re.search(
            r"版本|governance_meta|ontology_digest|installed_assets|method_assets", local):
        return ("axis", n)
    if unit == "步":
        if RANGE_RE.search(line):
            return None
        # 「这一步 / 下一步 / 每一步」以及「1 步升级前基线」都不是 post 步数；
        # post 步数当前为两位数，单个 1 步只可能是 pre 或口语量词。
        if n < 2 or re.search(r"升级前|pre_upgrade", local):
            return None
        if re.search(r"post_upgrade|POST_UPGRADE|升级后|升级流程|SOP|重跑|重新取证", local):
            return ("post_steps", n)
        return None
    if unit == "项":
        # scenario_guard 的「14 项检查 / checks」属于场景预检，不是 upgrade verify。
        if re.search(r"scenario-preflight|preflight|scenario_guard|场景预检", local):
            return None
        if re.search(r"判据|关键检查", local):
            return ("gate_criteria", n)
        if re.search(r"checks|verify|Verify|复验|检查|校验项", local):
            return ("verify_checks", n)
        if re.search(r"upgrade_complete|全\s*`?pass|全部\s*`?pass", local):
            return ("gate_criteria", n)
    return None


def scan_literals(root: Path, expect: dict) -> dict:
    drifts: list[dict] = []
    review: list[dict] = []
    scanned = 0
    paths = sorted({p for pat in SCAN_GLOBS for p in root.glob(pat) if p.is_file()})
    for p in paths:
        rel = p.relative_to(root).as_posix()
        if rel in EXEMPT_FILES:
            continue
        scanned += 1
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not TOKEN.search(line):
                continue
            is_hist = historical(line)
            for m in TOKEN.finditer(line):
                hit = classify(line, m)
                if hit is None:
                    continue
                kind, actual = hit
                want = expect.get(kind)
                if want is None or actual == want:
                    continue
                item = {"path": rel, "line": lineno, "kind": kind,
                        "actual": actual, "expected": want,
                        "excerpt": line.strip()[:120]}
                (review if is_hist else drifts).append(item)
    return {"scanned_files": scanned, "drifts": drifts, "review": review,
            "drift_count": len(drifts), "review_count": len(review)}


def check_derived(root: Path, tmp: Path) -> list[dict]:
    items = []
    for rel, gen in DERIVED:
        out = tmp / Path(rel).name
        proc = subprocess.run([sys.executable, gen, "--emit-md", str(out)],
                              cwd=root, capture_output=True, text=True)
        target = root / rel
        ok = (proc.returncode == 0 and out.is_file() and target.is_file()
              and out.read_bytes() == target.read_bytes())
        items.append({"path": rel, "generator": gen, "reproducible": ok,
                      "reason": "" if ok else (proc.stderr.strip()[:120] or "渲染结果与磁盘不一致")})
    return items


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def merge_probe(root: Path, tmp: Path) -> dict:
    """在临时副本上连跑两次真实 export，绝不触碰 feedback/ 里的权威观察包。"""
    src = root / "feedback" / "observations.jsonl"
    out = tmp / "observations.jsonl"
    shutil.copyfile(src, out)
    before = _rows(out)
    cmd = [sys.executable, "scripts/ledger_feedback.py", "export",
           "--target", "examples/demo-shop", "--out", str(out),
           "--phase", "after-upgrade", "--no-probe",
           "--apply", "--approved-by", "acceptance-gate"]
    r1 = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    after = _rows(out)
    r2 = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    after2 = _rows(out)
    return {"before": before, "after": after, "after2": after2,
            "rc1": r1.returncode, "rc2": r2.returncode}


def evaluate_probe(before: list[dict], after: list[dict], after2: list[dict],
                   rc1: int = 0, rc2: int = 0) -> dict:
    """纯函数：判定 append-only 契约。单测直接喂正确/错误结果验证判定逻辑。"""
    errors: list[str] = []
    if rc1 or rc2:
        errors.append(f"导出命令失败：rc={rc1},{rc2}")
    seen: set[str] = set()
    for o in after:
        oid = o.get("obs_id")
        if oid in seen:
            errors.append(f"obs_id 重复：{oid}")
        seen.add(oid)
    missing = [o.get("obs_id") for o in before if o.get("obs_id") not in seen]
    if missing:
        errors.append(f"append-only 违例：{len(missing)} 条既有观察消失")
    closed = {o.get("obs_id"): o for o in before if o.get("status") == "closed"}
    after_map = {o.get("obs_id"): o for o in after}
    for oid, o in closed.items():
        if oid not in after_map:
            errors.append(f"已收敛 triage 证据被销毁：{oid}")
            continue
        for key in ("status", "disposition", "artifact_ref", "reason", "approved_by"):
            if after_map[oid].get(key) != o.get(key):
                errors.append(f"{oid} 的 {key} 被改写")
    if len(after) < len(before):
        errors.append("重复导出行数少于原包：既有观察未保留")
    if after2 != after:
        errors.append("连续两次导出不幂等")
    return {"status": "pass" if not errors else "fail", "errors": errors,
            "rows_before": len(before), "rows_after": len(after),
            "closed_before": len(closed)}


def build(root: Path = ROOT, tmp: Path | None = None) -> dict:
    c = constants(root)
    with (tempfile.TemporaryDirectory() if tmp is None else _NullCtx(tmp)) as td:
        work = Path(td)
        lit = scan_literals(root, c["expect"])
        der = check_derived(root, work)
        probe = merge_probe(root, work)
    app = evaluate_probe(probe["before"], probe["after"], probe["after2"],
                         probe["rc1"], probe["rc2"])
    checks = [
        {"id": "literal_drift",
         "status": "fail" if lit["drifts"] or c["basis_errors"] else "pass",
         "scanned_files": lit["scanned_files"], "drift_count": lit["drift_count"],
         "items": lit["drifts"], "basis_errors": c["basis_errors"]},
        {"id": "derived_reproducible",
         "status": "pass" if all(x["reproducible"] for x in der) else "fail",
         "items": der},
        {"id": "append_only", "status": app["status"],
         "rows_before": app["rows_before"], "rows_after": app["rows_after"],
         "closed_before": app["closed_before"], "errors": app["errors"]},
    ]
    return {"schema": SCHEMA, "method_version": c["version"],
            "constants": c["expect"], "basis": c["basis"],
            "verify_ids": c["verify_ids"], "gate_ids": c["gate_ids"],
            "checks": checks, "review": lit["review"],
            "review_count": lit["review_count"],
            "overall": "fail" if any(x["status"] != "pass" for x in checks) else "pass"}


class _NullCtx:
    def __init__(self, path: Path):
        self.path = str(path)

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        return False


def render(result: dict, full: bool = False) -> str:
    lines = [f"验收契约 {result['schema']} · 目标版本 {result['method_version']}",
             f"代码常量：轴={result['constants']['axis']} "
             f"pre={result['constants']['pre_steps']} "
             f"post={result['constants']['post_steps']} "
             f"verify={result['constants']['verify_checks']} "
             f"判据={result['constants']['gate_criteria']}",
             f"依据：{result['basis']}"]
    for c in result["checks"]:
        lines.append(f"  [{c['status'].upper():4}] {c['id']}")
        if c["id"] == "literal_drift":
            lines.append(f"         扫描 {c['scanned_files']} 文件，"
                         f"漂移 {c['drift_count']} 处，历史复核 {result['review_count']} 处")
            for it in (c["items"] if full else c["items"][:8]):
                lines.append(f"         {it['path']}:{it['line']} "
                             f"{it['kind']} {it['actual']} → 应为 {it['expected']}")
            if not full and c["drift_count"] > 8:
                lines.append(f"         ... 其余 {c['drift_count'] - 8} 处见 --json")
            for e in c["basis_errors"]:
                lines.append(f"         [basis] {e}")
        elif c["id"] == "derived_reproducible":
            for it in c["items"]:
                lines.append(f"         {'OK ' if it['reproducible'] else 'STALE '}{it['path']}"
                             + ("" if it["reproducible"] else f" — {it['reason']}"))
        else:
            lines.append(f"         观察包 {c['rows_before']} → {c['rows_after']} 行，"
                         f"含 {c['closed_before']} 条已收敛证据")
            for e in c["errors"]:
                lines.append(f"         {e}")
    lines.append(f"结论：{result['overall'].upper()}"
                 + ("（S2 预期红灯；S3 改权威源后转绿）" if result["overall"] == "fail" else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="按验收契约判定，未达标返回 1")
    ap.add_argument("--json", action="store_true", help="输出 acceptance/1 JSON")
    ap.add_argument("--full", action="store_true", help="文本摘要列出全部漂移")
    args = ap.parse_args(argv)
    result = build()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result, args.full))
    return 0 if not args.check or result["overall"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
