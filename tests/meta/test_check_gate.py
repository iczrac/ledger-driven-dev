"""质量门禁的快检档（--fast）：阶段表单一来源 + 快检覆盖 + 契约检查不漏。

为什么
----
全量门禁 `bash scripts/check.sh` 实测约 445s，其中「测试」阶段（全量用例）
约 400s（占 90%）。实施中途每改一点就跑一次全量不现实，因此加一档「快检」
（`--fast`），把中途验证压到 50s 级。

纪律
----
1. **单一阶段表**：`--fast` 必须由同一份阶段表过滤得出，禁止手写第二份清单——
   两份清单必然漂移，而这正是门禁要防的病；
2. **快检不是提交依据**：输出必须明示「中途快检，非提交依據」，避免被读成
   「可以提交了」；
3. **快检不漏契约检查**：模板/示例同步、看板 EMBED、文档内链等阶段都在快检内。
   上次看板改名引入的门禁回归正是被「同步」阶段抓到的，快检不能把它省掉。

本文件测 check.sh 自身（脚本属元层）。为守住门禁时长，本文件不跑真实全量
用例：用「从 check.sh 抽出真代码 + 桩化阶段函数」的夹具执行真实分支逻辑，
并对同步 / 卫生两个阶段做真实执行；全量门禁与快检的实测耗时由发版前一次性
取证（`time bash scripts/check.sh --fast` / `time bash scripts/check.sh`）。
"""
from __future__ import annotations
MODULE_ID = "meta"

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

CHECK_SH = ROOT / "scripts" / "check.sh"

# 「快检不是提交依据」的明示文案：必须出现在快检输出里。
NOT_BASIS_MARK = "中途快检，非提交依據"

# 阶段表区段的边界标记（check.sh 内唯一）。
_TABLE_MARK = "# ---------------------------------------------------------------- 阶段表"


def _read() -> str:
    return CHECK_SH.read_text(encoding="utf-8")


def _slice(text: str, start: str, end: str | None = None) -> str:
    i = text.index(start)
    j = text.index(end, i) if end else len(text)
    return text[i:j]


def _parse_table(text: str) -> list[tuple[str, str, str, str]]:
    """解析 STAGE_TABLE；每行 4 字段：显示名|阶段函数|快检是否包含|汇总短名。"""
    m = re.search(r"STAGE_TABLE=\(\n(.*?)\n\)", text, re.S | re.M)
    if not m:
        raise AssertionError("check.sh 缺少 STAGE_TABLE 阶段表")
    rows: list[tuple[str, str, str, str]] = []
    for raw in m.group(1).splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if not (raw.startswith('"') and raw.endswith('"')):
            raise AssertionError(f"阶段表行必须写成带引号的一行：{raw}")
        fields = raw[1:-1].split("|")
        if len(fields) != 4:
            raise AssertionError(
                f"阶段表行必须 4 字段（显示名|函数|快检标志|汇总名）：{raw}")
        rows.append((fields[0], fields[1], fields[2], fields[3]))
    return rows


def _function_def(text: str, name: str) -> str:
    m = re.search(rf"^{name}\(\)\{{\n.*?\n\}}", text, re.S | re.M)
    if not m:
        raise AssertionError(f"check.sh 缺少函数 {name}")
    return m.group(0)


def _build_harness(tmp: Path, text: str, rows) -> Path:
    """造一个执行真分支逻辑的夹具：真代码 + 桩化阶段函数。

    抽的是 check.sh 自己的旗标解析、阶段表、过滤驱动与 dispatch；只有
    18 个阶段函数体被桩化。这样「--fast 是否真的按表过滤」「输出是否真的
    明示非提交依据」都由真实代码回答，而不是由本文件的断言回答。
    """
    flags = _slice(text, "FAILURES=0\n", _TABLE_MARK)
    table = _slice(text, "STAGE_TABLE=(", "\n)\n") + "\n)\n"
    helpers = "\n\n".join(
        _function_def(text, n)
        for n in ("select_stages", "skipped_summary", "stage_summary"))
    notes = "\n".join(re.findall(r"^(?:note|pass|fail)\(\)\{.*?\}$", text, re.M))
    tail = _slice(text, "run(){ name=")
    stubs = "\n".join(f"{fn}(){{ return 0; }}" for _label, fn, _f, _s in rows)
    script = tmp / "check_fast_harness.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -uo pipefail\n"
        'MODE="${1:-all}"\n'
        f"{flags}\n{table}\nSELECTED=()\n\n{helpers}\n\n{notes}\n\n{stubs}\n\n{tail}",
        encoding="utf-8")
    return script


def _run_harness(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script), *args],
                          capture_output=True, text=True)


class StageTableTest(unittest.TestCase):
    """阶段表：唯一事实源 + 字段完整 + 引用的阶段函数真实存在。"""

    def test_table_rows_are_wellformed(self):
        rows = _parse_table(_read())
        self.assertEqual(len(rows), 18, "顶层阶段数应为 18")
        labels = [r[0] for r in rows]
        self.assertEqual(len(labels), len(set(labels)), "阶段显示名不得重复")
        fns = [r[1] for r in rows]
        self.assertEqual(len(fns), len(set(fns)), "阶段函数不得重复")
        for label, fn, fast, sname in rows:
            self.assertTrue(label, "显示名不得为空")
            self.assertRegex(fn, r"^stage_[a-z_]+$", f"{label} 的函数名不合规")
            self.assertIn(fast, ("0", "1"), f"{label} 的快检标志只能是 0/1")
            self.assertTrue(sname, f"{label} 缺汇总短名")

    def test_every_stage_function_is_defined(self):
        text = _read()
        for label, fn, _fast, _sname in _parse_table(text):
            self.assertIn(f"{fn}(){{", text, f"阶段「{label}」的函数 {fn} 未定义")

    def test_summary_is_derived_from_table(self):
        """末行文案必须由阶段表渲染：有人再手写一份清单时本断言必须失效。"""
        text = _read()
        self.assertIn("""printf '质量门禁全绿：%s\\n' "$(stage_summary)\"""", text)
        self.assertNotIn("质量门禁全绿：测试 /", text,
                         "全绿文案被改回手写清单：会变成第二份阶段表")

    def test_full_mode_summary_shape_unchanged(self):
        """全量模式的末行内容与改造前保持一致（增量改动不得改既有输出）。"""
        summary = " / ".join(r[3] for r in _parse_table(_read()))
        self.assertTrue(summary.startswith("测试 / 测试架构 / 证据分层 /"))
        self.assertTrue(summary.endswith("/ 验收契约 / 前置条件"))
        self.assertIn("32 条三态不变量", summary)
        self.assertIn("卫生（脱敏+文档链接）", summary)


class FastModeTest(unittest.TestCase):
    """快检：只跳全量用例那一关，且不漏契约检查。"""

    def test_fast_skips_only_the_full_test_stage(self):
        rows = _parse_table(_read())
        skipped = [r[1] for r in rows if r[2] != "1"]
        self.assertEqual(skipped, ["stage_tests"],
                         "快检只能跳「测试」这一关，其余阶段一律要跑")
        self.assertEqual(len(rows) - len(skipped), 17)

    def test_fast_keeps_sync_and_hygiene(self):
        """快检不得漏掉抓过真实回归的两个阶段（看板改名回归＝「同步」抓到的）。"""
        text = _read()
        fast = {r[1] for r in _parse_table(text) if r[2] == "1"}
        self.assertIn("stage_sync", fast, "快检漏了「同步」阶段")
        self.assertIn("stage_hygiene", fast, "快检漏了「卫生」阶段")
        # 负向证明：把同步阶段挪出快检后，上面的断言必须失效。
        broken = text.replace('"同步|stage_sync|1|同步"', '"同步|stage_sync|0|同步"')
        self.assertNotEqual(broken, text, "负向样本没能改写阶段表")
        fast_broken = {r[1] for r in _parse_table(broken) if r[2] == "1"}
        self.assertNotIn("stage_sync", fast_broken)

    def test_fast_skips_exactly_the_expensive_stage(self):
        """「比全量快」的结构性证明：被跳过的正是跑全量用例的那一关。"""
        text = _read()
        rows = _parse_table(text)
        costly = []
        for label, fn, _fast, _sname in rows:
            body = _function_def(text, fn)
            if "unittest discover" in body or "--dir tests" in body:
                costly.append(fn)
        self.assertEqual(costly, ["stage_tests"],
                         "只有「测试」阶段该跑全量用例；若别的阶段也跑，它也必须被跳过")
        skipped = [r[1] for r in rows if r[2] != "1"]
        self.assertEqual(skipped, costly,
                         "快检跳过的必须正好是最贵的那一关，否则「快」没有意义")

    def test_fast_output_declares_not_submission_basis(self):
        """输出必须明示「中途快检，非提交依據」，且开头与末行各出现一次。"""
        text = _read()
        self.assertGreaterEqual(text.count(NOT_BASIS_MARK), 2,
                                "快检的开头横幅与末行都必须明示非提交依据")
        self.assertIn("快检结果不可作为提交依据", text)
        self.assertIn("快检通过不等于可以提交", text)

    def test_fast_help_mentions_flag(self):
        text = _read()
        self.assertIn("--fast", _slice(text, "echo \"用法:", "else"))
        self.assertIn(NOT_BASIS_MARK, text)


class FastDispatchTest(unittest.TestCase):
    """行为证明：真跑一遍 check.sh 的分支逻辑（阶段函数桩化）。"""

    def setUp(self):
        self.text = _read()
        self.rows = _parse_table(self.text)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.script = _build_harness(Path(self._tmp.name), self.text, self.rows)

    @staticmethod
    def _passed(out: str) -> list[str]:
        return [m.group(1) for m in re.finditer(r"^\[PASS\] (.+)$", out, re.M)]

    def test_full_mode_runs_all_stages(self):
        r = _run_harness(self.script)
        self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-400:])
        self.assertEqual(len(self._passed(r.stdout)), 18)

    def test_fast_mode_runs_17_stages_and_skips_tests(self):
        r = _run_harness(self.script, "--fast")
        self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-400:])
        passed = self._passed(r.stdout)
        self.assertEqual(len(passed), 17, f"快检应跑 17 个阶段，实得 {passed}")
        self.assertNotIn("测试", passed, "快检不得跑全量用例那一关")
        self.assertIn("同步", passed, "快检漏了「同步」")
        self.assertIn("卫生", passed, "快检漏了「卫生」")

    def test_fast_output_states_not_submission_basis(self):
        r = _run_harness(self.script, "--fast")
        self.assertIn(NOT_BASIS_MARK, r.stdout)
        self.assertIn("快检结果不可作为提交依据", r.stdout)
        self.assertIn("快检通过不等于可以提交", r.stdout)
        self.assertIn("质量门禁快检通过", r.stdout)

    def test_only_modes_stay_exclusive_single_stage(self):
        """--only-* 仍是互斥的 MODE 分支：只跑一个阶段，且不被 --fast 影响。"""
        for mode, label in (("--only-idempotence", "幂等"),
                            ("--only-doc-lifecycle", "文档生命周期（shadow）")):
            with self.subTest(mode=mode):
                r = _run_harness(self.script, mode)
                self.assertEqual(r.returncode, 0, r.stdout[-400:])
                self.assertEqual(self._passed(r.stdout), [label])

    def test_only_mode_ignores_fast_flag(self):
        """--fast 只作用于全量阶段表；与 --only-* 同用时明确告知已忽略。"""
        r = _run_harness(self.script, "--only-idempotence", "--fast")
        self.assertEqual(r.returncode, 0, r.stdout[-400:])
        self.assertEqual(self._passed(r.stdout), ["幂等"])
        self.assertIn("已忽略快检旗标", r.stdout)

    def test_strict_flag_stays_independent(self):
        """--strict 是扫全部 args 的独立旗标：全量跑 18 阶段；--fast 时跑 17。"""
        r = _run_harness(self.script, "--strict")
        self.assertEqual(len(self._passed(r.stdout)), 18)
        r = _run_harness(self.script, "--fast", "--strict")
        self.assertEqual(len(self._passed(r.stdout)), 17)
        r = _run_harness(self.script, "--strict", "--fast")
        self.assertEqual(len(self._passed(r.stdout)), 17)

    def test_fast_runs_real_sync_and_hygiene_stages(self):
        """真跑「同步」「卫生」两个阶段：证明快检里它们不是摆设，真跑会红。"""
        text = self.text
        parts = []
        parts.append("#!/usr/bin/env bash")
        parts.append("set -uo pipefail")
        parts.append(f'cd "{ROOT}"')
        parts.append('DEMO="examples/demo-shop/governance"')
        parts.append('BOARD_DEMO="$(python3 scripts/board_path.py --target "$DEMO" --resolved)"')
        parts.append('BOARD_DEMO_NAME="$(python3 scripts/board_path.py --target "$DEMO" --filename)"')
        parts.append('BOARD_NAME="$(python3 scripts/board_path.py --target . --filename)"')
        parts.append("FAILURES=0")
        parts.append("\n".join(re.findall(r"^(?:note|pass|fail)\(\)\{.*?\}$", text, re.M)))
        parts.append(_function_def(text, "stage_sync"))
        parts.append(_function_def(text, "stage_hygiene"))
        parts.append("stage_sync; rc_sync=$?")
        parts.append("stage_hygiene; rc_hygiene=$?")
        parts.append('echo "rc_sync=$rc_sync rc_hygiene=$rc_hygiene"')
        parts.append('[ "$rc_sync" -eq 0 ] && [ "$rc_hygiene" -eq 0 ]')
        script = Path(self._tmp.name) / "real_stages.sh"
        script.write_text("\n".join(parts) + "\n", encoding="utf-8")
        r = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-400:])
        self.assertIn("看板 EMBED 与账本一致", r.stdout)
        self.assertIn("脱敏无残留；文档内链全部有效", r.stdout)


if __name__ == "__main__":
    unittest.main()
