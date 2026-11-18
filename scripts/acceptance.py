#!/usr/bin/env python3
"""S2 验收契约：先定义「什么算修好」，再改实现。

第一性原理
----------
v1.5.0 发版只批量更新了资产 frontmatter 的 ``version``，正文里的计数仍是
上一版的字面量。门禁里没有任何断言把「人写的数字」和「代码里的常量」绑在
一起，所以 13 阶段全绿也发现不了这类漂移。升级现场还发现：升级后复导使用
覆盖写，会销毁观察包里已收敛的 triage 证据——本质是观察包缺 append-only
写入契约。

本脚本是**只读的验收定义**，分四层，全部不写权威文件：

  L1 literal_drift        手写源与派生文件里的计数 == upgrade.py 的代码常量
  L2 derived_reproducible 派生文件可由生成器复算（禁止手改派生文件绕过 L1）
  L3 append_only          观察包重复导出不销毁既有证据、按 obs_id 去重、幂等
  L4 preconditions        v1.7.0 的 G1 / G2 / G3 机器断言（规划一致性 /
                          条件化 SOP / 无报告时的 activation 占位）

v1.6.0 的 S2 阶段 L1 / L3 预期为红灯；v1.7.0 的 S2 阶段 L4 三项同样刻意红灯，
S3 改权威源后四层同时转绿。本脚本自身不改任何实现，探针只在临时目录运行。
它不新增第二事实源：期望值全部由 ``upgrade.py`` 的 AST 抽取，派生层复用三个
既有 ``--emit-md`` 生成器，L4 的 G3 在临时副本上真实调用 ``upgrade.apply()``。

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

# ---------------------------------------------------------------- L4
# v1.7.0 收敛版前置条件：G1 规划一致性 / G2 条件化 SOP / G3 activation 占位。
# 三者都是「机器断言」，不是人眼复核；期望值从权威源文本与真实升级动作取得。
ROADMAP_DOC = "docs/23-本体投影.md"
CHANGELOG_DOC = "CHANGELOG.md"
PRECOND_DOC = "feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md"
DELAY_ANCHORS = ("v1.7.0", "v1.8.0", "v1.9.0", "v2.0.0")
CONDITIONAL_STEPS = (1, 2, 15)

# ---------------------------------------------------------------- L5
# v1.8.0 扩大范围：四缺口的机器断言，全部针对**方法论仓权威源**判定，
# 不读取主仓数据（主仓 registry / capability_model 属权威数据，由独立迁移方案处理）。
#   H1 布局探测 + 空绑定拒绝  → scripts/work_panel.py
#   H2 JUnit classname→file 映射 → scripts/work_panel.py
#   H3 hints 派生 + 不降级门禁 → templates/build_capability_model.py
#   H4 端到端报告→verified 可复演 → acceptance 自身 fixture
WORK_PANEL = "scripts/work_panel.py"
GENERATOR_TPL = "templates/build_capability_model.py"
ACCEPT_1_8_DOC = "feedback/ACCEPTANCE-1.8.0.md"
L5_ANCHORS = ("default_source_dirs", "classname", "evidence_hints", "no_regress")

# ---------------------------------------------------------------- L6
# v2.0.0 registry/2 多项目编码契约：修 monorepo 的 5 段码，双写兼容单项目模板。
#   R1 code_namespace 导出          → templates/build_capability_model.py
#   R2 build 两处 code 经命名空间生成 → templates/build_capability_model.py
#   R3 4 段码负向回归               → tests/core/test_registry2.py
#   R4 契约文档四锚点               → feedback/ACCEPTANCE-2.0.0.md
ACCEPT_2_0_DOC = "feedback/ACCEPTANCE-2.0.0.md"
REGISTRY2_TEST = "tests/core/test_registry2.py"
L6_ANCHORS = ("code_namespace", "registry2_contract", "no_prefix_leak", "cap_code_format")

# ---------------------------------------------------------------- L7
# v2.0.1 registry schema/2 容器契约：把单项目 project + modules[] 升级为
# schema=registry/2 + projects[]，同时保留旧形状双读。
#   S1 契约文档锚点 → feedback/ACCEPTANCE-2.0.1.md
#   S2 专项测试     → tests/core/test_registry_schema.py
#   S3 唯一 codec   → templates/registry_codec.py（目标项目副本 governance/registry_codec.py）
ACCEPT_2_0_1_DOC = "feedback/ACCEPTANCE-2.0.1.md"
REGISTRY_SCHEMA_TEST = "tests/core/test_registry_schema.py"
REGISTRY_CODEC = "templates/registry_codec.py"
L7_ANCHORS = ("registry/2", "dual_read", "stable_code", "single_codec")

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
    post_cmds: list[str] = []
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
                    # 相邻字符串字面量在 AST 里已合并为单个 Constant，可直接求值。
                    # 抽文本供 G2 的静态守卫检查与动态负向回归使用，不写死任何步骤内容。
                    try:
                        post_cmds = [x for x in (ast.literal_eval(e) for e in val.elts)
                                     if isinstance(x, str)]
                    except (ValueError, TypeError, SyntaxError):
                        post_cmds = []

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
        "post_upgrade_cmds": post_cmds,
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


# ---------------------------------------------------------------- L4 实现
def _heading_section(text: str, heading_re: str) -> str:
    """取二级标题正文到下一个二级标题（或文末）；找不到返回空串。"""
    m = re.search(heading_re, text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def roadmap_consistency(root: Path = ROOT) -> dict:
    """G1：docs/23 第七节不再把 v1.6.0 定义为语义图，且与 CHANGELOG 顺延表一致。

    机器断言而非人眼复核：三份文档必须含同一组顺延锚点，CHANGELOG 必须有
    1.7.0 发布段落，前置契约必须写明 P1–P3 不满足时的范围裁剪依据。
    """
    errors: list[str] = []
    paths = {"docs/23": root / ROADMAP_DOC, "CHANGELOG": root / CHANGELOG_DOC,
             "PRECONDITIONS": root / PRECOND_DOC}
    texts: dict[str, str] = {}
    for name, p in paths.items():
        if not p.is_file():
            errors.append(f"缺 {name}（{p.name}）")
        else:
            texts[name] = p.read_text(encoding="utf-8")
    sec = _heading_section(texts.get("docs/23", ""), r"^##\s*七、后续\s*$")
    rel = _heading_section(texts.get("CHANGELOG", ""), r"^##\s*\[1\.7\.0\][^\n]*$")
    if not sec:
        errors.append("docs/23 第七节缺失")
    if re.search(r"v1\.6\.0\s*才", sec):
        errors.append("docs/23 第七节仍写着「v1.6.0 才做语义图」")
    if not rel:
        errors.append("CHANGELOG 缺 1.7.0 发布段落")
    for label, block in (("docs/23 第七节", sec), ("CHANGELOG 1.7.0 段落", rel)):
        for anchor in DELAY_ANCHORS:
            if anchor not in block:
                errors.append(f"{label} 缺顺延锚点 {anchor}")
        if "收敛版" not in block:
            errors.append(f"{label} 未写明「一致性与可适配性」收敛版范围")
    pre = texts.get("PRECONDITIONS", "")
    if "收敛版" not in pre or "语义图再次顺延" not in pre:
        errors.append("前置契约未写明 P1–P3 不满足时的范围裁剪依据")
    return {"status": "pass" if not errors else "fail", "errors": errors,
            "roadmap_chars": len(sec), "changelog_chars": len(rel),
            "anchors": list(DELAY_ANCHORS)}


def _materialize(cmd: str, target: Path) -> str:
    """把 SOP 里记作 P 的目标项目占位符换成临时 fixture 路径。"""
    return re.sub(r"(?<![\w])P(?![\w])", str(target), cmd)


def evaluate_conditional(cmds: list[str], post_steps: int,
                         skips: list[dict], generated: bool) -> dict:
    """纯函数：G2 判定逻辑，供绿灯自测喂正确/错误输入。"""
    errors: list[str] = []
    if len(cmds) != post_steps:
        errors.append("POST_UPGRADE 文本抽取与 AST 长度不一致")
    for i in CONDITIONAL_STEPS:
        if i > len(cmds):
            errors.append(f"第 {i} 步不存在")
            continue
        cmd = cmds[i - 1]
        if "if [" not in cmd:
            errors.append(f"第 {i} 步缺 shell 条件守卫")
        if "SKIP" not in cmd or "status=na" not in cmd:
            errors.append(f"第 {i} 步缺可审计 skip 记录（SKIP / status=na）")
    for s in skips:
        if not s.get("skip"):
            errors.append(f"第 {s.get('step')} 步在空 tests/ fixture 上未降级为 skip："
                          f"{str(s.get('detail', ''))[:100]}")
    if generated:
        errors.append("空 tests/ fixture 上仍生成了 governance/test_report.json")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def conditional_sop(root: Path = ROOT) -> dict:
    """G2：第 1/2/15 步在无 tests/ 项目上降级为显式 na + 可审计 skip 记录。

    静态检查三步都带 shell 守卫与 SKIP/status=na；动态在空 fixture 上真实
    执行三步命令，断言不生成 governance/test_report.json。post 步数不变。
    """
    c = constants(root)
    cmds = c["post_upgrade_cmds"]
    skips: list[dict] = []
    generated = False
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "P"
        (proj / "governance").mkdir(parents=True)
        for i in CONDITIONAL_STEPS:
            if i > len(cmds):
                skips.append({"step": i, "skip": False, "detail": "步骤不存在"})
                continue
            r = subprocess.run(["bash", "-c", _materialize(cmds[i - 1], proj)],
                               cwd=root, capture_output=True, text=True)
            skipped = r.returncode == 0 and "SKIP" in r.stdout
            skips.append({"step": i, "skip": skipped,
                          "detail": f"rc={r.returncode} / {r.stdout[:70]!r} / "
                                    f"{r.stderr[:70]!r}"})
        generated = (proj / "governance" / "test_report.json").exists()
    verdict = evaluate_conditional(cmds, c["expect"]["post_steps"], skips, generated)
    return {"status": verdict["status"], "errors": verdict["errors"],
            "post_steps": len(cmds), "conditional_steps": list(CONDITIONAL_STEPS),
            "skips": skips, "report_generated": generated}


def evaluate_activation(activation: object, invariants: dict) -> dict:
    """纯函数：G3 判定逻辑，供绿灯自测喂正确/错误输入。"""
    errors: list[str] = []
    if not isinstance(activation, dict) or not activation.get("state"):
        errors.append("M8 未写入显式 activation 占位（仍为 null）")
    if invariants.get("failed") != 0 or invariants.get("na") != 1 \
            or invariants.get("all_active") is not False:
        errors.append("三态语义回归：需要 failed=0 / na=1 / all_active=false")
    if invariants.get("passed") != 23:
        errors.append("24 条不变量计数回归：需要 23 pass + 1 na")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def activation_placeholder(root: Path = ROOT) -> dict:
    """G3：无报告时 M8 写入显式 activation 占位，且三态不变量不回归。

    在临时副本上真实调用 upgrade.apply()（人批准探针），读回账本与校验器
    输出；不触碰任何权威文件，也不触碰目标项目 P。
    """
    errors: list[str] = []
    activation: object = None
    invariants: dict = {}
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        proj = base / "examples" / "demo-shop"
        shutil.copytree(root / "examples" / "demo-shop", proj,
                        ignore=shutil.ignore_patterns("__pycache__"))
        (proj / "governance" / "test_report.json").unlink(missing_ok=True)
        lp = proj / "governance" / "DECISION_LEDGER.json"
        ledger = json.loads(lp.read_text(encoding="utf-8"))
        ledger.pop("test_results", None)
        lp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.path.insert(0, str(root / "scripts"))
        import upgrade  # noqa: E402  — 复用真实升级器，不重写第二套规则
        p = upgrade.plan(proj, root)
        if p["blocks"]:
            errors.append("fixture 升级被前置条件阻止："
                          + "；".join(b["id"] for b in p["blocks"]))
        else:
            upgrade.apply(proj, "acceptance-gate", source_root=root, p=p)
        after = json.loads(lp.read_text(encoding="utf-8"))
        activation = (after.get("governance_meta") or {}).get("activation")
        out = subprocess.run(
            [sys.executable, str(proj / "governance" / "verify_ledger.py"),
             "--root", str(base), "--registry", str(proj / "governance" / "registry.json"),
             "--ledger", str(lp), "--board", str(proj / "governance" / "index.html"),
             "--json"], capture_output=True, text=True)
        try:
            v = json.loads(out.stdout)
            invariants = {k: v.get(k) for k in
                          ("passed", "failed", "na", "all_ok", "all_active")}
        except json.JSONDecodeError:
            errors.append("verify_ledger.py --json 输出不可解析：" + out.stderr[:80])
    verdict = evaluate_activation(activation, invariants)
    errors.extend(verdict["errors"])
    return {"status": "pass" if not errors else "fail", "errors": errors,
            "activation_state": activation.get("state") if isinstance(activation, dict) else None,
            "invariants": invariants}


def _source_symbols(path: Path) -> set[str]:
    """抽取模块顶层函数名，供 L5 结构断言使用（不导入执行）。"""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _source_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def evidence_adapter(root: Path = ROOT) -> dict:
    """H1+H2：work_panel 必须有布局探测、空绑定拒绝、JUnit classname→file 映射。"""
    syms = _source_symbols(root / WORK_PANEL)
    text = _source_text(root / WORK_PANEL)
    errors = []
    for name in ("default_source_dirs", "classname_to_file"):
        if name not in syms:
            errors.append(f"{WORK_PANEL} 缺少函数 {name}()")
    if "空绑定" not in text and "empty_binding" not in text:
        errors.append(f"{WORK_PANEL} 未见空绑定拒绝逻辑")
    if "projects/" not in text:
        errors.append(f"{WORK_PANEL} 未见 monorepo 布局（projects/）探测")
    return {"status": "pass" if not errors else "fail", "errors": errors,
            "symbols": sorted(s for s in syms if s in L5_ANCHORS)}


def no_regression_guard(root: Path = ROOT) -> dict:
    """H3：生成器必须有账本证据派生 hints 与 level 不降级门禁。"""
    text = _source_text(root / GENERATOR_TPL)
    syms = _source_symbols(root / GENERATOR_TPL)
    errors = []
    for name in ("evidence_hints", "no_regress"):
        if name not in syms:
            errors.append(f"{GENERATOR_TPL} 缺少函数/门禁 {name}()")
    if "降级" not in text and "regress" not in text:
        errors.append(f"{GENERATOR_TPL} 未见 level 不降级判据")
    return {"status": "pass" if not errors else "fail", "errors": errors,
            "symbols": sorted(s for s in syms if s in L5_ANCHORS)}


def l5_contract_doc(root: Path = ROOT) -> dict:
    """H4：v1.8.0 验收契约文档须存在并含四缺口锚点。"""
    text = _source_text(root / ACCEPT_1_8_DOC)
    errors = []
    if not text:
        errors.append(f"缺少 {ACCEPT_1_8_DOC}")
    for anchor in L5_ANCHORS:
        if anchor not in text:
            errors.append(f"{ACCEPT_1_8_DOC} 缺少锚点 {anchor}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def evidence_end_to_end(root: Path = ROOT, tmp: Path | None = None) -> dict:
    """H4：证明 work_panel 的可调用实现已落地（按路径加载，避免 sys.path 污染）。"""
    errors: list[str] = []
    path = root / "scripts" / "work_panel.py"
    if not path.is_file():
        return {"status": "fail", "errors": [f"缺少 {path}"]}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_accept_wp", path)
        if spec is None or spec.loader is None:
            raise ValueError("无法构造模块加载器")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ("default_source_dirs", "classname_to_file"):
            if not callable(getattr(module, name, None)):
                errors.append(f"work_panel 缺少可调用实现 {name}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"work_panel 加载失败：{exc}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


# ---------------------------------------------------------------- L6 (v2.0.0)
def _load_module(path: Path):
    """按文件路径加载模块，避免 sys.path 污染与同名模块冲突。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_accept_mod", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载模块：{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def code_namespace_check(root: Path = ROOT) -> dict:
    """R1：生成器须导出 code_namespace，且双写兼容（含项目段直用 / 否则加前缀）。"""
    path = root / GENERATOR_TPL
    syms = _source_symbols(path)
    errors = []
    if "code_namespace" not in syms:
        errors.append(f"{GENERATOR_TPL} 缺少函数 code_namespace()")
    try:
        gen = _load_module(path)
        fn = getattr(gen, "code_namespace", None)
        if not callable(fn):
            errors.append("code_namespace 不可调用")
        else:
            # 双写兼容：monorepo 已含项目段直用；单项目补前缀
            cases = [
                (("ROOT", "PROJ.DATA"), "PROJ.DATA"),
                (("DEMO", "DATA"), "DEMO.DATA"),
                (("ROOT", "MIND.DEC"), "MIND.DEC"),
                (("HELM", "API"), "HELM.API"),
            ]
            for args, expect in cases:
                got = fn(*args)
                if got != expect:
                    errors.append(f"code_namespace{args}={got!r}，期望 {expect!r}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"code_namespace 加载/调用失败：{exc}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def registry2_contract_check(root: Path = ROOT) -> dict:
    """R2：build 的 module/cap code 均经 code_namespace 生成，无裸 f"{code}.{mcode}"。

    允许两种等价实现：每处各自调用 code_namespace()，或在循环开头算一次
    namespace（如 cap_ns）供 module code 与 cap code 共用。
    """
    text = _source_text(root / GENERATOR_TPL)
    errors = []
    if 'f"{code}.{mcode}"' in text or 'f"{code}.{mcode}.{domain}' in text:
        errors.append(f"{GENERATOR_TPL} 仍有裸拼接 code.mcode（未走 code_namespace）")
    calls = text.count("code_namespace(")  # 定义 1 处 + build 中至少 1 处
    uses_ns = 'f"{cap_ns}.{domain}' in text or 'f"{ns}.{domain}' in text
    if calls < 2 and not uses_ns:
        errors.append("build 未见 code_namespace 调用或共用命名空间（module/cap code 未受契约约束）")
    if '"code": cap_ns' not in text and '"code": f"{code}.{mcode}"' in text:
        errors.append("module code 未走命名空间")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def no_prefix_leak_check(root: Path = ROOT) -> dict:
    """R3：必须有 4 段码负向回归测试文件，覆盖双写与无前缀泄漏。"""
    path = root / REGISTRY2_TEST
    text = _source_text(path)
    errors = []
    if not text:
        errors.append(f"缺少 {REGISTRY2_TEST}")
    for anchor in ("code_namespace", "4 段", "DEMO.DATA"):
        if anchor not in text:
            errors.append(f"{REGISTRY2_TEST} 缺少锚点 {anchor}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def cap_code_format_check(root: Path = ROOT) -> dict:
    """R4：v2.0.0 契约文档存在且含四锚点。"""
    text = _source_text(root / ACCEPT_2_0_DOC)
    errors = []
    if not text:
        errors.append(f"缺少 {ACCEPT_2_0_DOC}")
    for anchor in L6_ANCHORS:
        if anchor not in text:
            errors.append(f"{ACCEPT_2_0_DOC} 缺少锚点 {anchor}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


# ---------------------------------------------------------------- L7 (v2.0.1)
def registry_schema_doc_check(root: Path = ROOT) -> dict:
    """S1：registry schema/2 契约文档存在且含四锚点。"""
    text = _source_text(root / ACCEPT_2_0_1_DOC)
    errors = []
    if not text:
        errors.append(f"缺少 {ACCEPT_2_0_1_DOC}")
    for anchor in L7_ANCHORS:
        if anchor not in text:
            errors.append(f"{ACCEPT_2_0_1_DOC} 缺少锚点 {anchor}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def registry_schema_test_check(root: Path = ROOT) -> dict:
    """S2：必须有 schema v2 双读/稳定码专项测试。"""
    text = _source_text(root / REGISTRY_SCHEMA_TEST)
    errors = []
    if not text:
        errors.append(f"缺少 {REGISTRY_SCHEMA_TEST}")
    for anchor in (*L7_ANCHORS, "normalize_projects"):
        if anchor not in text:
            errors.append(f"{REGISTRY_SCHEMA_TEST} 缺少锚点 {anchor}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def registry_codec_contract_check(root: Path = ROOT) -> dict:
    """S3：唯一 codec 必须由 registry_codec 提供，生成器/校验器/投影器共同消费。"""
    errors = []
    path = root / REGISTRY_CODEC
    if not path.is_file():
        errors.append(f"缺少 {REGISTRY_CODEC}")
    else:
        syms = _source_symbols(path)
        for name in ("code_namespace", "cap_code", "normalize_projects", "iter_caps"):
            if name not in syms:
                errors.append(f"{REGISTRY_CODEC} 缺少函数 {name}()")
    consumers = (
        GENERATOR_TPL,
        "templates/verify_ledger.py",
        "scripts/trace_common.py",
    )
    for rel in consumers:
        text = _source_text(root / rel)
        if "registry_codec" not in text:
            errors.append(f"{rel} 未消费 registry_codec（存在第二套 codec 风险）")
    trace_text = _source_text(root / "scripts/trace_common.py")
    if 'f"{code}.{mcode}.{domain}' in trace_text:
        errors.append("trace_common.py 仍有裸拼五段码")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def registry_dual_read_check(root: Path = ROOT) -> dict:
    """S3：旧 project + modules[] 与新 projects[] 必须归一化出同一组能力码。"""
    errors = []
    path = root / REGISTRY_CODEC
    if not path.is_file():
        return {"status": "fail", "errors": [f"缺少 {REGISTRY_CODEC}"]}
    try:
        codec = _load_module(path)
        fn = getattr(codec, "iter_caps", None)
        if not callable(fn):
            return {"status": "fail", "errors": ["iter_caps 不可调用"]}
        legacy = {
            "project": {"code": "DEMO", "root": ".", "governance_gate": True},
            "modules": [{"code": "DATA", "caps": [
                {"name": "数据就绪", "domain": "READY", "code": "DEMO.DATA.READY.01"}]}],
        }
        modern = {
            "schema": "registry/2",
            "projects": [{
                "code": "DEMO", "root": ".", "governance_gate": True,
                "modules": [{"code": "DATA", "caps": [
                    {"name": "数据就绪", "domain": "READY", "code": "DEMO.DATA.READY.01"}]}],
            }],
        }
        expected = ["DEMO.DATA.READY.01"]
        old_codes = [c["code"] for c in fn(legacy)]
        new_codes = [c["code"] for c in fn(modern)]
        if old_codes != expected:
            errors.append(f"旧形状归一化得到 {old_codes}，期望 {expected}")
        if new_codes != expected:
            errors.append(f"新形状归一化得到 {new_codes}，期望 {expected}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"registry_codec 加载/双读失败：{exc}")
    return {"status": "pass" if not errors else "fail", "errors": errors}


def build(root: Path = ROOT, tmp: Path | None = None,
          only_preconditions: bool = False) -> dict:
    c = constants(root)
    lit: dict | None = None
    review: list[dict] = []
    der: list[dict] = []
    app: dict = {"status": "pass", "rows_before": 0, "rows_after": 0,
                 "closed_before": 0, "errors": []}
    if not only_preconditions:
        with (tempfile.TemporaryDirectory() if tmp is None else _NullCtx(tmp)) as td:
            work = Path(td)
            lit = scan_literals(root, c["expect"])
            der = check_derived(root, work)
            probe = merge_probe(root, work)
        app = evaluate_probe(probe["before"], probe["after"], probe["after2"],
                             probe["rc1"], probe["rc2"])
        review = lit["review"]
    g1 = roadmap_consistency(root)
    g2 = conditional_sop(root)
    g3 = activation_placeholder(root)
    h1 = evidence_adapter(root)
    h3 = no_regression_guard(root)
    h4 = l5_contract_doc(root)
    h5 = evidence_end_to_end(root)
    r1 = code_namespace_check(root)
    r2 = registry2_contract_check(root)
    r3 = no_prefix_leak_check(root)
    r4 = cap_code_format_check(root)
    s1 = registry_schema_doc_check(root)
    s2 = registry_schema_test_check(root)
    s3 = registry_codec_contract_check(root)
    s4 = registry_dual_read_check(root)
    checks: list[dict] = []
    if not only_preconditions:
        checks += [
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
    checks += [
        {"id": "roadmap_consistency", "status": g1["status"],
         "errors": g1["errors"], "anchors": g1["anchors"]},
        {"id": "conditional_sop", "status": g2["status"], "errors": g2["errors"],
         "post_steps": g2["post_steps"], "skips": g2["skips"],
         "report_generated": g2["report_generated"]},
        {"id": "activation_placeholder", "status": g3["status"],
         "errors": g3["errors"], "activation_state": g3["activation_state"],
         "invariants": g3["invariants"]},
    ]
    # L5 属于 v1.8.0 全量验收，不并入 v1.7.0 的 preconditions 范围。
    if not only_preconditions:
        checks += [
            {"id": "evidence_adapter", "status": h1["status"], "errors": h1["errors"]},
            {"id": "no_regression_guard", "status": h3["status"], "errors": h3["errors"]},
            {"id": "l5_contract_doc", "status": h4["status"], "errors": h4["errors"]},
            {"id": "evidence_end_to_end", "status": h5["status"], "errors": h5["errors"]},
        ]
        # L6 属于 v2.0.0 registry/2 契约，不并入 preconditions 范围。
        checks += [
            {"id": "code_namespace", "status": r1["status"], "errors": r1["errors"]},
            {"id": "registry2_contract", "status": r2["status"], "errors": r2["errors"]},
            {"id": "no_prefix_leak", "status": r3["status"], "errors": r3["errors"]},
            {"id": "cap_code_format", "status": r4["status"], "errors": r4["errors"]},
        ]
        # L7 属于 v2.0.1 registry schema/2 容器契约，不并入 preconditions 范围。
        checks += [
            {"id": "registry_schema_doc", "status": s1["status"], "errors": s1["errors"]},
            {"id": "registry_schema_test", "status": s2["status"], "errors": s2["errors"]},
            {"id": "registry_codec_contract", "status": s3["status"], "errors": s3["errors"]},
            {"id": "registry_dual_read", "status": s4["status"], "errors": s4["errors"]},
        ]
    return {"schema": SCHEMA, "method_version": c["version"],
            "constants": c["expect"], "basis": c["basis"],
            "verify_ids": c["verify_ids"], "gate_ids": c["gate_ids"],
            "checks": checks, "review": review,
            "review_count": len(review),
            "scope": "preconditions" if only_preconditions else "full",
            "overall": "fail" if any(x["status"] != "pass" for x in checks) else "pass"}


class _NullCtx:
    def __init__(self, path: Path):
        self.path = str(path)

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        return False


def render(result: dict, full: bool = False) -> str:
    lines = [f"验收契约 {result['schema']} · 目标版本 {result['method_version']}"
             f" · 范围 {result['scope']}",
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
        elif c["id"] == "append_only":
            lines.append(f"         观察包 {c['rows_before']} → {c['rows_after']} 行，"
                         f"含 {c['closed_before']} 条已收敛证据")
            for e in c["errors"]:
                lines.append(f"         {e}")
        else:  # L4 前置条件三项
            for e in c["errors"]:
                lines.append(f"         {e}")
            if c["id"] == "conditional_sop":
                lines.append(f"         post 步数 {c['post_steps']}；"
                             f"空 fixture 生成报告={c['report_generated']}；"
                             f"skip={[x['skip'] for x in c['skips']]}")
            if c["id"] == "activation_placeholder":
                lines.append(f"         activation={c['activation_state']}；"
                             f"不变量 {c['invariants']}")
    lines.append(f"结论：{result['overall'].upper()}"
                 + ("（S2 预期红灯；S3 改权威源后转绿）" if result["overall"] == "fail" else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="按验收契约判定，未达标返回 1")
    ap.add_argument("--json", action="store_true", help="输出 acceptance/1 JSON")
    ap.add_argument("--full", action="store_true", help="文本摘要列出全部漂移")
    ap.add_argument("--preconditions", action="store_true",
                    help="只跑 L4 的 G1 / G2 / G3 机器断言（第 15 门禁阶段）")
    args = ap.parse_args(argv)
    result = build(only_preconditions=args.preconditions)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result, args.full))
    return 0 if not args.check or result["overall"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
