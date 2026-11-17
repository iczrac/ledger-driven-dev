"""节点工作台的负向证明：作用域覆盖、投影绑定、不变量与写入纪律。"""
from __future__ import annotations
MODULE_ID = "views"

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import DEMO, ROOT, demo_copy

sys.path.insert(0, str(ROOT / "scripts"))
from ledger_io import load_ledger, write_ledger  # noqa: E402
from work_panel import (add_item, cap_index, check, close_item, nodes,  # noqa: E402
                        sync_tests, test_results_from_report, validate,
                        valid_scopes)


def synthetic_ledger() -> dict:
    caps = ["DEMO.CORE.ORDER.01", "DEMO.CORE.PRICE.02", "DEMO.API.QUERY.01"]
    cm = {"projects": [{"code": "DEMO", "modules": [
        {"code": "DEMO.CORE", "caps": [
            {"code": caps[0], "name": "订单", "level": 3, "evidence_tier": "verified",
             "doc_index": {"unit_tests": [{"path": "tests/unit/test_order.py"}]}},
            {"code": caps[1], "name": "定价", "level": 2, "evidence_tier": "declared",
             "doc_index": {"unit_tests": [{"path": "tests/unit/test_pricing.py"}]}},
        ]},
        {"code": "DEMO.API", "caps": [
            {"code": caps[2], "name": "查询", "level": 1, "evidence_tier": "declared",
             "doc_index": {"unit_tests": []}},
        ]},
    ]}], "summary": {"evidence_freshness": "fresh"}}
    return {
        "entries": [{"id": "D-001", "status": "decided"}],
        "capability_model": cm,
        "work_items": [
            {"id": "W-TODO-001", "kind": "todo", "scope": "DEMO.CORE.ORDER.01",
             "status": "open", "severity": "med", "title": "补边界用例",
             "detail": "", "owner": "", "refs": [{"kind": "capability", "value": caps[0]}]},
            {"id": "W-ISSUE-001", "kind": "issue", "scope": "DEMO.CORE",
             "status": "blocked", "severity": "high", "title": "契约缺失",
             "detail": "", "owner": "", "refs": [{"kind": "decision", "value": "D-001"}]},
            {"id": "W-TODO-002", "kind": "todo", "scope": "PROJECT",
             "status": "done", "severity": "low", "title": "已完成项",
             "detail": "", "owner": "", "refs": []},
        ],
        "test_results": {
            "schema": "node-test-results/1", "source": "governance/test_report.json",
            "source_sha256": "", "overall": "fail",
            "summary": {"total": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 0},
            "cases": [
                {"id": "t1", "file": "tests/unit/test_order.py", "status": "pass", "seconds": 0},
                {"id": "t2", "file": "tests/unit/test_pricing.py", "status": "fail", "seconds": 0},
            ],
        },
    }


class WorkPanelTest(unittest.TestCase):

    def test_node_summary_scopes_work_items(self):
        d = synthetic_ledger()
        self.assertEqual(validate(d), [])
        out = nodes(d)
        by = {n["scope"]: n for n in out["nodes"]}
        self.assertEqual(by["DEMO.CORE"]["todo_open"], 1)
        self.assertEqual(by["DEMO.CORE"]["issues_blocked"], 1)
        self.assertEqual(by["DEMO.CORE.ORDER.01"]["todo_open"], 1)
        self.assertEqual(by["DEMO.API.QUERY.01"]["todo_open"], 0)  # done 不计
        self.assertEqual(by["DEMO.CORE"]["tests_total"], 2)
        self.assertEqual(by["DEMO.CORE"]["tests_failed"], 1)
        self.assertEqual(by["PROJECT"]["issues_blocked"], 1)
        self.assertLess(by["DEMO.CORE"]["health"], by["DEMO.API"]["health"])
        self.assertIn("DEMO.CORE", valid_scopes(d))
        self.assertEqual(len(cap_index(d)), 3)

    def test_validation_rejects_bad_scope_and_refs(self):
        d = synthetic_ledger()
        d["work_items"][0]["scope"] = "NOPE.MODULE"
        self.assertTrue(any("scope" in e for e in validate(d)))
        d = synthetic_ledger()
        d["work_items"][0]["refs"] = [{"kind": "decision", "value": "D-999"}]
        self.assertTrue(any("决策" in e for e in validate(d)))
        d = synthetic_ledger()
        d["work_items"][0]["status"] = "invented"
        self.assertTrue(any("status" in e for e in validate(d)))
        d = synthetic_ledger()
        d["test_results"]["cases"][0]["status"] = "green"
        self.assertTrue(any("用例状态" in e for e in validate(d)))

    def test_sync_tests_binding_and_24_invariants(self):
        with demo_copy() as (root, ledger_path, _reg, board_path):
            target = board_path.parent.parent
            gov = board_path.parent
            before = load_ledger(gov)
            d = copy.deepcopy(before)
            d.setdefault("test_results", test_results_from_report(gov))
            d["test_results"]["source_sha256"] = "0" * 64
            write_ledger(gov, d)
            with self.assertRaises(ValueError):
                sync_tests(target, apply=True)
            out = sync_tests(target, approved_by="gate-bot", apply=True)
            self.assertFalse(out["noop"])
            after = load_ledger(gov)
            tr = after["test_results"]
            self.assertEqual(tr["schema"], "node-test-results/1")
            self.assertEqual(tr["source_sha256"],
                             test_results_from_report(gov)["source_sha256"])
            self.assertTrue(check(target)["ok"])
            verifier = gov / "verify_ledger.py"
            p = subprocess.run([sys.executable, str(verifier), "--root", str(root),
                                "--ledger", str(ledger_path), "--registry", str(_reg),
                                "--board", str(board_path), "--json", "--strict"],
                               capture_output=True, text=True)
            payload = json.loads(p.stdout)
            self.assertEqual(payload["failed"], 0, payload["checks"])
            self.assertEqual(len(payload["checks"]), 24)
            self.assertTrue(any(c["id"] == "test_results_binding_valid"
                                for c in payload["checks"]))

    def test_tampered_projection_fails_verifier(self):
        with demo_copy() as (root, ledger_path, _reg, board_path):
            target, gov = board_path.parent.parent, board_path.parent
            sync_tests(target, approved_by="gate-bot", apply=True)
            d = load_ledger(gov)
            d["test_results"]["source_sha256"] = "0" * 64
            write_ledger(gov, d)
            self.assertFalse(check(target)["ok"])
            p = subprocess.run([sys.executable, str(gov / "verify_ledger.py"),
                                "--root", str(root), "--ledger", str(ledger_path),
                                "--registry", str(_reg), "--board", str(board_path),
                                "--json"], capture_output=True, text=True)
            failed = [c["id"] for c in json.loads(p.stdout)["checks"] if not c["ok"]]
            self.assertIn("test_results_binding_valid", failed)

    def test_add_and_close_require_approval_and_are_deterministic(self):
        with demo_copy() as (_tmp, _ledger, _reg, board_path):
            target, gov = board_path.parent.parent, board_path.parent
            d = load_ledger(gov)
            d["work_items"] = []
            d.pop("test_results", None)
            write_ledger(gov, d)
            with self.assertRaises(ValueError):
                add_item(target, kind="todo", scope="PROJECT", title="x", apply=True)
            dry = add_item(target, kind="todo", scope="PROJECT", title="x")
            self.assertEqual(dry["mode"], "dry-run")
            self.assertEqual(dry["item"]["id"], "W-TODO-001")
            a = add_item(target, kind="issue", scope="PROJECT", title="缺陷 A",
                         severity="high", refs=["D-001"],
                         approved_by="gate-bot", apply=True)
            self.assertEqual(a["item"]["id"], "W-ISSUE-001")
            self.assertTrue(check(target)["ok"])
            closed = close_item(target, item_id="W-ISSUE-001",
                                approved_by="gate-bot", apply=True)
            self.assertEqual(closed["item"]["status"], "done")
            self.assertEqual(closed["item"]["closed_by"], "gate-bot")

    def test_work_panel_check_on_demo_is_clean(self):
        r = check(ROOT / "examples" / "demo-shop")
        self.assertTrue(r["ok"], r["errors"])
        self.assertGreater(r["nodes"], 0)


if __name__ == "__main__":
    unittest.main()
