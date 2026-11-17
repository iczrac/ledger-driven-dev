"""技能纪律：写决策与写经验的硬约束必须由代码保证，而非靠 Agent 记得。"""
import json
import unittest

from _base import demo_copy, load_ledger
from ledger_decide import decide, next_id as next_decision_id
from ledger_lesson import confirm_lesson, dismiss_lesson, next_id as next_lesson_id


class DecideTest(unittest.TestCase):
    def test_creates_proposed_from_queue(self):
        d = load_ledger()
        e = decide(d, "DEMO.API.QUERY.01", "补齐接口单测", "rank 1 缺证据")
        self.assertEqual(e["id"], "D-004")
        self.assertEqual(e["status"], "proposed")
        self.assertIn("DEMO.API.QUERY.01", e["evidence"])
        self.assertEqual(e["scope"], "DEMO")

    def test_rejects_duplicate_open_decision(self):
        d = load_ledger()
        decide(d, "DEMO.API.QUERY.01", "首次立项", "理由")
        with self.assertRaises(ValueError):
            decide(d, "DEMO.API.QUERY.01", "重复立项", "理由")

    def test_rejects_code_not_in_queue(self):
        with self.assertRaises(ValueError):
            decide(load_ledger(), "DEMO.CORE.PRICE.02", "已达标", "不在队列")

    def test_id_never_reuses(self):
        entries = load_ledger()["entries"]
        self.assertEqual(next_decision_id(entries), "D-004")


class LessonTest(unittest.TestCase):
    def setUp(self):
        self.ledger = load_ledger()
        self.cid = self.ledger["lessons"]["candidates"][0]["id"]

    def test_confirm_requires_insight_and_action(self):
        with self.assertRaises(ValueError):
            confirm_lesson(self.ledger, self.cid, "标题", "有洞察", "")
        self.assertEqual(len(self.ledger["lessons"]["items"]), 1)

    def test_confirm_links_back_to_candidate(self):
        item = confirm_lesson(self.ledger, self.cid, "标题", "为什么", "下次怎么做")
        self.assertEqual(item["id"], "L-002")
        self.assertEqual(item["from_candidate"], self.cid)
        self.assertEqual(item["scope"], {"capabilities": ["DEMO.API.QUERY.01"]})

    def test_dismiss_requires_reason(self):
        with self.assertRaises(ValueError):
            dismiss_lesson(self.ledger, self.cid, "")

    def test_dismiss_marks_candidate(self):
        dismiss_lesson(self.ledger, self.cid, "已排期，非阻塞")
        cand = next(c for c in self.ledger["lessons"]["candidates"] if c["id"] == self.cid)
        self.assertEqual(cand["status"], "dismissed")
        self.assertEqual(cand["dismiss_reason"], "已排期，非阻塞")

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(ValueError):
            confirm_lesson(self.ledger, "LC-NOPE", "标题", "洞察", "行动")

    def test_id_never_reuses(self):
        self.assertEqual(next_lesson_id(self.ledger["lessons"]["items"]), "L-002")


if __name__ == "__main__":
    unittest.main()
