"""目标编排契约：方向锁、预算单调、终态纪律、人批准调整、循环 fail-closed。"""
MODULE_ID = "routing"
import json
import tempfile
import unittest
from pathlib import Path

from _base import ROOT
import goal_ledger as gl
import agent_gateway as gw
import goal_loop
import route_expert as route

CRIT = [{"id": "c1", "metric": "queue_empty", "target": "next_queue", "op": "eq"}]


def _base_ledger() -> dict:
    return {
        "ledger_version": "1.0",
        "capability_model": {"projects": [], "next_queue": []},
        "goals": {"schema": gl.GOALS_SCHEMA, "items": []},
        "access": {"schema": "access/1", "revision": 0,
                   "agents": [], "leases": [], "audit": []},
    }


class GoalObjectTest(unittest.TestCase):
    def test_create_and_direction_lock(self):
        led = _base_ledger()
        g = gl.create_goal(led, goal_id="G-A1", description="目标A",
                           success_criteria=CRIT, max_loops=3,
                           authorized_by="张三", approved_by="李四")
        self.assertEqual(g["status"], "active")
        self.assertEqual(g["current_loop"], 0)
        self.assertTrue(gl.check_direction(g))
        self.assertEqual(g["direction_lock"], gl.canonical_lock("目标A", CRIT))

    def test_create_rejects_self_approval_and_bad_input(self):
        led = _base_ledger()
        for kw in (dict(goal_id="bad", authorized_by="a", approved_by="b"),
                   dict(goal_id="G-A1", authorized_by="", approved_by="b"),
                   dict(goal_id="G-A1", authorized_by="a", approved_by="")):
            with self.assertRaises(ValueError):
                gl.create_goal(led, description="x", success_criteria=CRIT,
                               max_loops=2, **kw)
        with self.assertRaises(ValueError):
            gl.create_goal(led, goal_id="G-A1", description="x",
                           success_criteria=[], max_loops=2,
                           authorized_by="a", approved_by="b")
        with self.assertRaises(ValueError):
            gl.create_goal(led, goal_id="G-A1", description="x",
                           success_criteria=CRIT, max_loops=0,
                           authorized_by="a", approved_by="b")

    def test_budget_monotonic_and_over_budget_denied(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        gl.advance_goal(led, "G-A1", actor="bot")
        gl.advance_goal(led, "G-A1", actor="bot")
        self.assertEqual(gl.find_goal(led, "G-A1")["current_loop"], 2)
        with self.assertRaises(ValueError):
            gl.advance_goal(led, "G-A1", actor="bot")

    def test_direction_tamper_blocks_advance(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="原目标",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        g = gl.find_goal(led, "G-A1")
        g["description"] = "被专家篡改"
        self.assertFalse(gl.check_direction(g))
        with self.assertRaises(ValueError):
            gl.advance_goal(led, "G-A1", actor="bot")

    def test_terminal_states_are_final(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        gl.achieve_goal(led, "G-A1", actor="bot")
        with self.assertRaises(ValueError):
            gl.advance_goal(led, "G-A1", actor="bot")
        with self.assertRaises(ValueError):
            gl.deactivate_goal(led, "G-A1", actor="bot", reason="x")

    def test_pause_resume(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        gl.pause_goal(led, "G-A1", actor="bot", reason="等批准")
        self.assertEqual(gl.find_goal(led, "G-A1")["status"], "paused")
        with self.assertRaises(ValueError):
            gl.advance_goal(led, "G-A1", actor="bot")
        gl.resume_goal(led, "G-A1", actor="bot")
        gl.advance_goal(led, "G-A1", actor="bot")
        self.assertEqual(gl.find_goal(led, "G-A1")["current_loop"], 1)


class ApprovalFlowTest(unittest.TestCase):
    def test_propose_does_not_change_goal_then_human_approves(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="原目标",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        old_lock = gl.find_goal(led, "G-A1")["direction_lock"]
        p = gl.propose_change(led, "G-A1", actor="bot",
                              original_goal="原目标", proposed_change="改描述",
                              rationale="理由", impact="影响",
                              proposed_description="新目标", proposed_criteria=CRIT)
        self.assertEqual(gl.find_goal(led, "G-A1")["description"], "原目标")
        self.assertEqual(gl.find_goal(led, "G-A1")["direction_lock"], old_lock)
        self.assertEqual(p["status"], "pending")
        gl.approve_change(led, "G-A1", p["id"], approved_by="人")
        self.assertEqual(gl.find_goal(led, "G-A1")["description"], "新目标")
        self.assertNotEqual(gl.find_goal(led, "G-A1")["direction_lock"], old_lock)
        self.assertTrue(gl.check_direction(gl.find_goal(led, "G-A1")))

    def test_reject_keeps_goal(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="原目标",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        p = gl.propose_change(led, "G-A1", actor="bot",
                              original_goal="原目标", proposed_change="x",
                              rationale="y", impact="z",
                              proposed_description="新", proposed_criteria=CRIT)
        gl.reject_change(led, "G-A1", p["id"], approved_by="人", reason="不需要")
        self.assertEqual(gl.find_goal(led, "G-A1")["description"], "原目标")
        self.assertEqual(p["status"], "rejected")

    def test_double_approve_denied(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        p = gl.propose_change(led, "G-A1", actor="bot",
                              original_goal="x", proposed_change="y",
                              rationale="r", impact="i",
                              proposed_description="z", proposed_criteria=CRIT)
        gl.approve_change(led, "G-A1", p["id"], approved_by="人")
        with self.assertRaises(ValueError):
            gl.approve_change(led, "G-A1", p["id"], approved_by="人")


class EvaluateTest(unittest.TestCase):
    def test_queue_empty_metric(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        self.assertTrue(gl.evaluate_criteria(led, gl.find_goal(led, "G-A1"))["all_met"])
        led["capability_model"]["next_queue"] = [{"code": "X"}]
        self.assertFalse(gl.evaluate_criteria(led, gl.find_goal(led, "G-A1"))["all_met"])

    def test_cap_level_metric(self):
        led = _base_ledger()
        led["capability_model"]["projects"] = [{"modules": [
            {"caps": [{"code": "C.1", "level": 4}]}]}]
        crit = [{"id": "c", "metric": "cap_level", "target": "C.1", "op": "gte", "value": 3}]
        gl.create_goal(led, goal_id="G-A1", description="x", success_criteria=crit,
                       max_loops=2, authorized_by="a", approved_by="b")
        self.assertTrue(gl.evaluate_criteria(led, gl.find_goal(led, "G-A1"))["all_met"])


class GatewayDispatchTest(unittest.TestCase):
    def test_dispatch_goal_actions(self):
        led = _base_ledger()
        led, msg = gw.dispatch(led, {
            "action": "goal-create", "agent": "human:a", "goal_id": "G-A1",
            "title": "x", "criteria": CRIT, "max_loops": 2,
            "authorized_by": "a", "approved_by": "a"})
        self.assertIn("创建目标", msg)
        led, msg = gw.dispatch(led, {"action": "goal-advance", "agent": "bot",
                                     "goal_id": "G-A1"})
        self.assertIn("1/2", msg)
        led, msg = gw.dispatch(led, {"action": "goal-deactivate", "agent": "bot",
                                     "goal_id": "G-A1", "reason": "超预算"})
        self.assertEqual(gl.find_goal(led, "G-A1")["status"], "deactivated")

    def test_definitions_include_goal_actions(self):
        errs = gw.check_definitions()
        self.assertEqual(errs, [])
        for a in ("goal-create", "goal-approve", "goal-advance", "goal-deactivate",
                  "goal-propose", "goal-achieve"):
            self.assertIn(a, gw.ACTIONS)
        self.assertIn("goal-orchestrator", gw.ROLE_POLICIES)
        self.assertTrue(gw.ACTIONS["goal-create"]["approval"])
        self.assertTrue(gw.ACTIONS["goal-approve"]["approval"])

    def test_load_json_arg(self):
        self.assertEqual(gw._load_json_arg(""), [])
        self.assertEqual(gw._load_json_arg('[{"id":"c"}]'), [{"id": "c"}])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text('[{"id":"f"}]', encoding="utf-8")
            self.assertEqual(gw._load_json_arg(f"@{p}"), [{"id": "f"}])


class RoutingTest(unittest.TestCase):
    def test_goal_intent_routes_to_orchestrator(self):
        r = route.build(ROOT, "目标循环 自动迭代达成目标", "auto", str(ROOT))
        self.assertEqual(r["route"]["expert"], "goal-orchestrator")
        self.assertIn("goal-orchestrator", r["route"]["handoff"]["chain"])

    def test_card_has_goal_orchestrator(self):
        self.assertIn("goal-orchestrator", route.EXPERT_CARDS)
        card = route.EXPERT_CARDS["goal-orchestrator"]
        self.assertEqual(card["writes"], [])
        self.assertIn("goal-orchestrate", card["skills"])


class CriteriaMetricsTest(unittest.TestCase):
    def test_semver_ordering_not_string_ordering(self):
        self.assertFalse(gl.compare_version("2.9.0", "2.10.0", "gte"))
        self.assertTrue(gl.compare_version("2.13.0", "2.10.0", "gte"))
        self.assertTrue(gl.compare_version("2.13.0", "2.13.0", "eq"))
        self.assertFalse(gl.compare_version("2.13.0", "2.13.0", "ne"))

    def test_unknown_op_is_fail_closed(self):
        self.assertFalse(gl.compare_version("2.13.0", "2.10.0", "bogus"))

    def test_method_version_and_level_progress_evaluation(self):
        crit = [
            {"id": "v", "metric": "method_version", "target": "2.13.0", "op": "gte"},
            {"id": "l", "metric": "level_progress", "target": "M.GOV.TEST.01",
             "baseline": 2, "value": 2, "op": "gte"},
        ]
        self.assertEqual(gl.validate_criteria(crit), [])
        led = {
            "governance_meta": {"method_version": "2.13.0"},
            "capability_model": {"projects": [{"modules": [{"caps": [
                {"code": "M.GOV.TEST.01", "level": 3}]}]}]},
        }
        ev = gl.evaluate_criteria(led, {"success_criteria": crit})
        self.assertEqual(ev["met_count"], 1)
        self.assertTrue(ev["criteria"][0]["met"])
        self.assertFalse(ev["criteria"][1]["met"])
        led["capability_model"]["projects"][0]["modules"][0]["caps"][0]["level"] = 4
        self.assertTrue(gl.evaluate_criteria(led, {"success_criteria": crit})["all_met"])

    def test_new_metric_params_validated(self):
        bad = [{"id": "v", "metric": "method_version", "target": "abc", "op": "gte"}]
        self.assertTrue(gl.validate_criteria(bad))
        bad = [{"id": "l", "metric": "level_progress", "target": "M.A.B.01",
                "op": "gte"}]
        self.assertTrue(gl.validate_criteria(bad))

    def test_unknown_metric_rejected(self):
        bad = [{"id": "x", "metric": "evil", "target": "a", "op": "eq"}]
        self.assertIn("未知 metric", "".join(gl.validate_criteria(bad)))


class StagnationTest(unittest.TestCase):
    def test_fingerprint_tracks_task_level_and_version(self):
        goal = {"success_criteria": [
            {"id": "l", "metric": "level_progress", "target": "M.A.B.01",
             "baseline": 1, "value": 1, "op": "gte"}]}
        led = {"governance_meta": {"method_version": "2.1.2"},
               "capability_model": {"projects": [{"modules": [{"caps": [
                   {"code": "M.A.B.01", "level": 2}]}]}]}}
        task = {"code": "M.A.B.01"}
        fp = goal_loop.progress_fingerprint(led, goal, task)
        self.assertEqual(fp, goal_loop.progress_fingerprint(led, goal, task))
        led["capability_model"]["projects"][0]["modules"][0]["caps"][0]["level"] = 3
        self.assertNotEqual(fp, goal_loop.progress_fingerprint(led, goal, task))
        led["governance_meta"]["method_version"] = "2.13.0"
        self.assertNotEqual(fp, goal_loop.progress_fingerprint(led, goal, task))

    def test_invalid_stall_limit_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            gov = target / "governance"
            gov.mkdir()
            led = _base_ledger()
            gl.create_goal(led, goal_id="G-S1", description="停滞测试",
                           success_criteria=CRIT, max_loops=3,
                           authorized_by="a", approved_by="b")
            (gov / "DECISION_LEDGER.json").write_text(
                json.dumps(led, ensure_ascii=False), encoding="utf-8")
            out = goal_loop.run(target, "G-S1", stall_limit=0)
            self.assertEqual(out["verdict"], "invalid")
            self.assertIn("stall_limit", out["stop_reason"])


class LoopScriptTest(unittest.TestCase):
    def test_gateway_command_has_apply_and_agent(self):
        cmd = goal_loop.gateway_command("goal-advance", "G-A1",
                                        agent="goal-orchestrator", reason="r")
        self.assertIn("--agent goal-orchestrator", cmd)
        self.assertIn("--action goal-advance", cmd)
        self.assertIn("--apply", cmd)

    def test_missing_goal_is_invalid(self):
        out = goal_loop.run(ROOT, "G-NONEXIST")
        self.assertEqual(out["verdict"], "invalid")
        self.assertIn("目标不存在", out["stop_reason"])
        self.assertEqual(out["rounds"], [])


class InvariantTest(unittest.TestCase):
    def _verify(self, ledger):
        # 唯一模块名，避免命中其他测试缓存的同名 verify_ledger 模块。
        import importlib.util
        path = ROOT / "templates" / "verify_ledger.py"
        spec = importlib.util.spec_from_file_location("_goal_verify_ledger", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.verify(ROOT, ledger, None, None)

    def test_no_goals_is_na(self):
        led = _base_ledger()
        led.pop("goals")
        row = next(r for r in self._verify(led) if r["id"] == "goal_loop_valid")
        self.assertEqual(row["status"], "na")

    def test_direction_tamper_fails_invariant(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        gl.find_goal(led, "G-A1")["description"] = "篡改"
        row = next(r for r in self._verify(led) if r["id"] == "goal_loop_valid")
        self.assertEqual(row["status"], "fail")

    def test_over_budget_and_terminal_fails_invariant(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        g = gl.find_goal(led, "G-A1")
        g["current_loop"] = 3  # 越界
        row = next(r for r in self._verify(led) if r["id"] == "goal_loop_valid")
        self.assertEqual(row["status"], "fail")

    def test_illegal_new_metric_fails_invariant(self):
        led = _base_ledger()
        gl.create_goal(led, goal_id="G-A1", description="x",
                       success_criteria=CRIT, max_loops=2,
                       authorized_by="a", approved_by="b")
        # 绕过网关直接篡改账本判据（方向锁一并失效，但判据本身也应被抓）
        g = gl.find_goal(led, "G-A1")
        g["success_criteria"] = [{"id": "v", "metric": "method_version",
                                  "target": "abc", "op": "gte"}]
        row = next(r for r in self._verify(led) if r["id"] == "goal_loop_valid")
        self.assertEqual(row["status"], "fail")
        self.assertIn("method_version.target", row["detail"])


if __name__ == "__main__":
    unittest.main()
