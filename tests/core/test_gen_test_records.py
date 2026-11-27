"""L4 测试记录生成器（scripts/gen_test_records.py）的契约测试。

背景
----
L4 的判定规则是「docs/test_records/ 有测试记录」。只看路径存在会漏掉三类假绿：
记录正文从不被核对、声明了不存在的路径只打印 WARN、旧记录可以冒充新证据。
`scripts/gen_test_records.py` 是产出端（第 32 条 `test_record_evidence_valid`
是校验端），**两端必须同源**——否则生成器写一套、护栏读另一套，谁都绿。

这组用例把生成器钉住：

1. 派生正确性：记录里的字段逐字来自报告，不臆造；
2. 幂等：同一份报告重跑，记录逐字节相同（`--check` 无漂移）；
3. 缺证据不出记录：报告里没有通过用例 → 明确不出记录，不假装覆盖；
4. 篡改被 `--check` 拦下：手改记录 → exit 1 且点名该文件；
5. registry 声明同步：`--update-registry` 外科式改写，不重排；
6. **产出端与校验端同源**：生成器产的记录必须让第 32 条判据判 pass。
"""
MODULE_ID = "core"

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT  # noqa: F401  确保 sys.path 指向 templates/

GENERATOR = ROOT / "scripts" / "gen_test_records.py"
RECORD_SUFFIX = "_TEST_RECORD.md"
CAP_CODE = "APP.CORE.ORDER.01"
RECORD_REL = f"docs/test_records/{CAP_CODE}{RECORD_SUFFIX}"
REPORT_TIME = "2026-11-27 01:35 HKT"


def _load(name: str, path: Path):
    """按路径加载权威源（不能靠 sys.path 顺序：同名副本不止一份）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load("gen_test_records", GENERATOR)
V = _load("template_verify_ledger", ROOT / "templates" / "verify_ledger.py")

PASS_CASES = [
    {"id": "mod_alpha.TestAlpha.test_ok", "file": "tests/unit/test_alpha.py",
     "status": "pass"},
    {"id": "mod_alpha.TestAlpha.test_other", "file": "tests/unit/test_alpha.py",
     "status": "pass"},
]
FAIL_CASE = {"id": "mod_beta.TestBeta.test_broken", "file": "tests/unit/test_beta.py",
             "status": "fail"}


class GenTestRecordsTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gentr-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.gov = self.tmp / "governance"
        self.gov.mkdir()
        (self.tmp / "tests" / "unit").mkdir(parents=True)
        (self.tmp / "tests" / "unit" / "test_alpha.py").write_text(
            "def test_ok():\n    assert 1\n", encoding="utf-8")
        self.registry = self.tmp / "governance" / "registry.json"
        self.report = self.tmp / "governance" / "test_report.json"
        self._write_registry()
        self._write_report()

    # ------------------------------------------------------------ 夹具

    def _write_registry(self, tests=("tests/unit/test_alpha.py",)):
        reg = {
            "project": {
                "code": "APP", "name": "App", "root": ".", "governance_gate": False,
                "contracts_dir": "src/contracts", "unit_test_dir": "tests",
                "test_record_dir": "docs/test_records", "docs_dir": "docs",
                "governance_dir": "governance",
            },
            "modules": [{
                "code": "CORE", "name": "核心", "src": ["src/"],
                "caps": [{"name": "订单", "domain": "ORDER",
                          "impl": ["src/domain/order.py"],
                          "tests": list(tests)}],
            }],
        }
        self.registry.write_text(json.dumps(reg, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        return reg

    def _write_report(self, cases=None, overall="pass", generated_at=REPORT_TIME):
        cases = PASS_CASES if cases is None else cases
        rep = {
            "schema": "ledger-test-report/1",
            "generated_at": generated_at,
            "test_dir": "tests",
            "command": "unittest load from tests",
            "load_errors": [],
            "summary": {"total": len(cases),
                        "passed": sum(1 for c in cases if c["status"] == "pass"),
                        "failed": sum(1 for c in cases if c["status"] != "pass"),
                        "errors": 0, "skipped": 0},
            "cases": cases,
            "overall": overall,
        }
        self.report.write_text(json.dumps(rep, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        return rep

    def _report_sha(self):
        return hashlib.sha256(self.report.read_bytes()).hexdigest()

    def _cli(self, *args):
        # 路径按「相对项目根」给（脚本的既定语义：相对路径即 root 相对）。
        # 绝对路径形态的缺陷由 engineer-6 修，不在本文件固化成期望行为。
        cmd = [sys.executable, str(GENERATOR), "--root", str(self.tmp),
               "--registry", "governance/registry.json",
               "--report", "governance/test_report.json", *args]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _record_path(self):
        return self.tmp / RECORD_REL

    def _git_track(self):
        """把临时目录纳入 git index：护栏的「已入库」子判据需要 index 可读。"""
        try:
            probe = subprocess.run(["git", "-C", str(self.tmp), "rev-parse",
                                    "--is-inside-work-tree"],
                                   capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            return False
        if probe.returncode != 0 or probe.stdout.strip() != "true":
            return False
        subprocess.run(["git", "-C", str(self.tmp), "add", "-f", "."],
                       capture_output=True, text=True)
        return True

    # ------------------------------------------------------------ 1 派生正确性

    def test_record_fields_come_from_report_verbatim(self):
        """记录里的字段逐字来自报告：sha256 / cases / 覆盖 / 结果 / 时间。"""
        self.assertEqual(self._cli().returncode, 0)
        path = self._record_path()
        self.assertTrue(path.is_file(), "记录文件没生成")
        text = path.read_text(encoding="utf-8")
        fields = V.parse_record_fields(text)
        self.assertEqual(fields["source_sha256"], self._report_sha())
        self.assertEqual(fields["report_generated_at"], REPORT_TIME)
        self.assertEqual(fields["generated_at"], "2026-11-27T01:35:00+08:00")
        self.assertEqual(fields["time_basis"], "evidence_report")
        self.assertEqual(V.parse_record_cases(fields["cases"]),
                         [c["id"] for c in PASS_CASES])
        self.assertIn('- 覆盖: ["tests/unit/test_alpha.py"]', text)
        self.assertIn(f"- 结果: {len(PASS_CASES)} passed", text)
        # 没通过的用例不得进记录
        self.assertNotIn("test_broken", text)

    def test_only_pass_cases_are_recorded(self):
        """报告里 status != pass 的用例不得写进记录。"""
        self._write_report(cases=PASS_CASES + [FAIL_CASE])
        self.assertEqual(self._cli().returncode, 0)
        text = self._record_path().read_text(encoding="utf-8")
        self.assertNotIn("test_broken", text)
        self.assertIn(f"- 结果: {len(PASS_CASES)} passed", text)

    # ------------------------------------------------------------ 2 幂等

    def test_regenerate_is_byte_identical(self):
        """同一份报告重跑，记录逐字节相同（幂等是「重跑 diff 为空」的机器证明）。"""
        self.assertEqual(self._cli().returncode, 0)
        first = self._record_path().read_bytes()
        self.assertEqual(self._cli().returncode, 0)
        second = self._record_path().read_bytes()
        self.assertEqual(first, second, "重跑产生了 diff（时间戳漂移？）")

    def test_check_is_clean_after_generate(self):
        """生成 + 同步声明后 --check 必须 0 问题。

        注意顺序：--check 同时核对「记录内容」与「registry 声明」，
        所以必须先 --update-registry 把声明写进去，否则「声明缺失」本身
        就是一条不一致——那是设计，不是缺陷。
        """
        self.assertEqual(self._cli().returncode, 0)
        self.assertEqual(self._cli("--update-registry").returncode, 0)
        r = self._cli("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("[不一致]", r.stdout)

    # ------------------------------------------------------------ 3 缺证据不出记录

    def test_no_passing_evidence_means_no_record(self):
        """报告里没有通过用例 → 不出记录，并明确报出来（不臆造证据）。"""
        self._write_report(cases=[FAIL_CASE])
        self._write_registry(tests=("tests/unit/test_beta.py",))
        r = self._cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self._record_path().exists(),
                         "没有通过用例却生成了记录")
        self.assertIn("不出记录", r.stdout)

    def test_cap_without_declared_tests_is_skipped(self):
        """未声明 tests 的 cap 缺的是 L1/L2 证据，不是测试记录——跳过并说明。"""
        self._write_registry(tests=())
        r = self._cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self._record_path().exists())
        self.assertIn("未声明 tests", r.stdout)

    # ------------------------------------------------------------ 4 篡改被拦下

    def test_check_fails_on_tampered_record(self):
        """手改记录（改 sha256）→ --check 必须 exit 1 且点名该文件。"""
        self.assertEqual(self._cli().returncode, 0)
        path = self._record_path()
        path.write_text(path.read_text(encoding="utf-8").replace(
            self._report_sha(), "0" * 64), encoding="utf-8")
        r = self._cli("--check")
        self.assertEqual(r.returncode, 1, "篡改未被拦下")
        self.assertIn("[不一致]", r.stdout)
        self.assertIn(RECORD_SUFFIX, r.stdout)

    def test_check_fails_on_missing_record(self):
        """记录文件缺失 → --check 必须 exit 1（缺就是缺，不当没这回事）。"""
        r = self._cli("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("缺记录文件", r.stdout)

    # ------------------------------------------------------------ 5 registry 声明同步

    def test_update_registry_writes_declarations_surgically(self):
        """--update-registry 外科式写声明：不重排、不动别的键。"""
        before = json.loads(self.registry.read_text(encoding="utf-8"))
        before_cap = before["modules"][0]["caps"][0]
        r = self._cli("--update-registry")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        after = json.loads(self.registry.read_text(encoding="utf-8"))
        after_cap = after["modules"][0]["caps"][0]
        # 新增声明，且只新增这一个键
        self.assertEqual(after_cap["test_records"], [RECORD_REL])
        self.assertEqual(set(after_cap) - set(before_cap), {"test_records"})
        self.assertEqual(set(before_cap) - set(after_cap), set())
        # 键顺序不被重排（外科式改写：tests 之后插入 test_records）
        self.assertEqual([k for k in after_cap if k in before_cap],
                         list(before_cap))
        # 声明与实际文件一一对应
        self.assertTrue((self.tmp / after_cap["test_records"][0]).is_file())
        # 其余部分一字未动
        before_rest = json.loads(json.dumps(before))
        del before_rest["modules"][0]["caps"][0]["tests"]
        after_rest = json.loads(json.dumps(after))
        del after_rest["modules"][0]["caps"][0]["tests"]
        del after_rest["modules"][0]["caps"][0]["test_records"]
        self.assertEqual(before_rest, after_rest)

    def test_check_flags_registry_declaration_mismatch(self):
        """声明与实际文件不一致 → --check 必须点名（声明了却不存在要被抓到）。"""
        reg = json.loads(self.registry.read_text(encoding="utf-8"))
        reg["modules"][0]["caps"][0]["test_records"] = ["docs/test_records/GONE.md"]
        self.registry.write_text(json.dumps(reg, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        r = self._cli("--check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("test_records 声明应为", r.stdout)

    # ------------------------------------------------------------ 6 产出端与校验端同源（核心）

    def test_generated_record_satisfies_the_guardrail(self):
        """生成器产的记录必须让第 32 条判据判 pass——两端不能各写一套格式。

        这是本组用例最关键的一条：产出端（gen_test_records.py）与校验端
        （verify_ledger.py 的 test_record_evidence_valid）如果各自演进，
        就会出现「生成器说写好了、护栏说对不上」的空转。
        """
        self.assertEqual(self._cli().returncode, 0)
        self.assertEqual(self._cli("--update-registry").returncode, 0)
        self._git_track()
        reg = json.loads(self.registry.read_text(encoding="utf-8"))
        caps = [{"code": CAP_CODE,
                 "doc_index": {"test_records": [{"path": RECORD_REL}]}}]
        status, detail = V.check_test_record_evidence(
            self.tmp, reg, caps, self.gov)
        self.assertEqual(status, "pass", detail)

    def test_guardrail_catches_generator_output_when_report_moves(self):
        """报告一变，旧的记录立刻对不上（这正是第 32 条存在的意义）。"""
        self.assertEqual(self._cli().returncode, 0)
        self.assertEqual(self._cli("--update-registry").returncode, 0)
        self._git_track()
        reg = json.loads(self.registry.read_text(encoding="utf-8"))
        caps = [{"code": CAP_CODE,
                 "doc_index": {"test_records": [{"path": RECORD_REL}]}}]
        self.assertEqual(
            V.check_test_record_evidence(self.tmp, reg, caps, self.gov)[0], "pass")
        # 报告变了（生成时刻变 → 字节摘要变）→ 旧记录与新报告对不上
        self._write_report(generated_at="2026-11-27 02:00 HKT")
        status, detail = V.check_test_record_evidence(
            self.tmp, reg, caps, self.gov)
        self.assertEqual(status, "fail", detail)
        self.assertIn("source_sha256", detail)

    # ------------------------------------------------------------ 7 不从坏报告派生

    def test_refuses_to_derive_from_failing_report(self):
        """报告整体未通过 → 拒绝派生（不得据此产出 L4 证据）。"""
        self._write_report(overall="fail")
        r = self._cli()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("整体未通过", r.stdout + r.stderr)
        self.assertFalse(self._record_path().exists())

    def test_refuses_when_report_missing(self):
        """报告不存在 → 拒绝派生（无证据不产出）。"""
        self.report.unlink()
        r = self._cli()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("测试报告不存在", r.stdout + r.stderr)
        self.assertFalse(self._record_path().exists())


if __name__ == "__main__":
    unittest.main()
