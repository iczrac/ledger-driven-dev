"""校验器自身可信：正向全通过 + 负向注入必须被抓到。"""
MODULE_ID = "core"
import copy
import json
import unittest

from _base import ROOT, demo_copy, load_ledger, run_verify


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


if __name__ == "__main__":
    unittest.main()
