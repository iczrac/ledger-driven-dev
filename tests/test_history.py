"""历史契约：指纹稳定、diff 正确、幂等、链自证、候选识别。"""
import copy
import unittest

from _base import demo_copy, load_ledger, run_generator, state_signature
import build_capability_model as gen
import verify_ledger as ver


class FingerprintTest(unittest.TestCase):
    def test_stable_and_sensitive(self):
        cm = load_ledger()["capability_model"]
        snap = gen.snapshot_state(cm)
        self.assertEqual(gen.fingerprint_state(snap), gen.fingerprint_state(gen.snapshot_state(cm)))
        changed = copy.deepcopy(snap)
        first = next(iter(changed))
        changed[first]["l"] = 1
        self.assertNotEqual(gen.fingerprint_state(snap), gen.fingerprint_state(changed))

    def test_cross_implementation_agrees(self):
        # 生成器和校验器各自独立实现指纹，必须对同一状态得出相同结果
        cm = load_ledger()["capability_model"]
        snap = gen.snapshot_state(cm)
        self.assertEqual(gen.fingerprint_state(snap), ver.fingerprint_state(snap))

    def test_diff_reports_transitions_and_evidence(self):
        before = {"A.X.Y.01": {"l": 2, "c": 0.4, "e": ["a.py"], "d": [], "dec": []}}
        after = {"A.X.Y.01": {"l": 5, "c": 1.0, "e": ["a.py", "b.md"], "d": [], "dec": []},
                 "A.X.Z.01": {"l": 1, "c": 0.2, "e": [], "d": [], "dec": []}}
        d = gen.diff_state(before, after)
        self.assertEqual(d["level_transitions"], [{"code": "A.X.Y.01", "from": "L2", "to": "L5"}])
        self.assertEqual(d["added"], ["A.X.Z.01"])
        self.assertEqual(d["evidence_changes"][0]["added"], ["b.md"])
        self.assertTrue(gen.diff_has_changes(d))
        self.assertFalse(gen.diff_has_changes(gen.diff_state(after, after)))


class HistoryTest(unittest.TestCase):
    def test_event_chain_self_certifies(self):
        events = load_ledger()["history"]["events"]
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual([e["seq"] for e in events], list(range(1, len(events) + 1)))
        self.assertIsNone(events[0]["fingerprint_before"])
        for i, ev in enumerate(events):
            self.assertEqual(gen.fingerprint_state(ev["state_digest"]), ev["fingerprint_after"])
            if i:
                self.assertEqual(ev["fingerprint_before"], events[i - 1]["fingerprint_after"])

    def test_real_transition_recorded(self):
        events = load_ledger()["history"]["events"]
        transitions = [t for e in events for t in e["changes"]["level_transitions"]]
        self.assertIn({"code": "DEMO.CORE.PRICE.02", "from": "L2", "to": "L5"}, transitions)

    def test_candidate_rules_fired(self):
        kinds = {c["kind"] for c in load_ledger()["lessons"]["candidates"]}
        self.assertIn("stagnation", kinds)
        self.assertIn("superseded_decision", kinds)

    def test_repeated_generation_is_idempotent(self):
        with demo_copy() as (root, ledger, reg, board):
            before = state_signature(ledger)
            for _ in range(3):
                result = run_generator(root, ledger, reg, board)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(state_signature(ledger), before)

    def test_new_evidence_appends_one_event(self):
        with demo_copy() as (root, ledger, reg, board):
            before = state_signature(ledger)
            (root / "examples/demo-shop/tests/unit/test_order_api.py").write_text(
                "from src.api.order_api import get_order\n\ndef test_get():\n    assert get_order('o1')['order_id'] == 'o1'\n"
            )
            result = run_generator(root, ledger, reg, board)
            self.assertEqual(result.returncode, 0, result.stderr)
            after = state_signature(ledger)
            self.assertEqual(after[0], before[0] + 1)
            self.assertNotEqual(after[1], before[1])


if __name__ == "__main__":
    unittest.main()
