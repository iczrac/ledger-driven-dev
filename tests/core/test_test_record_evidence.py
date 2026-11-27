"""第 32 条不变量 test_record_evidence_valid：L4 测试记录必须与真实证据对得上。

背景
----
L4 的判定规则是「docs/test_records/ 有测试记录」。只看路径存在会漏掉三类假绿：

1. 记录正文从不被核对——用例名可以凭空编造，日期可以手写硬编码；
2. registry 声明了不存在的记录路径，生成器只打印 WARN，没有机器检查把它揪出来；
3. 旧记录可以冒充新证据——记录与当前测试报告之间没有任何绑定。

这组用例把第 32 条钉死：四路并重（声明真实性 / 报告哈希对账 / 用例真实性 /
时间序），缺任一路即不得算通过；旧格式记录（缺机器字段）判 na 而不是 fail。

记录字段口径与 scripts/gen_test_records.py 的渲染口径一致——同一份契约，
生成器负责产出，校验器负责验。
"""
MODULE_ID = "core"

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _base import ROOT, demo_copy, run_verify  # noqa: F401  确保 sys.path 指向 templates/

# 直接按路径加载权威源 templates/verify_ledger.py：不能靠 sys.path 顺序，
# 因为 examples/demo-shop/governance/ 下有同名副本（两份必须逐字节一致）。
_spec = importlib.util.spec_from_file_location(
    "template_verify_ledger", ROOT / "templates" / "verify_ledger.py")
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

CAP_CODE = "APP.CORE.ORDER.01"
RECORD_REL = "docs/test_records/APP.CORE.ORDER.01_TEST_RECORD.md"
REPORT_GENERATED_AT = "2026-11-27 01:35 HKT"
RECORD_GENERATED_AT = "2026-11-27T01:35:00+08:00"
CASES = [
    {"id": "mod_alpha.TestAlpha.test_ok", "file": "tests/unit/test_alpha.py",
     "status": "pass"},
    {"id": "mod_alpha.TestAlpha.test_other", "file": "tests/unit/test_alpha.py",
     "status": "pass"},
]


class TestRecordEvidenceTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="testrec-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.gov = self.tmp / "governance"
        self.gov.mkdir(parents=True)
        (self.tmp / "docs" / "test_records").mkdir(parents=True)
        self._write_report()

    # ------------------------------------------------------------ 夹具

    def _write_report(self, cases=None, generated_at=REPORT_GENERATED_AT):
        cases = CASES if cases is None else cases
        report = {
            "schema": "ledger-test-report/1",
            "generated_at": generated_at,
            "test_dir": "tests",
            "command": "unittest load from tests",
            "load_errors": [],
            "summary": {"total": len(cases),
                        "passed": sum(1 for c in cases if c["status"] == "pass"),
                        "failed": 0, "errors": 0, "skipped": 0},
            "cases": cases,
            "overall": "pass",
        }
        (self.gov / "test_report.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return report

    def _report_sha(self):
        import hashlib
        return hashlib.sha256(
            (self.gov / "test_report.json").read_bytes()).hexdigest()

    def _record_text(self, sha=None, generated_at=RECORD_GENERATED_AT,
                     cases=None, report_generated_at=REPORT_GENERATED_AT,
                     legacy=False):
        """按 gen_test_records.py 的字段口径渲染一份测试记录。"""
        if legacy:
            return ("# 订单测试记录\n\n"
                    "- 日期：2026-11-17\n"
                    "- 覆盖：`test_alpha.py`\n"
                    "- 结果：2 passed\n")
        cases = CASES if cases is None else cases
        ids = [c["id"] for c in cases]
        return "\n".join([
            "# 订单测试记录",
            "",
            "- schema: ledger-test-record/1",
            f"- cap_code: {CAP_CODE}",
            "- cap_name: 订单",
            "- source_report: governance/test_report.json",
            f"- source_sha256: {sha or self._report_sha()}",
            f"- report_generated_at: {report_generated_at}",
            f"- generated_at: {generated_at}",
            "- time_basis: evidence_report",
            '- 覆盖: ["tests/unit/test_alpha.py"]',
            "- 声明未覆盖: []",
            f"- 结果: {len(ids)} passed",
            "- cases: " + json.dumps(ids, ensure_ascii=False),
            "",
        ])

    def _write_record(self, **kwargs):
        path = self.tmp / RECORD_REL
        path.write_text(self._record_text(**kwargs), encoding="utf-8")
        return path

    def _registry(self, declared=(RECORD_REL,)):
        return {
            "project": {
                "code": "APP", "name": "App", "root": ".",
                "governance_gate": False,
                "contracts_dir": "src/contracts", "unit_test_dir": "tests",
                "test_record_dir": "docs/test_records", "docs_dir": "docs",
                "governance_dir": "governance",
            },
            "modules": [{
                "code": "CORE", "name": "核心", "src": ["src/"],
                "caps": [{
                    "name": "订单", "domain": "ORDER",
                    "impl": ["src/domain/order.py"],
                    "tests": ["tests/unit/test_alpha.py"],
                    "test_records": list(declared),
                }],
            }],
        }

    def _caps(self, records=(RECORD_REL,)):
        return [{
            "code": CAP_CODE,
            "doc_index": {"test_records": [{"path": p} for p in records]},
        }]

    def _check(self, registry=None, caps=None):
        registry = self._registry() if registry is None else registry
        caps = self._caps() if caps is None else caps
        return V.check_test_record_evidence(self.tmp, registry, caps, self.gov)

    def _track(self):
        """把临时目录纳入 git index（若它在 git 仓库里）——否则「已入库」无从核对。

        返回 True 表示 index 可读（记录必须已 add），False 表示非 git 环境
        （校验器会跳过「已入库」子判据，只核对存在性）。
        """
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.tmp), "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            return False
        if proc.returncode != 0 or proc.stdout.strip() != "true":
            return False
        subprocess.run(["git", "-C", str(self.tmp), "add", "-f", "."],
                       capture_output=True, text=True)
        return True

    # ------------------------------------------------------------ 正向

    def test_valid_record_passes_all_four_routes(self):
        """四路全对 → pass。"""
        self._write_record()
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "pass", detail)

    def test_no_declaration_is_na_not_pass(self):
        """没有任何声明 → na（未启用），绝不记 pass。"""
        status, detail = self._check(registry=self._registry(declared=()),
                                     caps=[])
        self.assertEqual(status, "na", detail)
        self.assertIn("无记录", detail)

    def test_legacy_record_without_machine_fields_is_na(self):
        """旧格式记录（只有日期/覆盖/结果）判 na 而不是 fail。

        旧记录不是伪造的证据，只是没到可机读的新格式——判 fail 会误伤存量项目。
        """
        self._write_record(legacy=True)
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "na", detail)
        self.assertIn("缺机器字段", detail)

    # ------------------------------------------------------------ 负向

    def test_declared_but_missing_file_fails(self):
        """声明了却不存在 → fail（旧实现只打印 WARN，没有任何机器检查）。"""
        status, detail = self._check()
        self.assertEqual(status, "fail", detail)
        self.assertIn("不存在", detail)

    def test_stale_source_sha256_fails(self):
        """source_sha256 与当前报告不符 → fail（拿旧记录冒充新证据）。"""
        self._write_record(sha="0" * 64)
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "fail", detail)
        self.assertIn("source_sha256", detail)

    def test_fabricated_case_name_fails(self):
        """记录里编造的用例名 → fail（报告里根本没有这个用例）。"""
        self._write_record(cases=[{"id": "mod_alpha.TestAlpha.test_ok",
                                   "file": "tests/unit/test_alpha.py",
                                   "status": "pass"},
                                  {"id": "mod_alpha.TestAlpha.test_invented",
                                   "file": "tests/unit/test_alpha.py",
                                   "status": "pass"}])
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "fail", detail)
        self.assertIn("test_invented", detail)

    def test_non_passing_case_in_record_fails(self):
        """报告里没通过的用例不得写进记录 → fail。"""
        self._write_report(cases=CASES + [
            {"id": "mod_alpha.TestAlpha.test_broken",
             "file": "tests/unit/test_alpha.py", "status": "fail"}])
        self._write_record(cases=CASES + [
            {"id": "mod_alpha.TestAlpha.test_broken",
             "file": "tests/unit/test_alpha.py", "status": "fail"}])
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "fail", detail)
        self.assertIn("test_broken", detail)

    def test_record_older_than_report_fails(self):
        """记录时间早于报告生成时间 → fail（旧证据冒充新证据）。"""
        self._write_record(generated_at="2026-11-20T09:00:00+08:00")
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "fail", detail)
        self.assertIn("早于报告生成时间", detail)

    def test_untracked_record_fails(self):
        """记录存在但未入库 → fail（「本机有、仓库没有」是最坏的一类绿灯）。"""
        if not self._git_available():
            self.skipTest("环境无 git，跳过「已入库」子判据")
        self._write_record()
        status, detail = self._check()
        self.assertEqual(status, "fail", detail)
        self.assertIn("未入库", detail)

    def test_tracked_record_is_accepted(self):
        """同一份记录纳入 git index 后 → 不再因「未入库」而红。"""
        if not self._git_available():
            self.skipTest("环境无 git，跳过「已入库」子判据")
        self._write_record()
        self._track()
        status, detail = self._check()
        self.assertEqual(status, "pass", detail)

    def _git_available(self):
        try:
            proc = subprocess.run(["git", "-C", str(self.tmp), "init", "-q"],
                                  capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError):
            return False
        return proc.returncode == 0

    # ------------------------------------------------------------ 真实仓库

    def test_demo_legacy_records_are_na(self):
        """示例仓的 3 份旧格式记录 → na（存量项目不被新判据误伤）。"""
        with demo_copy() as (root, ledger, reg, board):
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            checks = {c["id"]: c for c in payload["checks"]}
            self.assertIn("test_record_evidence_valid", checks)
            item = checks["test_record_evidence_valid"]
            self.assertEqual(item["status"], "na", item["detail"])
            self.assertIn("缺机器字段", item["detail"])
            # 存量判据一条都不能被放宽
            self.assertEqual(payload["failed"], 0)

    def test_check_count_is_32(self):
        """不变量总数 31 → 32；旧判据一条不少。"""
        with demo_copy() as (root, ledger, reg, board):
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            self.assertEqual(len(payload["checks"]), 32)
            self.assertEqual(payload["failed"], 0)


if __name__ == "__main__":
    unittest.main()
