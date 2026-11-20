"""来源投影契约：只读投影不新增账本字段、来源分组、完成定义派生、可复算。"""
MODULE_ID = "routing"
import copy
import json
import unittest
from pathlib import Path

from _base import ROOT
import provenance_view as pv

REAL_TARGET = ROOT


def fixture_ledger() -> dict:
    return {
        "entries": [{
            "id": "D-001", "date": "2026-11-20", "status": "proposed",
            "supersedes": None, "title": "T", "category": "能力建设",
            "scope": "M", "decision": "D", "rationale": "R",
            "evidence": ["path"], "confidence": "high",
        }],
        "work_items": [{
            "id": "W-BIND-X", "kind": "issue", "scope": "X", "status": "open",
            "severity": "high", "source": "derived",
            "derived_from": {"code": "X", "binding_status": "unbound"},
            "close_condition": {"kind": "capability_verified"},
            "refs": [], "owner": "", "owner_note": "note", "detail": "detail",
        }],
        "capability_model": {"next_queue": [{
            "code": "X", "target_level": "L4",
            "missing_evidence": ["契约(L1)", "测试记录(L4)"],
        }]},
    }


class ProjectionTest(unittest.TestCase):
    def test_no_mutation_of_ledger(self):
        ledger = fixture_ledger()
        snapshot = copy.deepcopy(ledger)
        pv.project(ledger)
        self.assertEqual(ledger, snapshot, "投影不得修改账本入参")

    def test_no_new_fields_in_ledger(self):
        # 核心纪律：P2 不往账本写 origin / definition_of_done 等新字段。
        ledger = fixture_ledger()
        pv.project(ledger)
        self.assertNotIn("origin", ledger["work_items"][0])
        self.assertNotIn("definition_of_done", ledger["capability_model"]["next_queue"][0])

    def test_issue_provenance_groups(self):
        out = pv.project(fixture_ledger(), "issue")
        iss = out["issues"][0]
        ai = iss["ai_inferred"]["fields"]
        human = iss["human_confirmed"]["fields"]
        self.assertIn("source", ai)
        self.assertIn("derived_from", ai)
        self.assertIn("close_condition", ai)
        self.assertNotIn("owner", ai)
        self.assertIn("owner", human)
        self.assertIn("owner_note", human)
        self.assertIn("detail", human)
        self.assertNotIn("derived_from", human)

    def test_labels_present(self):
        out = pv.project(fixture_ledger(), "issue")
        iss = out["issues"][0]
        self.assertIn("[AI推断]", iss["ai_inferred"]["label"])
        self.assertIn("[人确认]", iss["human_confirmed"]["label"])
        self.assertIn("勿手改", iss["ai_inferred"]["label"])

    def test_decision_provenance_groups(self):
        out = pv.project(fixture_ledger(), "decision")
        dec = out["decisions"][0]
        self.assertIn("status", dec["ai_inferred"]["fields"])
        self.assertIn("supersedes", dec["ai_inferred"]["fields"])
        self.assertIn("decision", dec["human_confirmed"]["fields"])
        self.assertIn("evidence", dec["human_confirmed"]["fields"])
        self.assertNotIn("decision", dec["ai_inferred"]["fields"])

    def test_definition_of_done_derived(self):
        out = pv.project(fixture_ledger(), "task")
        dod = out["tasks"][0]
        self.assertEqual(dod["code"], "X")
        self.assertEqual(dod["target_level"], "L4")
        self.assertEqual(dod["criteria"], ["契约(L1)", "测试记录(L4)"])
        self.assertIn("verified⟺bound", dod["satisfied_when"])
        self.assertIn("非账本字段", dod["provenance"])

    def test_kind_filter(self):
        ledger = fixture_ledger()
        self.assertIn("issues", pv.project(ledger, "issue"))
        self.assertNotIn("decisions", pv.project(ledger, "issue"))
        self.assertIn("tasks", pv.project(ledger, "task"))
        self.assertNotIn("issues", pv.project(ledger, "task"))

    def test_deterministic_bytes(self):
        a = json.dumps(pv.project(fixture_ledger()), ensure_ascii=False, sort_keys=True)
        b = json.dumps(pv.project(fixture_ledger()), ensure_ascii=False, sort_keys=True)
        self.assertEqual(a, b)

    def test_real_ledger_projects(self):
        ledger = pv.load_ledger(REAL_TARGET)
        out = pv.project(ledger)
        self.assertGreaterEqual(out["summary"].find("issues="), 0)
        self.assertTrue(all("ai_inferred" in x for x in out.get("issues", [])))
        self.assertTrue(all("criteria" in x for x in out.get("tasks", [])))


class CliTest(unittest.TestCase):
    def test_bad_ledger_path(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            # 直接调 main，捕获返回值；空目录无账本应返回 1。
            rc = pv.main(["--target", td, "--json"])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
