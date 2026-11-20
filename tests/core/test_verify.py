"""校验器自身可信：正向全通过 + 负向注入必须被抓到。"""
MODULE_ID = "core"
import copy
import json
import subprocess
import sys
import unittest

from _base import ROOT, VERIFIER, demo_copy, load_ledger, run_verify
from asset_bundle import install  # v2.1.2：资产对账负向证明
from ledger_io import write_ledger


class VerifyTest(unittest.TestCase):
    def test_clean_ledger_passes_all_checks(self):
        with demo_copy() as (root, ledger, reg, board):
            result = run_verify(root, ledger, reg, board)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["failed"], 0)
            self.assertEqual(len(payload["checks"]), 29)  # 27 + 分析层 + D3 投影

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

    def test_detects_verified_without_bound_binding(self):
        """v2.2.0：verified 却把 binding_status 篡成非 bound → 第 7 条必须抓住。

        这是「声明权=伪造权」的负向证明：即便 tier_detail/tier 都还是
        verified，只要绑定依据不成立，账本就是伪造的绿灯。
        """
        def mutate(d):
            for p in d["capability_model"]["projects"]:
                for m in p["modules"]:
                    for c in m["caps"]:
                        if c.get("evidence_tier") == "verified":
                            c["binding_status"] = "unbound"
                            return
        self._corrupt_and_check(mutate, "verified_tier_traceable")

    def test_detects_verified_with_missing_binding_field(self):
        """旧账本（无 binding_status 字段）不得凭空挂 verified。"""
        def mutate(d):
            for p in d["capability_model"]["projects"]:
                for m in p["modules"]:
                    for c in m["caps"]:
                        if c.get("evidence_tier") == "verified":
                            c.pop("binding_status", None)
                            return
        self._corrupt_and_check(mutate, "verified_tier_traceable")

    def test_detects_forged_analytics_health(self):
        """v2.11.0 #28：分数手改成越界值必须被抓到，健康度不能靠声明。"""
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            a = d["capability_model"].get("analytics")
            if not isinstance(a, dict):
                self.skipTest("demo 账本尚未生成 analytics（数据层未实现）")
            a["health"]["dimensions"]["test_pass_rate"]["score"] = 999
            ledger.write_text(json.dumps(d, ensure_ascii=False))
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            failed = [c["id"] for c in payload["checks"] if not c["ok"]]
            self.assertIn("analytics_maturity_valid", failed)

    def test_detects_forged_d3_lineage(self):
        """v2.12.0 #29：追溯状态节点手改到与当前能力不符必须被抓到。"""
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            a = d["capability_model"].get("analytics") or {}
            lineage = a.get("lineage")
            if not isinstance(lineage, dict) or not lineage.get("trees"):
                self.skipTest("demo 账本尚未生成 lineage（数据层未实现）")
            tree = next(iter(lineage["trees"].values()))
            for node in tree.get("children") or []:
                if node.get("kind") == "state":
                    node["level"] = 99
                    break
            ledger.write_text(json.dumps(d, ensure_ascii=False))
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            failed = [c["id"] for c in payload["checks"] if not c["ok"]]
            self.assertIn("analytics_d3_projection_valid", failed)

    def test_detects_non_bound_cap_without_derived_issue(self):
        """v2.3.0 #27：非 bound 能力却删掉派生 issue → 必须 fail。

        这是 issue 闭环的反伪造：不能靠删 issue 让红灯「消失」。
        """
        def mutate(d):
            # demo 的 DEMO.API.QUERY.01 是 no_tests（非 bound）
            for p in d["capability_model"]["projects"]:
                for m in p["modules"]:
                    for c in m["caps"]:
                        if c.get("binding_status") in ("unbound", "no_impl", "via1", "no_tests"):
                            c["binding_status"] = "unbound"
                            d["work_items"] = [
                                w for w in d.get("work_items", [])
                                if w.get("source") != "derived"]
                            return
        self._corrupt_and_check(mutate, "binding_issues_derived")

    def test_detects_satisfied_derived_issue_still_open(self):
        """v2.3.0 #27：能力已 bound 但派生 issue 仍 open → 账本说谎，fail。"""
        def mutate(d):
            d["work_items"].append({
                "id": "W-BIND-DEMO-CORE-ORDER-01", "kind": "issue",
                "scope": "DEMO.CORE.ORDER.01", "status": "open", "severity": "high",
                "title": "伪造的未关闭项", "detail": "", "owner": "", "refs": [],
                "source": "derived",
                "derived_from": {"code": "DEMO.CORE.ORDER.01",
                                 "binding_status": "bound"},
                "close_condition": {"kind": "capability_verified",
                                    "capability": "DEMO.CORE.ORDER.01"},
            })
        self._corrupt_and_check(mutate, "binding_issues_derived")

    def test_detects_tampered_event_state(self):
        def mutate(d):
            ev = d["history"]["events"][-1]
            first = next(iter(ev["state_digest"]))
            ev["state_digest"][first]["l"] = 0
        self._corrupt_and_check(mutate, "history_event_fingerprints")

    def test_detects_open_item_with_satisfied_close_condition(self):
        """工作项已完成却仍 open：结构合法但业务说谎，必须被第 22 条抓住。"""
        def mutate(d):
            d["work_items"][0]["status"] = "open"
            d["work_items"][0]["close_condition"] = {
                "kind": "file_exists",
                "path": "examples/demo-shop/governance/registry.json"}
        self._corrupt_and_check(mutate, "work_items_valid")

    def test_open_item_with_unmet_condition_still_passes(self):
        """条件未满足的 open 是诚实的，不能被误判。"""
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            d["work_items"][0]["status"] = "open"
            d["work_items"][0]["close_condition"] = {
                "kind": "file_exists",
                "path": "examples/demo-shop/governance/not-there.json"}
            write_ledger(ledger.parent, d)
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            self.assertEqual(payload["failed"], 0, payload["checks"])

    def test_detects_lesson_without_action(self):
        def mutate(d):
            d["lessons"]["items"][0]["action"] = ""
        self._corrupt_and_check(mutate, "lessons_valid")

    def test_detects_missing_document(self):
        def mutate(d):
            c = d["capability_model"]["projects"][0]["modules"][0]["caps"][0]
            c["doc_index"]["impl"] = [{"path": "examples/demo-shop/docs/GHOST.md"}]
        self._corrupt_and_check(mutate, "doc_paths_exist")

    def test_detects_unowned_open_work_item(self):
        """未完结工作没有 owner 也没有说明：专家层只剩装饰，必须抓到。"""
        def mutate(d):
            for x in d["work_items"]:
                x.pop("owner", None)
        self._corrupt_and_check(mutate, "work_items_owned")

    def test_owner_note_satisfies_ownership_rule(self):
        """写不出负责人时，owner_note 说明缺口是诚实的，不得误判。"""
        with demo_copy() as (root, ledger, reg, board):
            d = json.loads(ledger.read_text())
            for x in d["work_items"]:
                x.pop("owner", None)
                x["owner_note"] = "等用户指派负责专家（AI 不凭空指派）"
            write_ledger(ledger.parent, d)
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            row = next(c for c in payload["checks"] if c["id"] == "work_items_owned")
            self.assertTrue(row["ok"], row)

    def test_detects_tampered_installed_asset(self):
        """安装副本被改一个字节：三方对账（副本↔清单↔账本）必须红。"""
        with demo_copy() as (root, ledger, reg, board):
            target = board.parent.parent
            install(target, approved_by="gate-bot", apply=True, bind_ledger=True)
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            row = next(c for c in payload["checks"]
                       if c["id"] == "installed_assets_binding")
            self.assertTrue(row["ok"], row)  # 安装后必须先绿
            victim = next(target.glob(".workbuddy/skills/*/SKILL.md"))
            victim.write_text(victim.read_text(encoding="utf-8") + "\n# 改动\n",
                              encoding="utf-8")
            payload = json.loads(run_verify(root, ledger, reg, board).stdout)
            row = next(c for c in payload["checks"]
                       if c["id"] == "installed_assets_binding")
            self.assertFalse(row["ok"], row)
            self.assertIn("sha256 与清单不符", row["detail"], row)


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
            self.assertEqual(payload["na"], 2)  # test_results + 资产未安装
            self.assertEqual(payload["passed"], 27)  # 29 总检查 - 2 na
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
            self.assertEqual(json.loads(hard.stdout)["na"], 2)  # 投影 + 资产未安装


if __name__ == "__main__":
    unittest.main()
