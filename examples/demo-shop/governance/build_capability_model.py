#!/usr/bin/env python3
"""从真实文件系统证据生成能力模型（编码 + 完成度 + 嵌套组件树 + 文档索引）。

这是 ledger-driven-dev 方法的核心生成器。它把「项目做了什么、做到什么程度、
对应哪些文档、下一步该干什么」从散落的报告里收敛成一份可机读的账本，
再由看板渲染成可视化，供人查阅、供 AI 规划与编码。

设计原则
--------
1. 完成度不手填：由证据（契约/源码/单测/测试记录/治理门禁）自动判定 L0-L5。
2. 编码稳定：四段式 {项目}.{模块}.{能力域}.{序号}，不随名称变化。
3. 可复算：重跑即刷新；证据消失则等级自动回落。
4. 单一事实源：结果写入 DECISION_LEDGER.json 的 capability_model + architecture。
5. 索引可见：能力/规划都能点开对应文档，组件以真实嵌套树呈现。
6. 路径全集取自仓库：只引用 git 已跟踪的路径（见 RepoScope）。账本描述的是
   「仓库里有什么」，不是「这台机器上有什么」——否则干净检出必红、本机常绿。

用法
----
    python3 build_capability_model.py --root examples/demo-shop
    python3 build_capability_model.py --root . --dry-run
    python3 build_capability_model.py --root . --registry custom.json --ledger out.json --no-board
    python3 build_capability_model.py --root . --expect-fingerprint <fp> --strict-evidence

配置
----
项目定义放在 <root>/governance/registry.json（可用 --registry 覆盖），格式见
templates/registry.example.json。

依赖：仅标准库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# v2.0.1：唯一 registry codec。脚本被复制到目标项目时，sys.path[0] 是脚本目录；
# 被测试以 spec 方式加载时，显式补同目录，避免第二套编码实现。
try:
    from registry_codec import cap_code as codec_cap_code
    from registry_codec import code_namespace as _codec_code_namespace
    from registry_codec import normalize_projects
except ModuleNotFoundError:  # pragma: no cover - 仅在 spec 加载路径触发
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from registry_codec import cap_code as codec_cap_code
    from registry_codec import code_namespace as _codec_code_namespace
    from registry_codec import normalize_projects

# 场景预检契约：与 scenario_guard.py 保持一致；跨版本直写会破坏历史语义。
SUPPORTED_LEDGER_VERSIONS = {"1.0"}

# ---- 成熟度定义（可机判定的证据规则）----
LEVELS = {
    0: {"code": "L0", "name": "规划中", "rule": "仅出现在规划文档，无契约/源码"},
    1: {"code": "L1", "name": "契约已定", "rule": "contracts/ 目录有契约文件"},
    2: {"code": "L2", "name": "代码已落地", "rule": "src/ 有对应实现模块"},
    3: {"code": "L3", "name": "单测覆盖", "rule": "tests/unit/ 有对应测试"},
    4: {"code": "L4", "name": "运行验证", "rule": "docs/test_records/ 有测试记录"},
    5: {"code": "L5", "name": "生产闭环", "rule": "有治理门禁 + 运行台账/看板"},
}
LEVELS_CAVEAT = "L5 授予配置了 governance_gate=true 的项目；其他项目最高 L4。"

# ---- 证据分层（evidence tier）----
# 与成熟度正交：level 回答"做到哪一级"，tier 回答"这一级的证据是声明还是实测"。
# declared = 证据文件存在（生成器扫描可见）；verified = 有通过的测试报告证明其真跑过。
EVIDENCE_TIER_SPEC = {
    "purpose": "区分『写了测试文件』与『测试真实通过』，消除只看存在性造成的假绿灯。",
    "tiers": {
        "declared": "仅证据文件存在，未找到可核对的通过测试报告（默认，向后兼容）。",
        "verified": "存在 ledger-test-report 报告，且该能力的单测文件在报告中有 pass 记录。",
    },
    "source": "测试报告由 scripts/run_tests.py 生成（标准库 unittest），经 --test-report 传入。",
    "matching": "报告 cases[].file 与能力 unit_test 证据路径的 basename 匹配，且 status=pass、overall=pass。",
    "rule": "tier 只升不假：无报告或缺 pass 记录一律 declared；报告 fail/error 不得升级任何能力。",
    "invariant": "verified 必须指向真实存在的通过用例；测试记录被删则回落 declared。",
}

# ---- 历史层 / 经验层规范（写入账本，供人、AI、校验器共同消费）----
HISTORY_SPEC = {
    "purpose": "append-only 状态演进：只记录由证据/等级/文档真实变化驱动的事件，重跑不产生噪音。",
    "append_only": True,
    "fingerprint": "对派生状态（等级/完成度/证据路径/文档索引路径/决策引用）规范化排序后取 sha256 前 16 位；仅当与末事件不同才追加。",
    "replay": "每个事件携带 state_digest（当时完整能力状态），可重建任意时点快照。",
    "event_types": ["genesis", "change", "manual"],
    "invariant": "events[i].fingerprint_before == events[i-1].fingerprint_after；seq 从 1 连续递增。",
}
LESSONS_SPEC = {
    "purpose": "从历史沉淀可复用经验：机器识别候选信号，人/AI 确认后补充洞察与行动，任务卡自动携带相关经验。",
    "workflow": [
        "生成器从历史产生 candidates（降级 / 长期停滞 / 决策被取代），不替人下结论；",
        "人/AI 将候选确认成 items，填写 insight（学到了什么）与 action（下次怎么做）；",
        "next_queue 按 scope 匹配 confirmed 经验并附到任务卡，让下一轮站在前人结论上开工。",
    ],
    "candidate_rules": ["downgrade", "stagnation", "superseded_decision"],
    "status": ["draft", "confirmed", "retired"],
}

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
            ".md", ".json", ".yaml", ".yml", ".toml", ".sql", ".html"}
KEY_RE = re.compile(
    r"(engine|core|runner|pipeline|registry|gateway|gate|contract|router|adapter|"
    r"service|store|repository|handler|validator|client|manager|controller)",
    re.I,
)
PLAN_RE = re.compile(r"(plan|roadmap|方案|规划|guide|workflow|spec|设计|治理)", re.I)


# ------------------------------ 路径工具 ------------------------------

def rel_path(repo_root: Path, p: Path) -> str:
    """统一成仓库根相对路径；无法相对时退回绝对路径。"""
    try:
        return str(p.relative_to(repo_root))
    except ValueError:
        return str(p)


class RepoScope:
    """路径全集：账本只允许引用「仓库里有的东西」。

    为什么需要它
    ------------
    生成器原先直接遍历文件系统，于是本机被 .gitignore 的运行产物（``data/``、
    ``logs/``、``*.egg-info``）和还没入库的临时测试也会被写进账本。结果是账本
    记录「这台机器上有什么」而不是「仓库里有什么」：本机永远绿，干净检出必红。
    这是最坏的一类绿灯——它只在作者机器上成立，别人一 clone 就是假的。

    做法
    ----
    文件全集取自 git index（``git ls-files``）。不在 index 里的路径一律看不见，
    因此本机与干净检出产出同一份结果，差异不再有藏身之处。

    降级
    ----
    非 git 环境（导出的 tarball、示例的临时副本）无法读 index，退回文件系统
    全集，并由 ``verified`` 标为 False——此时调用方必须打印警告，绝不假装
    「已核对过仓库」。
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.files: set[str] | None = None
        self.dirs: set[str] = set()
        self.why = ""
        self._load()

    def _load(self) -> None:
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.root), "ls-files", "-z"],
                capture_output=True, check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.why = f"读不到 git index（{type(exc).__name__}），退回文件系统全集"
            return
        names = [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]
        if not names:
            self.why = "git index 为空，退回文件系统全集"
            return
        self.files = set(names)
        for name in names:
            parent = name
            while "/" in parent:
                parent = parent.rsplit("/", 1)[0]
                self.dirs.add(parent)

    @property
    def verified(self) -> bool:
        """是否真的按仓库 index 收窄过（False 表示降级为文件系统全集）。"""
        return self.files is not None

    def has_file(self, rel: str) -> bool:
        return True if self.files is None else rel in self.files

    def has_dir(self, rel: str) -> bool:
        """目录里有已跟踪文件才算存在；空目录/纯产物目录不算。"""
        return True if self.files is None else rel.strip("/") in self.dirs

    def allows(self, p: Path) -> bool:
        """p 是文件或目录时，分别按 file/dir 判定。"""
        rel = rel_path(self.root, p).replace("\\", "/")
        return self.has_dir(rel) if p.is_dir() else self.has_file(rel)


def norm_existing_path(repo_root: Path, value: str, proj_rel: str,
                       scope: "RepoScope | None" = None) -> str:
    """证据路径可能是仓库根相对或项目根相对；归一到仓库根相对，并校验存在。

    scope 存在时，「存在但未入库」视同不存在：返回原值，让校验阶段把
    「registry 指向仓库外文件」这件事暴露出来，而不是悄悄写进账本。
    """
    def ok(p: Path) -> bool:
        return p.exists() and (scope is None or scope.allows(p))

    if ok(repo_root / value):
        return value
    cand = repo_root / proj_rel / value
    if ok(cand):
        return rel_path(repo_root, cand)
    return value  # 保留原值，让缺失在校验阶段暴露


# ------------------------------ 证据分层 ------------------------------

def check_freshness(report: dict, repo_root: Path, proj_rel: str = "",
                    scope: "RepoScope | None" = None) -> tuple[bool, str]:
    """校验报告的源码绑定摘要是否仍对应当前文件。

    防止「测试跑过之后又改了源码，却继续挂着 verified」的过期证据假绿灯。
    内容摘要而非时间戳：跨时区、同分钟重跑都不会误判。

    scope 存在时额外要求被绑定文件已入库：一份报告若绑定了仓库里没有的测试，
    它在别人机器上永远无法复现——那不是证据，只是一句本地断言。
    """
    binding = report.get("evidence_binding") or {}
    inputs = binding.get("inputs") or []
    if binding.get("algorithm") != "sha256-files-v1" or not inputs:
        return True, "unbound"
    for item in inputs:
        rel = str(item.get("path", ""))
        want = str(item.get("sha256", ""))
        if not rel or not want:
            return False, "invalid-input"
        cands = [repo_root / rel]
        if proj_rel:
            cands.append(repo_root / proj_rel / rel)
        hit = next((p for p in cands if p.is_file()), None)
        if hit is None:
            same_name = [p for p in repo_root.rglob(Path(rel).name)
                         if p.is_file() and (scope is None or scope.allows(p))]
            if len(same_name) == 1:
                hit = same_name[0]
        if hit is None:
            return False, "missing:" + Path(rel).name
        if scope is not None and not scope.allows(hit):
            return False, "untracked:" + Path(rel).name
        if hashlib.sha256(hit.read_bytes()).hexdigest() != want:
            return False, "changed:" + Path(rel).name
    return True, "fresh"


def load_test_report(path: str | None, repo_root: Path) -> dict | None:
    """加载测试报告；路径相对仓库根。报告无效/整体失败时返回 None（不升级任何证据）。"""
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = repo_root / p
    if not p.is_file():
        return None
    try:
        report = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if report.get("schema") != "ledger-test-report/1":
        return None
    if report.get("overall") != "pass":
        return None
    if not isinstance(report.get("cases"), list):
        return None
    return report


def judge_tier(unit_tests: list[str], report: dict | None) -> tuple[str, dict]:
    """判定能力点的证据分层，返回 (tier, 明细)。

    没有报告、或该能力的任一单测文件都没有 pass 记录 → declared。
    只要有一个单测文件在报告里 status=pass 即 verified（保守但可解释）。
    """
    if report is None or not unit_tests:
        return "declared", {"basis": "no_report" if report is None else "no_unit_test"}

    passed_files = {
        Path(c.get("file", "")).name
        for c in report["cases"]
        if c.get("status") == "pass" and c.get("file")
    }
    matched = [Path(u).name for u in unit_tests if Path(u).name in passed_files]
    if matched:
        return "verified", {
            "basis": "test_report_pass",
            "matched_tests": sorted(matched),
            "report_at": report.get("generated_at", ""),
            "report_label": report.get("label", ""),
        }
    return "declared", {"basis": "no_matching_pass", "passed_files": sorted(passed_files)[:10]}


# ------------------------------ 证据扫描 ------------------------------

def glob_files(root: Path, patterns: list[str],
               scope: "RepoScope | None" = None) -> list[Path]:
    """按 glob 收集源码文件；scope 存在时只保留已入库路径。"""
    found: set[Path] = set()
    for pat in patterns:
        p = root / pat
        if p.is_file():
            found.add(p)
        if p.is_dir():
            found.update(x for x in p.glob("*") if x.is_file() and x.suffix in CODE_EXT)
        found.update(x for x in root.glob(pat) if x.is_file())
    if scope is not None:
        found = {x for x in found if scope.allows(x)}
    return sorted(found)


def resolve_declared(
    repo_root: Path, values: list, scope: "RepoScope | None", proj_rel: str = "",
) -> tuple[list[str], list[str]]:
    """把 registry 声明的路径解析为「存在且已入库」的仓库相对路径。

    返回 (命中, 缺失)。缺失项不静默丢弃——调用方必须打印告警，因为一条
    声明失效意味着该能力的证据链断了，等级应当如实回落。
    """
    hit: list[str] = []
    missing: list[str] = []
    for raw in values or []:
        s = str(raw).strip()
        if not s:
            continue
        cands = [repo_root / s]
        if proj_rel:
            cands.append(repo_root / proj_rel / s)
        p = next((c for c in cands if c.is_file()), None)
        if p is None or (scope is not None and not scope.allows(p)):
            missing.append(s)
            continue
        r = rel_path(repo_root, p)
        if r not in hit:
            hit.append(r)
    return hit, missing


def _project_trees(repo_root: Path, impl_globs: list[str] | None) -> list[Path]:
    """从 impl 声明前缀推导项目子树（``projects/<x>`` 或 ``examples/<x>``）。

    v2.1.0：项目根写 "." 时（多项目共仓），测试扫描必须限制在能力自己
    所属的项目里；否则 A 项目的关键词会匹配到 B 项目的同名测试。
    """
    trees: list[Path] = []
    for g in impl_globs or []:
        parts = Path(str(g)).parts
        if len(parts) >= 3 and parts[0] in {"projects", "examples"}:
            t = repo_root / parts[0] / parts[1]
            if t.is_dir() and t not in trees:
                trees.append(t)
    return trees


def _monorepo_dirs(repo_root: Path, configured: str,
                   scope: "RepoScope | None" = None,
                   impl_globs: list[str] | None = None) -> list[Path]:
    """把配置的单一目录展开为实际存在的扫描根。

    顺序：仓库根 → 项目子树（由 impl 声明推导）→ 旧的 monorepo 兜底。
    兜底仍保留，但只在无法从声明推导项目时使用；调用方会打印告警，
    避免「跨项目证据」在无声中发生。
    """
    primary = repo_root / configured
    if primary.is_dir() and (scope is None or scope.allows(primary)):
        return [primary]
    found: list[Path] = []
    for tree in _project_trees(repo_root, impl_globs):
        candidate = tree / configured
        if candidate.is_dir() and candidate not in found:
            if scope is not None and not scope.allows(candidate):
                continue
            found.append(candidate)
    if found:
        return found
    for container in ("projects", "examples"):
        base = repo_root / container
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir():
                candidate = child / configured
                if candidate.exists() and candidate not in found:
                    if scope is not None and not scope.allows(candidate):
                        continue
                    found.append(candidate)
    return found


def diff_projects(old_projects: list, new_projects: list) -> list[str]:
    """比较「已写账本」与「重新派生」的能力字段，返回差异描述。

    v2.1.0 的 --check 用它回答一个问题：账本还是不是 registry+仓库的函数？
    如果是，重算必须完全一致；如果不然，说明有人手改过账本，或者声明/证据
    在账本写完之后变了——两种都必须当场暴露。
    """
    def index(projects: list) -> dict[str, tuple]:
        out: dict[str, tuple] = {}
        for p in projects or []:
            for m in p.get("modules") or []:
                out["|module|" + str(m.get("code"))] = (
                    json.dumps(m.get("component_tree"), sort_keys=True, ensure_ascii=False),
                    json.dumps(m.get("doc_index"), sort_keys=True, ensure_ascii=False),
                )
                for c in m.get("caps") or []:
                    ev = c.get("evidence") or {}
                    out[str(c.get("code"))] = (
                        c.get("level"),
                        c.get("evidence_tier"),
                        tuple(ev.get("impl") or []),
                        tuple(ev.get("unit_test") or []),
                        tuple(ev.get("test_record") or []),
                    )
        return out

    a, b = index(old_projects), index(new_projects)
    drift: list[str] = []
    for code in sorted(set(a) - set(b)):
        drift.append(f"{code}: 账本有、重算无（声明已删除？）")
    for code in sorted(set(b) - set(a)):
        drift.append(f"{code}: 重算有、账本无（未提交生成结果）")
    for code in sorted(set(a) & set(b)):
        if a[code] != b[code]:
            drift.append(f"{code}: 账本 {a[code]} ≠ 重算 {b[code]}")
    return drift


def no_regress(old_ledger: dict, new_model: dict) -> list[str]:
    """重算不得降级任何能力的 level（v1.8.0 不降级硬门禁）。

    返回降级描述列表；非空即拒绝写盘。只比较 code→level_code，
    不改任何事实，纯判定。
    """
    old = {}
    for p in (old_ledger.get("capability_model") or {}).get("projects") or []:
        for m in p.get("modules") or []:
            for c in m.get("caps") or []:
                if c.get("code"):
                    old[c["code"]] = LEVELS_CODE(c.get("level"))
    errors = []
    for p in new_model.get("projects") or []:
        for m in p.get("modules") or []:
            for c in m.get("caps") or []:
                code = c.get("code")
                if code in old and LEVELS_CODE(c.get("level")) < old[code]:
                    errors.append(f"{code}: L{old[code]} → L{LEVELS_CODE(c.get('level'))}")
    return errors


def LEVELS_CODE(level) -> int:
    """level 可能是 int 或 'L5' 字符串，统一成整数。"""
    if isinstance(level, int):
        return level
    m = re.match(r"L(\d+)", str(level))
    return int(m.group(1)) if m else 0


def code_namespace(project_code: str, module_code: str) -> str:
    """v2.0.0 registry/2：返回 4 段编码的前两段命名空间。

    第一性原理：能力编码规范是 ``{项目}.{模块}.{域}.{序号}`` 恰好 4 段
    （见 verify_ledger.CODE_RE）。registry 有两种合法写法：
      - 单项目模板：``project.code=DEMO`` + ``module.code=DATA``（模块码不含项目段）
        → 命名空间 ``DEMO.DATA``；
      - 多项目 monorepo：``project.code=<ROOT>`` + ``module.code=<PROJ>.DATA``
        （模块码已含项目段）→ 命名空间直接用 ``<PROJ>.DATA``。

    判据：module_code 含 ``.`` 且首段为大写项目码时，视为已含项目段，直接用；
    否则补 ``project_code`` 前缀。绝不产生 5 段码或 ``<ROOT>.<ROOT>`` 前缀泄漏。
    """
    return _codec_code_namespace(project_code, module_code)


def judge_level(
    repo_root: Path, proj_root: Path, proj_rel: str, cfg: dict,
    impl_globs: list[str], hints: list[str],
    scope: "RepoScope | None" = None,
    declared_tests: list[str] | None = None,
    declared_records: list[str] | None = None,
) -> tuple[int, dict]:
    """按证据判定 L0-L5，返回 (level, 证据明细)。逐级判定，缺证据即停。

    v2.1.0：``declared_tests`` / ``declared_records`` 非 None 时即权威名单
    （已在调用方校验过「存在且已入库」），不再做关键词扫描。这一条把证据
    来源从「账本自证」改成「registry 声明」，是账本可复算的前提。
    """
    cfg = cfg.get("project", cfg)  # 兼容传整个配置或仅 project 段
    ev: dict = {"impl": [], "contract": [], "unit_test": [], "test_record": [], "governance": []}

    impl_files = glob_files(proj_root, impl_globs, scope)
    ev["impl"] = [rel_path(repo_root, x) for x in impl_files[:6]]

    # L1 契约：impl 命中契约目录，或 impl_globs 直接指向契约文件
    contract_dir = cfg.get("contracts_dir", "src/contracts")
    contracts = [x for x in impl_files if contract_dir.strip("/") in str(x)]
    ev["contract"] = [rel_path(repo_root, x) for x in contracts[:4]]
    for g in impl_globs:
        if contract_dir.strip("/") in g and (proj_root / g).exists():
            if scope is not None and not scope.allows(proj_root / g):
                continue
            v = norm_existing_path(repo_root, g, proj_rel, scope)
            if v not in ev["contract"]:
                ev["contract"].append(v)

    # L3 单测：声明优先；未声明才按 hint 匹配（限制在项目自身测试树内）
    if declared_tests is not None:
        ev["unit_test"] = list(declared_tests)
    else:
        test_roots = _monorepo_dirs(
            repo_root, cfg.get("unit_test_dir", "tests/unit"), scope, impl_globs)
        ut_hits: list[Path] = []
        for test_root in test_roots:
            ut_hits.extend(f for f in test_root.rglob("*")
                           if f.is_file() and f.suffix in CODE_EXT
                           and any(h.lower() in f.stem.lower() for h in hints)
                           and (scope is None or scope.allows(f)))
        ev["unit_test"] = [rel_path(repo_root, x) for x in ut_hits[:4]]

    # L4 测试记录：同样声明优先
    if declared_records is not None:
        ev["test_record"] = list(declared_records)
    else:
        tr_roots = _monorepo_dirs(
            repo_root, cfg.get("test_record_dir", "docs/test_records"), scope, impl_globs)
        tr_hits: list[Path] = []
        for tr in tr_roots:
            tr_hits.extend(f for f in tr.glob("*.md")
                           if f.is_file()
                           and any(h.lower() in f.stem.lower() for h in hints)
                           and (scope is None or scope.allows(f)))
        ev["test_record"] = [rel_path(repo_root, x) for x in tr_hits[:4]]

    # L5 治理门禁
    gov_dir = cfg.get("governance_dir", "governance")
    gov_hit = (proj_root / gov_dir).exists() and bool(cfg.get("governance_gate", False))

    level = 0
    if ev["contract"]:
        level = 1
    if ev["impl"]:
        level = max(level, 2)
    if ev["unit_test"]:
        level = max(level, 3)
    if ev["test_record"]:
        level = max(level, 4)
    if level >= 4 and gov_hit:
        ev["governance"] = [
            f"{proj_rel}/{gov_dir}/DECISION_LEDGER.json",
            f"{proj_rel}/{gov_dir}/index.html",
        ]
        level = 5
    return level, ev


# ------------------------------ 嵌套组件树 ------------------------------

def build_component_tree(
    repo_root: Path, root: Path, src_globs: list[str],
    cfg: dict, max_depth: int = 3, max_entries: int = 12,
    scope: "RepoScope | None" = None,
) -> list[dict]:
    """从真实目录生成嵌套组件树：目录 → 子目录 → 文件。

    每层最多 max_entries 项，深度最多 max_depth；关键模块名优先展示。
    这是一份「活」的结构——源码变了，重跑即更新，无需手工维护架构图。

    scope 存在时只收已入库路径：``data/``、``logs/``、``*.egg-info`` 这类被
    .gitignore 的产物目录不会出现在架构树里（它们不是仓库的结构）。
    """
    seen: set[Path] = set()
    nodes: list[dict] = []

    def keep(p: Path) -> bool:
        return scope is None or scope.allows(p)

    def make_node(p: Path, depth: int) -> dict | None:
        rel = rel_path(repo_root, p)
        if p.is_dir():
            subs = sorted(
                (x for x in p.iterdir()
                 if x.is_dir() and not x.name.startswith((".", "__"))
                 and x.name not in {"node_modules", ".git", "__pycache__", "venv", ".venv"}
                 and keep(x)),
                key=lambda x: x.name,
            )
            files = sorted(
                (x for x in p.iterdir()
                 if x.is_file() and x.suffix in CODE_EXT and keep(x)),
                key=lambda x: x.name,
            )
            key = [f for f in files if KEY_RE.search(f.stem)]
            other = [f for f in files if f not in key]
            children: list[dict] = []
            for s in subs:
                if depth < max_depth:
                    child = make_node(s, depth + 1)
                    if child:
                        children.append(child)
            for f in (key + other)[:max_entries]:
                children.append({
                    "name": f.name,
                    "path": str(Path(rel) / f.name),
                    "type": "file",
                })
            if not children:
                children.append({"name": "（空目录）", "type": "note", "path": ""})
            return {
                "name": p.name, "path": rel, "type": "dir",
                "count": len(children), "children": children,
            }
        return {"name": p.name, "path": rel, "type": "file"}

    for g in src_globs:
        p = root / g
        targets = [p] if p.is_dir() else list(root.glob(g))[:3]
        for t in targets:
            if t in seen or not keep(t):
                continue
            seen.add(t)
            node = make_node(t, 0)
            if node:
                nodes.append(node)
    return nodes


# ------------------------------ 文档索引 ------------------------------

def doc_hits(repo_root: Path, proj_root: Path, proj_rel: str,
             hints: list[str], domain: str, cfg: dict,
             scope: "RepoScope | None" = None) -> list[dict]:
    """按能力域/关键字匹配项目文档，区分规划类与说明类。"""
    docs = proj_root / cfg.get("docs_dir", "docs")
    if not docs.exists():
        return []
    keys = [domain.lower()] + [h.lower() for h in hints if len(h) > 2]
    out: list[dict] = []
    for f in docs.rglob("*"):
        if not f.is_file() or f.suffix not in CODE_EXT:
            continue
        if scope is not None and not scope.allows(f):
            continue
        stem = f.stem.lower()
        if any(k in stem for k in keys):
            out.append({
                "path": rel_path(repo_root, f),
                "title": f.stem,
                "kind": "plan" if PLAN_RE.search(stem) else "doc",
            })
    uniq = {x["path"]: x for x in out}
    return sorted(uniq.values(), key=lambda x: (x["kind"] != "plan", x["path"]))[:8]


def related_decisions(entries: list[dict], project_code: str,
                      domain: str, name: str, module_decisions: list[str]) -> list[dict]:
    """双向引用：能力点 → 关联决策（含状态）；模块级决策自动继承。"""
    ids = set(module_decisions or [])
    for e in entries:
        if e.get("scope") not in (project_code, "ALL"):
            continue
        blob = " ".join([
            e.get("title", ""), e.get("decision", ""), e.get("rationale", ""),
            " ".join(e.get("evidence", [])),
        ]).lower()
        if domain.lower() in blob or name.lower() in blob:
            ids.add(e["id"])
    idx = {e["id"]: e for e in entries}
    return [
        {"id": i, "title": idx[i].get("title", i), "status": idx[i].get("status", "")}
        for i in sorted(ids) if i in idx
    ][:8]


def build_doc_index(
    repo_root: Path, proj_root: Path, proj_rel: str, cfg: dict,
    domain: str, name: str, hints: list[str], ev: dict,
    module_map_mod: dict | None, entries: list[dict], project_code: str,
    scope: "RepoScope | None" = None,
) -> dict:
    """能力点 → 文档索引：规划/相关/模块文档/契约/实现/单测/测试记录/决策/控制入口。"""
    cfg = cfg.get("project", cfg)
    def paths(key: str, kind: str) -> list[dict]:
        return [
            {"path": norm_existing_path(repo_root, p, proj_rel, scope),
             "title": Path(p).name, "kind": kind}
            for p in ev.get(key, [])
        ]

    module_docs = [
        {"path": norm_existing_path(repo_root, d, proj_rel, scope),
         "title": Path(d).name, "kind": "module_doc"}
        for d in (module_map_mod or {}).get("docs", [])
    ]
    decisions = related_decisions(
        entries, project_code, domain, name,
        (module_map_mod or {}).get("decisions", []),
    )
    all_docs = doc_hits(repo_root, proj_root, proj_rel, hints, domain, cfg, scope)
    plans = [d for d in all_docs if d["kind"] == "plan"]
    # 模块级规划文档天然覆盖其下所有能力点
    for d in module_docs:
        if PLAN_RE.search(d["title"]) and d["path"] not in {x["path"] for x in plans}:
            plans.append({**d, "kind": "plan"})
    related = [
        d for d in all_docs
        if d["kind"] != "plan" and d["path"] not in {x["path"] for x in plans}
    ]
    return {
        "plans": plans,
        "related_docs": related,
        "module_docs": module_docs,
        "contracts": paths("contract", "contract"),
        "impl": paths("impl", "impl"),
        "unit_tests": paths("unit_test", "unit_test"),
        "test_records": paths("test_record", "test_record"),
        "decisions": decisions,
        "control_center": {
            "page": (module_map_mod or {}).get("page", ""),
            "sections": (module_map_mod or {}).get("sections", []),
        },
    }


# ------------------------------ 模型构建 ------------------------------

def build(repo_root: Path, cfg_all: dict, ledger: dict, test_report: dict | None = None,
          scope: "RepoScope | None" = None) -> dict:
    """构建 capability_model 与 architecture.component_tree。

    scope 为 None 时按文件系统全集工作（仅供测试/非 git 场景）；正常入口
    main() 会传入按 git index 收窄的 RepoScope，保证账本只描述仓库内路径。
    """
    projects_cfg = normalize_projects(cfg_all)
    if not projects_cfg:
        raise SystemExit("registry 未提供 project 或 projects[]，无法生成能力模型")
    first_cfg = projects_cfg[0]
    code = first_cfg["code"]

    model = {
        "version": "1.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M HKT"),
        "generator": "templates/build_capability_model.py",
        "purpose": "统一能力编码 + 可复算完成度 + 嵌套组件树 + 文档索引，供规划与编码代理消费。",
        "coding_spec": {
            "format": "{项目}.{模块}.{能力域}.{序号}",
            "example": f"{code}.DATA.READY.01",
            "segments": {
                "项目": "项目代码，来自 registry.json 的 project.code 或 projects[].code",
                "模块": "项目内一级能力域代码（DATA/CORE/...）",
                "能力域": "能力点域代码（READY/CORE/...）",
                "序号": "两位序号，01 起；废弃标 retired 不复用",
            },
            "stability": "编码一经分配不随名称变化；废弃标记 retired 而非复用序号。",
            "graph_edges": [
                "belongs_to（模块→项目）", "implements（能力→模块）",
                "supersedes（决策取代链）", "depends_on（规划依赖）",
            ],
        },
        "levels": LEVELS,
        "scoring": {
            "method": "逐级证据判定，取最高达成级；完成度 = level/5",
            "recompute": "重跑本生成器；证据消失则等级自动回落，不依赖人工填报。",
            "caveat": LEVELS_CAVEAT,
        },
        "evidence_tier_spec": EVIDENCE_TIER_SPEC,
        "doc_index_spec": {
            "purpose": "让每个能力点/规划都能索引到对应文档，且索引可见、可点开。",
            "path_base": "仓库根相对路径；看板点击时拼接 ../../ + path",
            "component_tree": "模块内真实嵌套组件：dir → child dirs → files",
            "capability_fields": {
                "plans": "规划/方案/指南类文档",
                "related_docs": "其他相关文档",
                "module_docs": "模块级文档",
                "contracts": "契约文件", "impl": "实现文件",
                "unit_tests": "单测", "test_records": "测试记录",
                "decisions": "关联决策条目（含状态）",
                "control_center": "对应页面与 section",
            },
        },
        "projects": [],
    }

    entries = ledger.get("entries", [])
    mm_by_name = {m.get("name"): m for m in ledger.get("module_map", {}).get("modules", [])}
    arch_projects = ledger.get("architecture", {}).get("projects", [])

    total_caps = 0
    total_modules = 0
    completion_sum = 0.0
    level_dist: dict[str, int] = {}
    tier_dist: dict[str, int] = {}

    # v2.0.1：同一生成器同时消费旧单项目形状与新 projects[] 形状。
    for project_cfg in projects_cfg:
        code = project_cfg["code"]
        proj_rel = project_cfg["root"]
        proj_root = repo_root / proj_rel
        arch_mod_by_id = {}
        for ap in arch_projects:
            if ap.get("id") == code:
                arch_mod_by_id = {m.get("id"): m for m in ap.get("modules", [])}

        pnode = {
            "code": code, "name": project_cfg.get("name", code),
            "root": proj_rel, "modules": [],
        }

        for midx, mod in enumerate(project_cfg["modules"], 1):
            mcode = str(mod.get("code", "CORE") or "CORE").strip().upper()
            # v2.0.0 registry/2：module/code 编码统一走唯一 codec，杜绝 5 段码。
            cap_ns = code_namespace(code, mcode)
            mnode = {
                "code": cap_ns, "name": mod["name"],
                "index": midx, "caps": [],
            }
            mm_mod = mm_by_name.get(mod["name"])
            arch_mod = arch_mod_by_id.get(f"M-{mcode}")
            src_globs = mod.get("src") or (arch_mod or {}).get("src") or [
                s for c in mod["caps"] for s in c.get("impl", []) if s.endswith("/")
            ]
            mnode["component_tree"] = build_component_tree(
                repo_root, proj_root, src_globs, project_cfg, scope=scope)
            mnode["doc_index"] = {
                "docs": [
                    {"path": norm_existing_path(repo_root, d, proj_rel, scope),
                     "title": Path(d).name, "kind": "module_doc"}
                    for d in (mm_mod or {}).get("docs", [])
                ],
                "page": (mm_mod or {}).get("page") or (arch_mod or {}).get("page", ""),
                "sections": (mm_mod or {}).get("sections") or (arch_mod or {}).get("sections", []),
            }

            for cidx, cap in enumerate(mod.get("caps") or [], 1):
                cap_name = cap["name"]
                domain = str(cap["domain"]).strip().upper()
                impl_globs = cap.get("impl", [])
                cap_code_src = cap.get("code", "")
                # v2.1.0：证据只来自 registry 声明，绝不回读账本。
                # 回读会让账本变成自身的函数——抹掉证据就再也算不回来。
                hints = [str(h) for h in (cap.get("hints") or [])]
                declared_tests = declared_records = None
                if isinstance(cap.get("tests"), list):
                    declared_tests, miss_t = resolve_declared(
                        repo_root, cap["tests"], scope, proj_rel)
                    if miss_t:
                        print(f"[WARN] {cap_code_src}: 声明的测试不存在或未入库 "
                              f"{miss_t}（该能力证据按缺失处理）")
                if isinstance(cap.get("test_records"), list):
                    declared_records, miss_r = resolve_declared(
                        repo_root, cap["test_records"], scope, proj_rel)
                    if miss_r:
                        print(f"[WARN] {cap_code_src}: 声明的测试记录不存在或未入库 "
                              f"{miss_r}（该能力证据按缺失处理）")
                if declared_tests is None and not hints:
                    print(f"[WARN] {cap_code_src}: 既未声明 tests 也无 hints，"
                          "单测证据无法派生（等级不会超过 L2）")
                level, ev = judge_level(
                    repo_root, proj_root, proj_rel, project_cfg, impl_globs, hints,
                    scope=scope, declared_tests=declared_tests,
                    declared_records=declared_records)
                tier, tier_detail = judge_tier(ev.get("unit_test", []), test_report)
                # v2.0.1 stable_code：显式 code 合法时优先，迁移前后身份不变。
                cap_code = codec_cap_code(code, mcode, domain, cidx, cap_code_src)
                cnode = {
                    "code": cap_code,
                    "name": cap_name,
                    "domain": domain,
                    "level": level,
                    "level_code": LEVELS[level]["code"],
                    "completion": round(level / 5, 2),
                    "evidence": ev,
                    "evidence_tier": tier,
                    "tier_detail": tier_detail,
                    "next_level": min(level + 1, 5),
                    "next_action": (
                        LEVELS[min(level + 1, 5)]["rule"]
                        if level < 5 else "保持生产闭环，持续监控"
                    ),
                    "status": (
                        "operational" if level == 5
                        else "active" if level >= 2
                        else "planned" if level <= 1 else "in_progress"
                    ),
                    "doc_index": build_doc_index(
                        repo_root, proj_root, proj_rel, project_cfg, domain, cap_name,
                        hints, ev, mm_mod, entries, code, scope,
                    ),
                }
                mnode["caps"].append(cnode)
                total_caps += 1
                lc = LEVELS[level]["code"]
                level_dist[lc] = level_dist.get(lc, 0) + 1
                tier_dist[tier] = tier_dist.get(tier, 0) + 1

            mnode["completion"] = round(
                sum(c["completion"] for c in mnode["caps"]) / len(mnode["caps"]), 2
            ) if mnode["caps"] else 0.0
            pnode["modules"].append(mnode)

        pnode["completion"] = round(
            sum(m["completion"] for m in pnode["modules"]) / len(pnode["modules"]), 2
        ) if pnode["modules"] else 0.0
        model["projects"].append(pnode)
        total_modules += len(pnode["modules"])
        completion_sum += pnode["completion"]

    model["loop_protocol"] = {
        "purpose": "驱动 规划→实现→验证→决策 的自动循环。",
        "steps": [
            {"n": 1, "id": "SCAN", "action": "重跑生成器，按证据重算每个能力的 level/completion"},
            {"n": 2, "id": "SELECT", "action": "筛选 next_level>level 且 completion 最低的能力点"},
            {"n": 3, "id": "PLAN", "action": "为目标能力新增 proposed 决策，编码引用能力 code"},
            {"n": 4, "id": "EXECUTE", "action": "按决策实现代码+契约+单测+测试记录，补齐 L1→L4 证据"},
            {"n": 5, "id": "VERIFY", "action": "重跑生成器；达标则 proposed→done，否则记录阻塞"},
            {"n": 6, "id": "VISUALIZE", "action": "看板自动反映新等级/完成度，无需手改图"},
        ],
        "invariants": [
            "编码稳定不复用；废弃标 retired 不删",
            "完成度只由证据判定，禁止手填",
            "每个能力点 next_action 对应一个具体的等级证据要求",
            "决策与能力双向引用：决策 evidence 含能力 code，能力可回溯决策",
        ],
    }
    model["summary"] = {
        "projects": len(projects_cfg),
        "modules": total_modules,
        "capabilities": total_caps,
        "level_distribution": level_dist,
        "overall_completion": round(completion_sum / len(projects_cfg), 2) if projects_cfg else 0.0,
        "evidence_tier_distribution": tier_dist,
        "verified_coverage": round(tier_dist.get("verified", 0) / total_caps, 2) if total_caps else 0.0,
    }
    # SELECT 步骤的机器可读产出：每次重跑自动刷新，供规划/编码代理直接消费
    model["next_queue"] = build_next_queue(model)
    return model


# ------------------------------ 历史层 ------------------------------

EVIDENCE_KEYS = ("impl", "contract", "unit_test", "test_record")
DOC_PATH_KEYS = ("plans", "related_docs", "module_docs",
                 "contracts", "impl", "unit_tests", "test_records")


def _path_list(values) -> list[str]:
    """证据/索引中的路径可能是字符串或 {path:...} 对象，统一取路径。"""
    out: list[str] = []
    for v in values or []:
        if isinstance(v, dict):
            v = v.get("path")
        if v:
            out.append(str(v))
    return out


def snapshot_state(model: dict) -> dict[str, dict]:
    """提取紧凑且稳定的派生状态：指纹与回放都基于它，而非可变元数据。"""
    snap: dict[str, dict] = {}
    for p in model.get("projects", []):
        for m in p.get("modules", []):
            for c in m.get("caps", []):
                ev, di = c.get("evidence", {}), c.get("doc_index", {})
                snap[c["code"]] = {
                    "l": c.get("level", 0),
                    "c": c.get("completion", 0),
                    "t": c.get("evidence_tier", "declared"),
                    "e": sorted({x for k in EVIDENCE_KEYS for x in _path_list(ev.get(k))}),
                    "d": sorted({x for k in DOC_PATH_KEYS for x in _path_list(di.get(k))}),
                    "dec": sorted({x.get("id") for x in di.get("decisions", [])
                                   if isinstance(x, dict) and x.get("id")}),
                }
    return snap


def fingerprint_state(snap: dict) -> str:
    """稳定指纹：与生成时间、注释、字段顺序无关，只反映派生状态。"""
    payload = json.dumps(snap, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def diff_state(before: dict, after: dict) -> dict:
    """对比两次状态快照，产出可机读的变更摘要。"""
    bkeys, akeys = set(before), set(after)
    transitions, deltas, ev_changes = [], [], []
    for code in sorted(bkeys & akeys):
        b, a = before[code], after[code]
        if b.get("l") != a.get("l"):
            transitions.append({"code": code, "from": f"L{b.get('l', 0)}", "to": f"L{a.get('l', 0)}"})
        if abs(float(b.get("c", 0)) - float(a.get("c", 0))) > 1e-9:
            deltas.append({"code": code, "from": b.get("c", 0), "to": a.get("c", 0)})
        be, ae = set(b.get("e", [])), set(a.get("e", []))
        if be != ae:
            ev_changes.append({"code": code, "added": sorted(ae - be), "removed": sorted(be - ae)})
    return {
        "level_transitions": transitions,
        "added": sorted(akeys - bkeys),
        "removed": sorted(bkeys - akeys),
        "completion_delta": deltas,
        "evidence_changes": ev_changes,
    }


def diff_has_changes(diff: dict) -> bool:
    return any(diff.get(k) for k in ("level_transitions", "added", "removed",
                                     "completion_delta", "evidence_changes"))


def build_lesson_candidates(ledger: dict, events: list[dict]) -> list[dict]:
    """从历史识别可沉淀信号——机器只标记候选，洞察与行动由人/AI 补。"""
    prior = list(ledger.get("lessons", {}).get("candidates", []))
    lessons_now = ledger.get("lessons", {})
    dismissed = [c for c in prior if c.get("status") == "dismissed"]
    # 只有「已驳回」或「已转成经验条目」的候选才不再提示；
    # open 候选按规则稳定重算（id 由信号确定），否则会交替消失/重现，破坏幂等。
    known = {c.get("id") for c in dismissed} | {
        x.get("from_candidate") for x in lessons_now.get("items", [])
        if x.get("from_candidate")
    }
    out: list[dict] = []

    def add(kind: str, ref: str, reason: str, source: list[int], scope: dict) -> None:
        cid = "LC-" + hashlib.sha1((kind + ":" + ref).encode("utf-8")).hexdigest()[:6].upper()
        if cid in known:  # 稳定 id 去重：已确认或已驳回的候选不重复出现
            return
        known.add(cid)
        out.append({"id": cid, "kind": kind, "reason": reason,
                    "source_events": source, "suggested_scope": scope,
                    "status": "open", "origin": "derive"})

    # 规则 1：能力降级——证据消失是最值得复盘的事件
    for ev in events:
        for t in (ev.get("changes") or {}).get("level_transitions", []):
            try:
                frm = int(str(t.get("from", "L0"))[1:])
                to = int(str(t.get("to", "L0"))[1:])
            except ValueError:
                continue
            if to < frm:
                add("downgrade", t.get("code", ""),
                    f"能力 {t.get('code')} 从 {t.get('from')} 回落到 {t.get('to')}；"
                    f"需查清是证据文件删除、路径变更还是判定规则变化，并记录防范措施。",
                    [ev.get("seq")], {"capabilities": [t.get("code")]})

    # 规则 2：长期停滞——最近若干事件完成度不变且未达 L5
    recent = [e for e in events if e.get("state_digest")][-3:]
    if len(recent) >= 2:
        first, last = recent[0], recent[-1]
        for code, s in (last.get("state_digest") or {}).items():
            b = (first.get("state_digest") or {}).get(code)
            if b and b.get("c") == s.get("c") and int(s.get("l", 5)) < 5:
                add("stagnation", code,
                    f"能力 {code} 连续 {len(recent)} 个事件停在 {float(s.get('c', 0)):.0%}"
                    f"（L{s.get('l')}），未补齐下一级证据；宜判断是优先级问题还是阻塞。",
                    [e.get("seq") for e in recent], {"capabilities": [code]})

    # 规则 3：决策被取代——原判断为何失效值得沉淀
    for e in ledger.get("entries", []):
        if e.get("supersedes"):
            add("superseded_decision", e.get("id", ""),
                f"决策 {e.get('id')} 取代了 {e.get('supersedes')}；"
                f"应沉淀原判断失效的原因，避免同类误判再次发生。",
                [], {"decisions": [e.get("id"), e.get("supersedes")]})

    # 已驳回的候选保留（避免反复提示），其余按规则稳定重算
    return dismissed + out


def evolve(ledger: dict, model: dict, ts: str) -> dict | None:
    """把历史层与经验层附加到 model 并写回 ledger。仅状态真变化时追加事件（幂等）。"""
    snap = snapshot_state(model)
    fp = fingerprint_state(snap)

    hist = ledger.setdefault("history", {"spec": HISTORY_SPEC, "events": []})
    hist["spec"] = HISTORY_SPEC
    events = hist.setdefault("events", [])
    new_event = None
    if not events:
        new_event = {
            "seq": 1, "ts": ts, "type": "genesis",
            "fingerprint_before": None, "fingerprint_after": fp,
            "changes": {"level_transitions": [], "added": sorted(snap), "removed": [],
                        "completion_delta": [], "evidence_changes": []},
            "state_digest": snap, "trigger": "derive",
            "note": "账本初始化：记录当前全部能力点快照作为演进基线。",
        }
        events.append(new_event)
    else:
        last = events[-1]
        if last.get("fingerprint_after") != fp:
            changes = diff_state(last.get("state_digest", {}), snap)
            new_event = {
                "seq": len(events) + 1, "ts": ts, "type": "change",
                "fingerprint_before": last.get("fingerprint_after"),
                "fingerprint_after": fp, "changes": changes,
                "state_digest": snap, "trigger": "derive",
                "note": "证据 / 等级 / 文档索引变化，由生成器自动侦测。",
            }
            events.append(new_event)

    lessons = ledger.setdefault("lessons", {"spec": LESSONS_SPEC, "items": [], "candidates": []})
    lessons["spec"] = LESSONS_SPEC
    lessons.setdefault("items", [])
    lessons["candidates"] = build_lesson_candidates(ledger, events)

    model["history"] = {
        "spec": HISTORY_SPEC, "event_count": len(events),
        "latest": events[-1] if events else None,
        "current_fingerprint": fp,
    }
    model["lessons"] = {
        "spec": LESSONS_SPEC,
        "items": lessons["items"],
        "candidates": lessons["candidates"],
    }
    return new_event


def lesson_matches(item: dict, task: dict, domain: str) -> bool:
    """已确认经验与任务卡的 scope 匹配：空 scope 视为全局经验。"""
    if item.get("status") != "confirmed":
        return False
    sc = item.get("scope") or {}
    caps, projs = sc.get("capabilities") or [], sc.get("projects") or []
    doms, lvls = sc.get("domains") or [], sc.get("levels") or []
    if not (caps or projs or doms or lvls):
        return True
    return (task["code"] in caps or task["project"] in projs
            or domain in doms or task["level"] in lvls)


def build_next_queue(model: dict, limit: int = 10, lessons: dict | None = None) -> list[dict]:
    """把循环协议的 SELECT 步骤机器化：输出可直接消费的任务队列。

    排序规则（可机读、可复算，免除每次重新解释）：
      1. 只收录未达 L5 的能力点；
      2. 按 completion 升序（最低完成度优先）；
      3. 同级按 code 排序，保证稳定可复现。
    每个任务携带：目标编码、当前/目标等级、具体动作、缺失的证据类型、
    关联文档与决策——AI 或人拿到一条即可开工，无需再查别处。
    """
    evidence_order = ("contracts", "impl", "unit_tests", "test_records")
    evidence_label = {
        "contracts": "契约(L1)", "impl": "实现(L2)",
        "unit_tests": "单测(L3)", "test_records": "测试记录(L4)",
    }
    tasks: list[dict] = []
    for p in model["projects"]:
        for m in p["modules"]:
            for c in m["caps"]:
                if c.get("level", 0) >= 5:
                    continue
                di = c.get("doc_index", {})
                missing = [
                    evidence_label[k] for k in evidence_order
                    if not di.get(k) and not c.get("evidence", {}).get(
                        {"contracts": "contract", "impl": "impl",
                         "unit_tests": "unit_test", "test_records": "test_record"}[k]
                    )
                ]
                parts = c["code"].split(".")
                domain = parts[2] if len(parts) >= 3 else ""
                task = {
                    "code": c["code"],
                    "name": c["name"],
                    "project": p["code"],
                    "module": m["code"],
                    "domain": domain,
                    "level": c["level_code"],
                    "completion": c["completion"],
                    "target_level": f"L{c['next_level']}",
                    "action": c["next_action"],
                    "evidence_tier": c.get("evidence_tier", "declared"),
                    "needs_runtime_verification": (
                        c.get("level", 0) >= 3
                        and c.get("evidence_tier", "declared") != "verified"
                    ),
                    "missing_evidence": missing,
                    "docs": {
                        k: [d["path"] for d in di.get(k, [])]
                        for k in ("plans", "module_docs", "contracts",
                                  "impl", "unit_tests", "test_records")
                    },
                    "decisions": [d["id"] for d in di.get("decisions", [])],
                }
                # 经验层接入：任务卡自带相关已确认经验，执行者无需另行检索
                items = (lessons or {}).get("items", []) or model.get("lessons", {}).get("items", [])
                task["lessons"] = [
                    {"id": x.get("id"), "title": x.get("title"),
                     "insight": x.get("insight"), "action": x.get("action")}
                    for x in items if lesson_matches(x, task, domain)
                ]
                tasks.append(task)
    tasks.sort(key=lambda t: (t["completion"], t["code"]))
    for i, t in enumerate(tasks, 1):
        t["rank"] = i
    return tasks[:limit]


def sync_architecture(ledger: dict, model: dict, repo_root: Path, proj_rel: str) -> None:
    """把嵌套组件树与文档索引写回 architecture，供架构钻取视图使用。

    v2.0.1：遍历 capability_model.projects；旧单项目形状仍只有一次循环。
    """
    projects = ledger.setdefault("architecture", {}).setdefault("projects", [])
    for pm in model.get("projects", []):
        ap = next((p for p in projects if p.get("id") == pm["code"]), None)
        if ap is None:
            ap = {
                "id": pm["code"],
                "name": pm["name"],
                "path": pm.get("root", proj_rel),
                "modules": [],
                "data_flow": [],
                "controls": [],
            }
            projects.append(ap)
        cm_by_code = {m["code"]: m for m in pm["modules"]}
        for am in ap["modules"]:
            bare = am["id"].replace("M-", "")
            cm = cm_by_code.get(bare) or cm_by_code.get(f"{pm['code']}.{bare}")
            if cm:
                am["component_tree"] = cm["component_tree"]
                am["doc_index"] = cm["doc_index"]
                am["capability_codes"] = [c["code"] for c in cm["caps"]]


# ------------------------------ 主流程 ------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="项目根目录（默认当前目录）")
    ap.add_argument("--registry", help="registry.json 路径（默认 <root>/governance/registry.json）")
    ap.add_argument("--ledger", help="账本路径（默认 <root>/governance/DECISION_LEDGER.json）")
    ap.add_argument("--board", help="看板 HTML 路径（默认 <root>/governance/index.html）")
    ap.add_argument("--no-board", action="store_true", help="不同步看板内嵌数据")
    ap.add_argument("--test-report", help="测试报告 JSON（由 scripts/run_tests.py 生成）；提供则判定 verified 级证据")
    ap.add_argument("--dry-run", action="store_true", help="只打印摘要，不写文件")
    ap.add_argument("--expect-fingerprint", help="读取账本时的 current_fingerprint；不符则拒绝写入（CAS）")
    ap.add_argument("--allow-regress", action="store_true",
                    help="人批准的数据迁移专用：允许能力 level 下降（默认拒绝，v1.8.0 门禁）")
    ap.add_argument("--strict-evidence", action="store_true",
                    help="拒绝未绑定源码摘要的测试报告（CI / 发布门禁建议开启）")
    ap.add_argument("--check", action="store_true",
                    help="漂移门禁：重算结果与已写账本不一致即 exit 1（不写盘）")
    args = ap.parse_args()

    repo_root = Path(args.root).resolve()
    reg_path = Path(args.registry) if args.registry else repo_root / "governance" / "registry.json"
    ledger_path = Path(args.ledger) if args.ledger else repo_root / "governance" / "DECISION_LEDGER.json"
    board_path = Path(args.board) if args.board else repo_root / "governance" / "index.html"

    cfg_all = json.loads(Path(reg_path).read_text())
    projects_cfg = normalize_projects(cfg_all)
    if not projects_cfg:
        raise SystemExit("registry 未提供 project 或 projects[]，无法生成能力模型")
    first_cfg = projects_cfg[0]
    ledger = json.loads(Path(ledger_path).read_text()) if Path(ledger_path).exists() else {
        "ledger_version": "1.0",
        "title": f"{first_cfg.get('name', first_cfg['code'])} 决策与能力账本",
        "purpose": "单一事实源：决策、裁决、待办及能力索引的唯一写入点。",
        "last_updated": "",
        "owner": "待定",
        "workflow": [
            "所有重大决策/裁决/待办只写入本文件 entries，不再新建独立报告。",
            "新增条目分配稳定 id，状态初始 proposed/decided，填齐字段。",
            "旧决策被取代时设 superseded/supersedes，用取代链表达演进。",
            "能力等级与完成度由 build_capability_model.py 从证据重算，禁止手填。",
        ],
        "fields": {
            "id": "稳定标识，永不复用",
            "status": "proposed | decided | done | superseded | deferred",
            "evidence": "证据/文档路径，可追溯到原始取证",
            "confidence": "high | medium | low",
        },
        "entries": [],
        "module_map": {"modules": []},
        "architecture": {"projects": []},
    }

    # 场景预检：版本契约 + 并发 CAS（fail-closed，任何一项不过都不写盘）
    lv = str(ledger.get("ledger_version", "1.0"))
    if lv not in SUPPORTED_LEDGER_VERSIONS:
        print(f"[BLOCK] 账本版本 {lv} 不受本生成器支持（支持 {sorted(SUPPORTED_LEDGER_VERSIONS)}）；"
              "请先导出快照并人工确认迁移，不要跨版本直写。", file=sys.stderr)
        sys.exit(2)
    if args.expect_fingerprint:
        cur_fp = (ledger.get("capability_model", {}).get("history", {})
                  .get("current_fingerprint"))
        if cur_fp != args.expect_fingerprint:
            print(f"[BLOCK] 并发写入：读取时指纹 {args.expect_fingerprint}，当前 {cur_fp}。"
                  "期间有人改过账本，请重新读取并合并变更后再试。", file=sys.stderr)
            sys.exit(2)

    # v2.1.0：路径全集取自 git index。仓库里没有的文件一律不进账本，
    # 这样「本机绿、干净检出红」的差异在生成阶段就不存在了。
    scope = RepoScope(repo_root)
    if scope.verified:
        print(f"[SCOPE] 路径全集取自 git index：{len(scope.files)} 个已跟踪文件")
    else:
        print(f"[WARN] {scope.why}：账本可能引用仓库外路径，"
              "干净检出会暴露差异（建议在 git 仓库内重跑）")

    test_report = load_test_report(args.test_report, repo_root)
    if args.test_report and test_report is None:
        print(f"[WARN] 测试报告不可用或整体未通过（{args.test_report}）；所有证据保持 declared")
    bound, fresh = False, True
    if test_report is not None:
        binding = test_report.get("evidence_binding") or {}
        bound = bool(binding.get("inputs"))
        if bound:
            for pcfg in projects_cfg:
                fresh, detail = check_freshness(test_report, repo_root, pcfg["root"], scope)
                if not fresh:
                    break
            if not fresh:
                print(f"[WARN] 报告源码摘要不可复现（{detail}）：报告生成后源码/测试已变化，"
                      "或报告引用了未入库的文件；本次不予采信，verified 全部回落 declared")
                test_report = None
        elif args.strict_evidence:
            print("[WARN] 报告未绑定源码摘要，--strict-evidence 下不予采信")
            test_report = None
        else:
            print("[WARN] 报告未绑定源码摘要；建议用 v0.8.0+ 的 run_tests.py 重跑")
    model = build(repo_root, cfg_all, ledger, test_report=test_report, scope=scope)
    if args.check:
        drift = diff_projects(
            (ledger.get("capability_model") or {}).get("projects") or [],
            model.get("projects") or [],
        )
        if drift:
            print("[DRIFT] 账本与「registry + 仓库」重算结果不一致：", file=sys.stderr)
            for line in drift[:20]:
                print("  - " + line, file=sys.stderr)
            print(f"[DRIFT] 共 {len(drift)} 处；重跑生成器并提交账本是唯一修法。",
                  file=sys.stderr)
            sys.exit(1)
        print("[OK] 账本 = f(registry, 仓库, 报告)：可复算")
        return
    model["summary"]["evidence_bound"] = bool(bound and fresh and test_report is not None)
    model["summary"]["evidence_freshness"] = (
        "fresh" if bound and fresh else "stale" if bound else "unbound")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M HKT")
    # 历史/经验只依赖派生状态与既有事件；dry-run 也计算，以便预览将产生的事件（不落盘）
    new_event = evolve(ledger, model, ts)
    # evolve 之后重算队列，让任务卡携带最新已确认经验（build 内那次是未接入经验的快照）
    model["next_queue"] = build_next_queue(model, lessons=ledger.get("lessons"))
    sync_architecture(ledger, model, repo_root, first_cfg["root"])

    print(json.dumps(model["summary"], ensure_ascii=False, indent=2))
    if args.dry_run:
        for pnode in model["projects"]:
            print(f"[{pnode['code']}] {pnode['name']}")
            for m in pnode["modules"]:
                caps = " ".join(c["level_code"] for c in m["caps"])
                print(f"  {m['code']:<24} {m['completion']:.2f}  {caps}")
        print(f"\n证据分层：{model['summary']['evidence_tier_distribution']} "
              f"· verified 覆盖 {model['summary']['verified_coverage']:.0%}")
        print(f"历史：{model['history']['event_count']} 事件 · 指纹 {model['history']['current_fingerprint']}"
              + (f" · 将追加 #{new_event['seq']} {new_event['type']}" if new_event else " · 无变化（幂等）"))
        ls = ledger.get("lessons", {})
        print(f"经验：{len(ls.get('items', []))} 条已确认 · {len(ls.get('candidates', []))} 个候选")
        print("\n下一轮任务队列（SELECT 产出，按完成度升序）：")
        for t in model["next_queue"]:
            gap = "/".join(t["missing_evidence"]) or "无显式缺口"
            lesson = f" · 经验 {','.join(x['id'] for x in t['lessons'])}" if t["lessons"] else ""
            print(f"  #{t['rank']} {t['code']:<24} {t['level']}→{t['target_level']} "
                  f"缺[{gap}] · {t['action']}{lesson}")
        return

    # v1.8.0 不降级硬门禁：重算不得把任何能力 level 调低。
    # 默认开启；--allow-regress 仅供人批准的数据迁移显式绕过。
    if not getattr(args, "allow_regress", False):
        down = no_regress(ledger, model)
        if down:
            print("[BLOCK] 重算会降级以下能力，拒绝写盘：" + "; ".join(down[:10]),
                  file=sys.stderr)
            sys.exit(2)

    lc = ledger.get("lifecycle", {})
    if isinstance(lc, dict) and lc.get("state", "active") != "active":
        print(f"[BLOCK] 项目生命周期为 {lc.get('state')}：冻结/归档期间不得写入账本。"
              "用 lifecycle.py unfreeze --approved-by <人> 解冻（归档为终态）。",
              file=sys.stderr)
        sys.exit(2)

    ledger["capability_model"] = model
    ledger["last_updated"] = ts
    Path(ledger_path).parent.mkdir(parents=True, exist_ok=True)
    Path(ledger_path).write_text(json.dumps(ledger, ensure_ascii=False, indent=2))

    if not args.no_board and Path(board_path).exists():
        compact = json.dumps(ledger, ensure_ascii=False, separators=(",", ":"))
        html = Path(board_path).read_text()
        pattern = r"const EMBED = \{.*?\};\nlet DATA"
        if not re.search(pattern, html, re.S):
            raise SystemExit("看板 EMBED 同步失败：未找到 const EMBED / let DATA 标记")
        # 用 lambda 作为替换值：避免账本中的反斜杠被 re.sub 解释为转义；
        # 不再用 html2 != html 判断成功——状态未变时内容本就相同，那是正常幂等。
        html2 = re.sub(
            pattern,
            lambda _m: "const EMBED = " + compact + ";\nlet DATA",
            html, count=1, flags=re.S,
        )
        Path(board_path).write_text(html2)
        print("已同步账本与看板内嵌数据")
    else:
        print("已写入账本（看板未同步）")


if __name__ == "__main__":
    main()
