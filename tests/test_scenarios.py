"""场景矩阵专项：把「支持哪些场景」变成可执行的证据。

覆盖状态来自 scripts/scenario_matrix.py 的单一定义；本文件对高风险场景
跑真实探针（真实临时项目、真实 CLI），其余只校验定义完整性。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy
from lifecycle import apply as lc_apply
from scenario_guard import collect, evaluate
from scenario_matrix import SCENARIOS, render_md, summary, validate

GUARD = ROOT / "scripts" / "scenario_guard.py"
LIFECYCLE = ROOT / "scripts" / "lifecycle.py"


def base_facts(**over) -> dict:
    facts = {
        "mode": "governed",
        "ledger_state": "active",
        "registry_state": "ok",
        "ledger_version": "1.0",
        "lifecycle": {"state": "active", "approved_by": "", "reason": "", "log_entries": 0},
        "current_fingerprint": "fp-current",
        "expect_fingerprint": None,
        "report": {"path": "test_report.json", "present": True, "overall": "pass",
                   "generated_at": "2026-01-01 00:00 HKT", "has_binding": True,
                   "declared_fresh": None},
        "board_synced": True,
        "git": {"present": True, "shallow": False},
        "retired": {"codes": [], "conflicts": []},
        "claims": [],
        "hygiene": {"absolute_paths": []},
        "template_sync": True,
        "scan": {"files": 12, "truncated": False},
        "registry_modules": 3,
    }
    facts.update(over)
    return facts


def check(result: dict, cid: str) -> dict:
    return next(c for c in result["checks"] if c["id"] == cid)


class ScenarioDefinitionTest(unittest.TestCase):
    def test_matrix_definition_is_valid(self):
        self.assertEqual(validate(), [])
        self.assertGreaterEqual(len(SCENARIOS), 40)

    def test_every_covered_scenario_has_a_probe(self):
        self.assertTrue(all(s["probe"] for s in SCENARIOS if s["status"] == "covered"))

    def test_every_gap_has_an_explicit_cost(self):
        self.assertTrue(all(s["note"] for s in SCENARIOS if s["status"] == "gap"))

    def test_matrix_render_is_deterministic(self):
        self.assertEqual(render_md(), render_md())
        self.assertIn("场景逐项", render_md())

    def test_summary_counts_match_definition(self):
        s = summary()
        self.assertEqual(s["total"], len(SCENARIOS))
        self.assertEqual(sum(s["by_status"].values()), len(SCENARIOS))
        self.assertGreaterEqual(s["coverage"], 0.7)


class ScenarioProbeTest(unittest.TestCase):
    def test_corrupt_ledger_blocks_writes(self):
        r = evaluate(base_facts(ledger_state="corrupt", mode="corrupt"))
        self.assertEqual(check(r, "ledger_parseable")["status"], "block")
        self.assertIn("generate", r["blocked_actions"])
        self.assertIn("verify", r["allowed_actions"])
        self.assertTrue(r["route_hint"]["blocked"])

    def test_frozen_blocks_writes_but_allows_read(self):
        r = evaluate(base_facts(mode="frozen", lifecycle={
            "state": "frozen", "approved_by": "张三", "reason": "发布窗口", "log_entries": 1}))
        self.assertEqual(check(r, "lifecycle_writable")["status"], "block")
        self.assertIn("generate", r["blocked_actions"])
        self.assertIn("verify", r["allowed_actions"])
        self.assertEqual(r["route_hint"]["expert"], "ledger-steward")

    def test_archive_is_terminal_even_for_lifecycle_writes(self):
        r = evaluate(base_facts(mode="archived", lifecycle={
            "state": "archived", "approved_by": "张三", "reason": "交付", "log_entries": 2}))
        self.assertIn("lifecycle", r["blocked_actions"])
        self.assertFalse(r["summary"]["writable"])

    def test_unsupported_version_blocks(self):
        r = evaluate(base_facts(ledger_version="9.9"))
        self.assertEqual(check(r, "schema_compat")["status"], "block")
        self.assertIn("decide", r["blocked_actions"])

    def test_missing_version_warns_instead_of_blocking(self):
        r = evaluate(base_facts(ledger_version=None))
        self.assertEqual(check(r, "schema_compat")["status"], "warn")
        self.assertEqual(r["blocked_actions"], [])

    def test_cas_rejects_stale_write(self):
        r = evaluate(base_facts(expect_fingerprint="fp-read-earlier"))
        self.assertEqual(check(r, "concurrent_write")["status"], "block")
        self.assertIn("generate", r["blocked_actions"])

    def test_fingerprint_drift_detected(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            d = json.loads(ledger.read_text())
            fp = d["capability_model"]["history"]["current_fingerprint"]
            p = subprocess.run(
                [sys.executable, str(GUARD), "--target", str(proj),
                 "--expect-fingerprint", fp + "x", "--strict"],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn("concurrent_write", p.stdout)

    def test_stale_report_downgrades_evidence(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            report = proj / "governance" / "test_report.json"
            gen = proj / "governance" / "build_capability_model.py"
            cmd = [sys.executable, str(gen), "--root", str(tmp),
                   "--registry", str(reg), "--ledger", str(ledger),
                   "--board", str(board), "--test-report", str(report),
                   "--strict-evidence"]

            def run() -> dict:
                p = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                return json.loads(ledger.read_text())

            first = run()
            self.assertTrue(first["capability_model"]["summary"]["evidence_bound"])
            self.assertEqual(first["capability_model"]["summary"]["evidence_freshness"], "fresh")
            # 报告没重跑，但测试源码变了 —— v0.7.0 会继续挂 verified
            f = proj / "tests" / "unit" / "test_order.py"
            f.write_text(f.read_text() + "\n# changed after test run\n", encoding="utf-8")
            second = run()
            caps = [c for p_ in second["capability_model"]["projects"]
                    for m in p_["modules"] for c in m["caps"]]
            self.assertTrue(all(c["evidence_tier"] == "declared" for c in caps))
            self.assertEqual(second["capability_model"]["summary"]["evidence_freshness"], "stale")
            self.assertFalse(second["capability_model"]["summary"]["evidence_bound"])

    def test_guard_detects_stale_report(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            f = proj / "tests" / "unit" / "test_order.py"
            f.write_text(f.read_text() + "\n# changed after test run\n", encoding="utf-8")
            p = subprocess.run([sys.executable, str(GUARD), "--target", str(proj),
                                "--strict", "--json"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2, p.stderr)
            data = json.loads(p.stdout)
            fresh = next(c for c in data["checks"] if c["id"] == "evidence_fresh")
            self.assertEqual(fresh["status"], "block")
            self.assertIn("claim_verified", data["blocked_actions"])

    def test_freshness_uses_content_not_clock(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            rp = proj / "governance" / "test_report.json"
            d = json.loads(rp.read_text())
            d["generated_at"] = "1999-01-01 00:00 HKT"
            rp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            p = subprocess.run(
                [sys.executable, str(proj / "governance" / "build_capability_model.py"),
                 "--root", str(tmp), "--registry", str(reg), "--ledger", str(ledger),
                 "--board", str(board), "--test-report", str(rp), "--strict-evidence"],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(ledger.read_text())["capability_model"]
                             ["summary"]["evidence_freshness"], "fresh")

    def test_unbound_report_is_warned_and_rejected_in_strict_mode(self):
        r = evaluate(base_facts(report={"path": "r.json", "present": True,
                                        "overall": "pass", "generated_at": "",
                                        "has_binding": False, "declared_fresh": None}))
        self.assertEqual(check(r, "evidence_bound")["status"], "warn")
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            rp = proj / "governance" / "test_report.json"
            d = json.loads(rp.read_text())
            d.pop("evidence_binding", None)
            rp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            p = subprocess.run(
                [sys.executable, str(proj / "governance" / "build_capability_model.py"),
                 "--root", str(tmp), "--registry", str(reg), "--ledger", str(ledger),
                 "--board", str(board), "--test-report", str(rp), "--strict-evidence"],
                capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            caps = [c for pr in json.loads(ledger.read_text())["capability_model"]["projects"]
                    for m in pr["modules"] for c in m["caps"]]
            self.assertTrue(all(c["evidence_tier"] == "declared" for c in caps))

    def test_retired_cap_conflict_blocks(self):
        r = evaluate(base_facts(retired={"codes": ["DEMO.CORE.ORDER.01"],
                                         "conflicts": ["DEMO.CORE.ORDER.01"]}))
        self.assertEqual(check(r, "retired_caps_consistent")["status"], "block")
        self.assertIn("generate", r["blocked_actions"])
        # 真实路径：retire 一个仍活跃的能力，guard 必须报冲突
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            d = json.loads(ledger.read_text())
            lc_apply(d, "retire", code="DEMO.CORE.ORDER.01", reason="取代")
            ledger.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            facts = collect(proj)
            self.assertIn("DEMO.CORE.ORDER.01", facts["retired"]["conflicts"])

    def test_absolute_path_blocks(self):
        r = evaluate(base_facts(hygiene={"absolute_paths": ["/Users/"]}))
        self.assertEqual(check(r, "path_hygiene")["status"], "block")
        self.assertIn("generate", r["blocked_actions"])

    def test_uri_schemes_are_not_false_absolute_paths(self):
        from scenario_guard import ABS_PATH_RE
        self.assertEqual(ABS_PATH_RE.findall(
            "file:// 离线打开；https://example.com/x；C:/Users/name/a.py"),
            ["C:/"])
        self.assertEqual(collect(Path(__file__).resolve().parents[1])["hygiene"]
                         ["absolute_paths"], [])

    def test_truncated_scan_warns(self):
        r = evaluate(base_facts(scan={"files": 2000, "truncated": True}))
        self.assertEqual(check(r, "scan_complete")["status"], "warn")

    def test_stale_claim_warns(self):
        r = evaluate(base_facts(claims=[{"code": "DEMO.API.QUERY.01",
                                         "actor": "ai-1", "at": "2000-01-01T00:00:00"}]))
        self.assertEqual(check(r, "execution_resumable")["status"], "warn")

    def test_guard_is_read_only(self):
        with demo_copy() as (tmp, ledger, reg, board):
            proj = tmp / "examples" / "demo-shop"
            files = {p: (p.stat().st_mtime_ns, p.stat().st_size)
                     for p in proj.rglob("*") if p.is_file()}
            p = subprocess.run([sys.executable, str(GUARD), "--target", str(proj), "--json"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            after = {q: (q.stat().st_mtime_ns, q.stat().st_size)
                     for q in proj.rglob("*") if q.is_file()}
            self.assertEqual(files, after)

    def test_guard_cli_json_is_leak_free(self):
        with demo_copy() as (tmp, ledger, reg, board):
            p = subprocess.run(
                [sys.executable, str(GUARD), "--target", str(tmp / "examples" / "demo-shop"),
                 "--json"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            data = json.loads(p.stdout)
            self.assertEqual(data["schema"], "scenario-preflight/1")
            self.assertNotIn("/Users/", p.stdout)
            self.assertNotIn(str(ROOT), p.stdout)
            self.assertTrue(data["allowed_actions"])

    def test_gap_scenarios_are_explicitly_declared(self):
        gaps = [s["id"] for s in SCENARIOS if s["status"] == "gap"]
        self.assertTrue(gaps, "场景矩阵必须诚实列出未覆盖项")
        self.assertIn("E7", gaps)
        self.assertIn("F7", gaps)


if __name__ == "__main__":
    unittest.main()
