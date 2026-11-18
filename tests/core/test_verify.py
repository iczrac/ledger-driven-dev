"""校验器自身可信：正向全通过 + 负向注入必须被抓到。"""
MODULE_ID = "core"
import copy
import json
import subprocess
import sys
import unittest

from _base import ROOT, VERIFIER, demo_copy, load_ledger, run_verify
from ledger_io import write_ledger


class VerifyTest(unittest.TestCase):
    def test_clean_ledger_passes_all_checks(self):
        with demo_copy() as (root, ledger, reg, board):
            result = run_verify(root, ledger, reg, board)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["failed"], 0)
            self.assertEqual(len(payload["checks"]), 24)  # 21 + 3 节点工作台

    def _corrupt_and_check(self, mutate, expected_check):
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            mutate(d)
            ledger.write_text(json.dumps(d, ensure_ascii=False))
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            failed = [c["id"] for c in payload["checks"] if not c["ok"]]
            self.assertIn(expected_check, failed, f"注入腐化未被 {expected_check} 抓到：{failed}")

    def test_detects_hand_written_completion(self):
        def mutate(d):
            d["capability_model"]["projects"][0]["modules"][2]["caps"][0]["completion"] = 0.99
        self._corrupt_and_check(mutate, "completion_matches_level")

    def test_detects_broken_history_chain(self):
        def mutate(d):
            d["history"]["events"][-1]["fingerprint_before"] = "bogus"
        self._corrupt_and_check(mutate, "history_chain_consistent")

    def test_detects_tampered_event_state(self):
        def mutate(d):
            ev = d["history"]["events"][-1]
            first = next(iter(ev["state_digest"]))
            ev["state_digest"][first]["l"] = 0
        self._corrupt_and_check(mutate, "history_event_fingerprints")

    def test_detects_lesson_without_action(self):
        def mutate(d):
            d["lessons"]["items"][0]["action"] = ""
        self._corrupt_and_check(mutate, "lessons_valid")

    def test_detects_missing_document(self):
        def mutate(d):
            c = d["capability_model"]["projects"][0]["modules"][0]["caps"][0]
            c["doc_index"]["impl"] = [{"path": "examples/demo-shop/docs/GHOST.md"}]
        self._corrupt_and_check(mutate, "doc_paths_exist")


class TristateTest(unittest.TestCase):
    """v1.3.0：能力未启用（na）绝不能被记成 pass。"""

    @staticmethod
    def _run(root, ledger, reg, board, *extra):
        return subprocess.run(
            [sys.executable, str(VERIFIER), "--root", str(root),
             "--registry", str(reg), "--ledger", str(ledger),
             "--board", str(board), "--json", *extra],
            capture_output=True, text=True)

    def test_missing_projection_is_na_not_pass(self):
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            d.pop("test_results", None)
            write_ledger(ledger.parent, d)
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            row = next(c for c in payload["checks"]
                       if c["id"] == "test_results_binding_valid")
            self.assertEqual(row["status"], "na")
            self.assertFalse(row["ok"])
            self.assertEqual(payload["na"], 1)
            self.assertEqual(payload["passed"], 23)
            self.assertEqual(payload["failed"], 0)
            self.assertFalse(payload["all_active"])

    def test_strict_ignores_na_but_require_active_does_not(self):
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            d.pop("test_results", None)
            write_ledger(ledger.parent, d)
            soft = self._run(root, ledger, reg, board, "--strict")
            self.assertEqual(soft.returncode, 0, soft.stdout + soft.stderr)
            hard = self._run(root, ledger, reg, board,
                             "--strict", "--require-active")
            self.assertEqual(hard.returncode, 1)
            self.assertEqual(json.loads(hard.stdout)["na"], 1)


if __name__ == "__main__":
    unittest.main()
