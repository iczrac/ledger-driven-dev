"""节点工作台的负向证明：作用域覆盖、投影绑定、不变量与写入纪律。"""
from __future__ import annotations
MODULE_ID = "views"

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import DEMO, ROOT, demo_copy

sys.path.insert(0, str(ROOT / "scripts"))
from ledger_io import load_ledger, write_ledger  # noqa: E402
from work_panel import (add_item, cap_index, check, close_item,  # noqa: E402
                        detect_adapter, import_report, nodes, sync_tests,
                        normalize_report, test_results_from_report, validate,
                        valid_scopes)

OPT_OUT_POLICY = {"schema": "projection-policy/1", "test_results": "opt-out",
                  "reason": "消费方刻意不投影节点测试结果", "approved_by": "iczrac"}


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
            self.assertEqual(len(payload["checks"]), 32)
            self.assertTrue(any(c["id"] == "test_results_binding_valid"
                                for c in payload["checks"]))

    def test_sync_tests_respects_opt_out_declaration(self):
        """P2：宣告 opt-out 后 sync-tests 早退 noop，无写入就不需要批准。"""
        with demo_copy() as (root, ledger_path, _reg, board_path):
            target, gov = board_path.parent.parent, board_path.parent
            d = load_ledger(gov)
            d.pop("test_results", None)  # 模拟消费方从未投影节点测试结果
            d.setdefault("governance_meta", {})["projection_policy"] = copy.deepcopy(
                OPT_OUT_POLICY)
            write_ledger(gov, d)
            out = sync_tests(target, apply=True)  # 故意不给 approved_by：无写入不应被拒
            self.assertTrue(out["noop"])
            self.assertEqual(out["policy"], "opt-out")
            self.assertEqual(out["cases"], 0)
            after = load_ledger(gov)
            self.assertNotIn("test_results", after)
            self.assertNotEqual(
                (after.get("governance_meta") or {}).get("activation", {}).get("state"),
                "active")

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


class ImportReportTest(unittest.TestCase):
    """v1.3.0：外部 CI 报告可规范化，且不得伪造全绿。"""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        base = Path(self.td.name)
        self.proj = base / "proj"
        (self.proj / "src").mkdir(parents=True)
        (self.proj / "tests").mkdir()
        (self.proj / "src" / "a.py").write_text("x = 1\n")
        (self.proj / "tests" / "test_a.py").write_text("def test_a(): pass\n")
        self.ext = base / "ci"
        self.ext.mkdir()

    def tearDown(self):
        self.td.cleanup()

    def _write(self, name, data):
        p = self.ext / name
        p.write_bytes(data if isinstance(data, bytes) else
                      json.dumps(data, ensure_ascii=False).encode("utf-8"))
        return p

    def test_three_adapters_autodetect(self):
        junit = self._write("j.xml", b'<testsuites><testsuite>'
                                     b'<testcase classname="C" name="ok" time="0.1"/>'
                                     b'<testcase classname="C" name="bad"><failure/></testcase>'
                                     b'</testsuite></testsuites>')
        jest = self._write("jest.json", {"testResults": [{
            "name": "a.test.js", "assertionResults": [
                {"fullName": "a", "status": "passed", "duration": 10},
                {"fullName": "b", "status": "skipped"}]}]})
        ledger = self._write("ledger.json", {
            "schema": "ledger-test-report/1",
            "cases": [{"id": "t1", "file": "tests/test_a.py",
                       "status": "pass", "seconds": 0.1}]})
        for path, kind, n, overall in ((junit, "junit", 2, "fail"),
                                       (jest, "jest", 2, "pass"),
                                       (ledger, "ledger", 1, "pass")):
            r = normalize_report(path.read_bytes(), "auto", self.proj,
                                 ["src", "tests"])
            self.assertEqual(r["source_adapter"], kind)
            self.assertEqual(r["schema"], "ledger-test-report/1")
            self.assertEqual(len(r["cases"]), n)
            self.assertEqual(r["overall"], overall)
            self.assertTrue(r["evidence_binding"]["inputs"])
            self.assertTrue(all(not x["path"].startswith("/")
                                for x in r["evidence_binding"]["inputs"]))

    def test_dry_run_and_human_approval(self):
        src = self._write("ledger.json", {
            "schema": "ledger-test-report/1",
            "cases": [{"id": "t1", "file": "tests/test_a.py",
                       "status": "pass", "seconds": 0.1}]})
        out = self.proj / "governance" / "test_report.json"
        dry = import_report(self.proj, source=str(src), adapter="auto")
        self.assertEqual(dry["mode"], "dry-run")
        self.assertFalse(out.exists())
        with self.assertRaises(ValueError):
            import_report(self.proj, source=str(src), adapter="auto", apply=True)
        done = import_report(self.proj, source=str(src), adapter="auto",
                             approved_by="张三", apply=True)
        self.assertEqual(done["mode"], "apply")
        rep = json.loads(out.read_text())
        self.assertEqual(rep["source_adapter"], "ledger")
        self.assertTrue(rep["evidence_binding"]["inputs"])

    def test_empty_report_never_green(self):
        src = self._write("empty.xml", b"<testsuites></testsuites>")
        r = normalize_report(src.read_bytes(), "junit", self.proj,
                             ["src", "tests"])
        self.assertEqual(r["overall"], "fail")
        self.assertEqual(r["summary"]["total"], 0)
        self.assertTrue(r["load_errors"])


class CloseConditionTest(unittest.TestCase):
    """关闭条件：证据已满足就不许继续挂 open，否则下一个执行者会被指挥重做。"""

    def _with(self, **cond):
        d = copy.deepcopy(synthetic_ledger())
        d["work_items"][0]["close_condition"] = cond
        return d

    def test_verified_capability_blocks_open(self):
        errs = validate(self._with(kind="capability_verified",
                                   capability="DEMO.CORE.ORDER.01"))
        self.assertTrue(any("关闭条件已满足" in e for e in errs), errs)

    def test_declared_capability_allows_open(self):
        self.assertEqual(validate(self._with(
            kind="capability_verified", capability="DEMO.CORE.PRICE.02")), [])

    def test_manual_never_auto_satisfied(self):
        self.assertEqual(validate(self._with(kind="manual")), [])

    def test_unknown_kind_is_rejected(self):
        errs = validate(self._with(kind="whenever"))
        self.assertTrue(any("close_condition.kind" in e for e in errs), errs)

    def test_file_exists_uses_project_root(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            gov = tmp / "governance"
            gov.mkdir()
            (tmp / "artifact.json").write_text("{}")
            d = self._with(kind="file_exists", path="artifact.json")
            self.assertTrue(any("关闭条件已满足" in e for e in validate(d, gov)))
            d2 = self._with(kind="file_exists", path="missing.json")
            self.assertEqual(validate(d2, gov), [])

    def test_close_requires_resolution_when_condition_present(self):
        with demo_copy() as (tmp, ledger_path, _reg, _board):
            target = ledger_path.parent.parent
            gov = ledger_path.parent
            d = load_ledger(gov)
            d.setdefault("work_items", []).append({
                "id": "W-TODO-900", "kind": "todo", "scope": "PROJECT",
                "status": "open", "severity": "low", "title": "待关项",
                "detail": "", "owner": "", "refs": [],
                "close_condition": {"kind": "manual"}})
            write_ledger(gov, d)
            with self.assertRaises(ValueError):
                close_item(target, item_id="W-TODO-900", approved_by="tester", apply=True)
            out = close_item(target, item_id="W-TODO-900", approved_by="tester",
                             resolution="人工确认完成", apply=True)
            self.assertEqual(out["item"]["status"], "done")
            again = load_ledger(gov)
            item = next(x for x in again["work_items"] if x["id"] == "W-TODO-900")
            self.assertEqual(item["resolution"], "人工确认完成")
            self.assertIn("closed_at", item)
            self.assertEqual(check(target)["ok"], True)


if __name__ == "__main__":
    unittest.main()
