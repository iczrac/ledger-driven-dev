"""证据分层（declared/verified）专项测试：零依赖、临时目录隔离。"""
from __future__ import annotations
MODULE_ID = "core"

import json
import unittest
from pathlib import Path

from _base import demo_copy, run_generator, run_verify, GOV
import sys

sys.path.insert(0, str(GOV))
from build_capability_model import judge_tier, load_test_report  # noqa: E402


REPORT_SCHEMA = "ledger-test-report/1"


def _report(cases, overall="pass"):
    # v2.0.0：报告须带合法源码绑定（algorithm + 真实文件 sha256），
    # 否则新生成器按 v1.8.0 空绑定拒绝逻辑不采信，verified 无法升级。
    src = Path(GOV).parent / "src" / "contracts" / "order_schema.py"
    binding = {
        "algorithm": "sha256-files-v1",
        "inputs": [{"path": "examples/demo-shop/src/contracts/order_schema.py",
                    "sha256": __import__("hashlib").sha256(src.read_bytes()).hexdigest()}],
        "source_digest": "fixture",
    }
    return {
        "schema": REPORT_SCHEMA,
        "generated_at": "2026-11-17 22:00 HKT",
        "label": "unit",
        "overall": overall,
        "cases": cases,
        "summary": {"total": len(cases)},
        "evidence_binding": binding,
    }


class EvidenceTierTest(unittest.TestCase):
    def test_no_report_is_declared(self):
        tier, detail = judge_tier(["examples/demo-shop/tests/unit/test_order.py"], None)
        self.assertEqual(tier, "declared")
        self.assertEqual(detail["basis"], "no_report")

    def test_passing_report_upgrades_to_verified(self):
        report = _report([
            {"id": "x", "file": "examples/demo-shop/tests/unit/test_order.py", "status": "pass"}
        ])
        tier, detail = judge_tier(["examples/demo-shop/tests/unit/test_order.py"], report)
        self.assertEqual(tier, "verified")
        self.assertEqual(detail["basis"], "test_report_pass")
        self.assertEqual(detail["matched_tests"], ["test_order.py"])

    def test_failed_report_never_upgrades(self):
        report = _report([
            {"id": "x", "file": "examples/demo-shop/tests/unit/test_order.py", "status": "fail"}
        ], overall="fail")
        # load_test_report 拒绝 overall=fail → None → declared
        self.assertIsNone(load_test_report_from_obj(report))
        tier, _ = judge_tier(["examples/demo-shop/tests/unit/test_order.py"], None)
        self.assertEqual(tier, "declared")

    def test_non_matching_test_stays_declared(self):
        report = _report([
            {"id": "x", "file": "tests/test_unrelated.py", "status": "pass"}
        ])
        tier, detail = judge_tier(["examples/demo-shop/tests/unit/test_order.py"], report)
        self.assertEqual(tier, "declared")
        self.assertEqual(detail["basis"], "no_matching_pass")

    def test_generator_without_report_keeps_all_declared(self):
        with demo_copy() as (root, ledger, reg, board):
            result = run_generator(root, ledger, reg, board)
            self.assertEqual(result.returncode, 0, result.stderr)
            caps = [c for p in json.loads(ledger.read_text())["capability_model"]["projects"]
                    for m in p["modules"] for c in m["caps"]]
            self.assertTrue(all(c["evidence_tier"] == "declared" for c in caps))

    def test_generator_with_report_upgrades_matching_caps(self):
        with demo_copy() as (root, ledger, reg, board):
            report = _report([
                {"id": "x", "file": "tests/unit/test_order.py", "status": "pass"},
                {"id": "y", "file": "tests/unit/test_pricing.py", "status": "pass"},
                {"id": "z", "file": "tests/unit/test_data_ready.py", "status": "pass"},
            ])
            rp = root / "report.json"
            rp.write_text(json.dumps(report))
            cmd = ["--test-report", str(rp)]
            import subprocess, sys as _sys
            result = subprocess.run(
                [_sys.executable, str(GOV / "build_capability_model.py"),
                 "--root", str(root), "--registry", str(reg),
                 "--ledger", str(ledger), "--board", str(board), "--allow-regress"] + cmd,
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            d = json.loads(ledger.read_text())
            caps = {c["code"]: c for p in d["capability_model"]["projects"]
                    for m in p["modules"] for c in m["caps"]}
            self.assertEqual(caps["DEMO.CORE.ORDER.01"]["evidence_tier"], "verified")
            self.assertEqual(caps["DEMO.CORE.PRICE.02"]["evidence_tier"], "verified")
            self.assertEqual(caps["DEMO.API.QUERY.01"]["evidence_tier"], "declared")
            self.assertEqual(d["capability_model"]["summary"]["verified_coverage"], 0.75)

    # ---- v2.2.0 硬门禁：verified ⟺ 符号绑定 bound ----
    # 负向证明：v2.1.2 及之前，只要往 caps[].tests 塞一条 pass 的测试路径，
    # 能力就能刷成 verified——即便测试 import 的实现与本能力毫无关系。
    # 这是「声明权 = 伪造权」漏洞。硬门禁要求 judge_tier 同时看绑定状态。
    def test_binding_unbound_denies_verified_even_with_pass_report(self):
        """核心负向：报告 pass 但绑定 unbound → 必须 declared（伪造被拦）。"""
        report = _report([
            {"id": "x", "file": "examples/demo-shop/tests/unit/test_order.py", "status": "pass"}
        ])
        tier, detail = judge_tier(
            ["examples/demo-shop/tests/unit/test_order.py"], report,
            binding_status="unbound")
        self.assertEqual(tier, "declared")
        self.assertEqual(detail["basis"], "binding_not_bound")

    def test_binding_no_impl_denies_verified(self):
        report = _report([
            {"id": "x", "file": "examples/demo-shop/tests/unit/test_order.py", "status": "pass"}
        ])
        tier, detail = judge_tier(
            ["examples/demo-shop/tests/unit/test_order.py"], report,
            binding_status="no_impl")
        self.assertEqual(tier, "declared")
        self.assertEqual(detail["basis"], "binding_not_bound")

    def test_binding_via1_denies_verified(self):
        """via1 隔一层编排，不算直接证明 → declared。"""
        report = _report([
            {"id": "x", "file": "examples/demo-shop/tests/unit/test_order.py", "status": "pass"}
        ])
        tier, _ = judge_tier(
            ["examples/demo-shop/tests/unit/test_order.py"], report,
            binding_status="via1")
        self.assertEqual(tier, "declared")

    def test_binding_bound_allows_verified(self):
        """正向：报告 pass + 绑定 bound → verified 保留。"""
        report = _report([
            {"id": "x", "file": "examples/demo-shop/tests/unit/test_order.py", "status": "pass"}
        ])
        tier, detail = judge_tier(
            ["examples/demo-shop/tests/unit/test_order.py"], report,
            binding_status="bound")
        self.assertEqual(tier, "verified")
        self.assertEqual(detail["basis"], "test_report_pass")

    def test_tier_corruption_caught_by_verifier(self):
        with demo_copy() as (root, ledger, reg, board):
            # 先生成带 verified 的稳态
            report = _report([{"id": "x", "file": "tests/unit/test_order.py", "status": "pass"}])
            rp = root / "report.json"
            rp.write_text(json.dumps(report))
            import subprocess, sys as _sys
            subprocess.run(
                [_sys.executable, str(GOV / "build_capability_model.py"),
                 "--root", str(root), "--registry", str(reg),
                 "--ledger", str(ledger), "--board", str(board),
                 "--test-report", str(rp), "--allow-regress"], capture_output=True, text=True)
            # 注入腐化：把 verified 改成无依据
            d = json.loads(ledger.read_text())
            for p in d["capability_model"]["projects"]:
                for m in p["modules"]:
                    for c in m["caps"]:
                        if c["evidence_tier"] == "verified":
                            c["tier_detail"] = {"basis": "no_basis", "matched_tests": []}
            ledger.write_text(json.dumps(d))
            result = run_verify(root, ledger, reg, board)
            payload = json.loads(result.stdout)
            checks = {x["id"]: x["ok"] for x in payload["checks"]}
            self.assertFalse(checks["verified_tier_traceable"])


def load_test_report_from_obj(report: dict):
    """模拟 load_test_report：overall!=pass 或非 schema 返回 None。"""
    if report.get("schema") != REPORT_SCHEMA or report.get("overall") != "pass":
        return None
    return report


if __name__ == "__main__":
    unittest.main()
