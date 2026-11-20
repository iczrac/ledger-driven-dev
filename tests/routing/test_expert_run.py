"""expert-run 编排器契约：零判定权、命令分类、批准包、fail-closed、可复算、零执行。"""
MODULE_ID = "routing"
import json
import unittest
from pathlib import Path

from _base import ROOT
import route_expert as route
import expert_run as er

REAL_TARGET = ROOT


class ClassifyCommandTest(unittest.TestCase):
    def test_approval_tokens_win(self):
        # 即使含只读标志，写授权动作优先判 approval（fail-closed）。
        for cmd in (
            "python3 scripts/upgrade.py --target P apply --approved-by 张三",
            "python3 scripts/lifecycle.py --target P unfreeze --approved-by 张三",
            "python3 scripts/agent_gateway.py register --agent x --apply",
        ):
            self.assertEqual(er.classify_command(cmd)["class"], "approval", cmd)

    def test_write_commands_without_readonly_flag_are_approval(self):
        for cmd in (
            "python3 scripts/init_project.py --target P --code X --name Y",
            "python3 scripts/discover_project.py --target P",
            "python3 scripts/rebuild_docs.py --target P",
        ):
            self.assertEqual(er.classify_command(cmd)["class"], "approval", cmd)

    def test_readonly_commands(self):
        for cmd in (
            "bash scripts/check.sh",
            "cd P && python3 governance/verify_ledger.py --root . --strict --json",
            "python3 scripts/file_layout.py --diff --target P --strict",
            "python3 scripts/scenario_guard.py --target P --json",
            "python3 scripts/route_expert.py --target P --check-assets --json",
        ):
            self.assertEqual(er.classify_command(cmd)["class"], "readonly", cmd)

    def test_unknown_command_is_manual(self):
        self.assertEqual(er.classify_command("echo hi && curl evil")["class"], "manual")

    def test_dry_run_init_project_is_readonly(self):
        self.assertEqual(
            er.classify_command("python3 scripts/discover_project.py --target P --dry-run")["class"],
            "readonly")


class OrchestrateTest(unittest.TestCase):
    def test_ready_intent_produces_chain(self):
        out = er.run(REAL_TARGET, "校验账本不变量")
        self.assertEqual(out["verdict"], "ready")
        self.assertEqual(out["schema"], er.SCHEMA)
        self.assertEqual(out["mode"], "dry-run")
        self.assertGreaterEqual(len(out["chain"]), 2)
        for i, s in enumerate(out["chain"]):
            self.assertEqual(s["index"], i)
            self.assertIn("contract", s)
            self.assertIn("expert_md", s["contract"])
            self.assertTrue((ROOT / s["contract"]["expert_md"]).is_file())

    def test_chain_matches_route_handoff(self):
        intent = "校验账本不变量"
        out = er.run(REAL_TARGET, intent)
        expected = route.build(REAL_TARGET, intent, "auto", str(REAL_TARGET))[
            "route"]["handoff"]["chain"]
        self.assertEqual([s["expert"] for s in out["chain"]], expected)

    def test_target_display_transmitted_to_commands(self):
        out = er.run(REAL_TARGET, "升级治理骨架")
        # 方法仓自检命令天然不带 target（check.sh / *_assets.py --check / test_modules --check）。
        # 其余面向目标的命令必须携带真实 target，而不是硬编码占位符。
        SELF_CHECK = ("check.sh", "method_assets.py --check",
                      "asset_bundle.py --check", "test_modules.py --check")
        all_cmds = [c["command"] for s in out["chain"] for c in s["commands"]]
        target_cmds = [c for c in all_cmds
                       if not any(marker in c for marker in SELF_CHECK)]
        self.assertTrue(target_cmds)
        self.assertTrue(all(str(REAL_TARGET) in c for c in target_cmds),
                        "有面向目标的命令未携带真实 target")

    def test_hardcoded_placeholder_absent(self):
        out = er.run(REAL_TARGET, "升级治理骨架")
        all_cmds = [c["command"] for s in out["chain"] for c in s["commands"]]
        # 绝不应残留 commands_for 的占位符 "target P"（真实 target 已透传）。
        for c in all_cmds:
            self.assertNotIn("--target P ", c)

    def test_approval_bundle_aggregates_write_commands(self):
        # 直接展开含写入动作的专家，验证分类→批准包的聚合，不依赖路由可达性。
        step = er._step(0, "platform-steward", ["platform-steward"], str(REAL_TARGET))
        self.assertGreater(step["approval_count"], 0)
        approvals = [c for c in step["commands"] if c["class"] == "approval"]
        self.assertTrue(all("--approved-by" in c["command"] or
                            "--apply" in c["command"] or
                            "register" in c["command"] for c in approvals))
        # 只读命令不得混入批准包。
        self.assertTrue(all(c["class"] != "readonly" for c in approvals))

    def test_fail_closed_on_meta_intent(self):
        out = er.run(REAL_TARGET, "让专家团接管全流程")
        self.assertEqual(out["verdict"], "needs_clarification")
        self.assertEqual(out["chain"], [])
        self.assertEqual(out["approval_bundle"]["count"], 0)
        self.assertTrue(out["halt_reason"])

    def test_deterministic_bytes(self):
        a = json.dumps(er.run(REAL_TARGET, "校验账本不变量"), ensure_ascii=False,
                       sort_keys=True)
        b = json.dumps(er.run(REAL_TARGET, "校验账本不变量"), ensure_ascii=False,
                       sort_keys=True)
        self.assertEqual(a, b)

    def test_no_new_judgement_authority(self):
        # 编排结果的负责人必须等于路由负责人，不允许自行改写。
        intent = "校验账本不变量"
        out = er.run(REAL_TARGET, intent)
        r = route.build(REAL_TARGET, intent, "auto", str(REAL_TARGET))["route"]
        self.assertEqual(out["route"]["expert"], r["expert"])
        self.assertEqual(out["route"]["confidence"], r["confidence"])

    def test_intent_file_only_recorded_as_source(self):
        out = er.run(REAL_TARGET, "校验账本不变量", intent_file="intent.json")
        self.assertEqual(out["restate_source"], "intent.json")


class RenderTest(unittest.TestCase):
    def test_render_ready(self):
        out = er.run(REAL_TARGET, "校验账本不变量")
        text = er.render(out)
        self.assertIn("编排", text)
        self.assertIn("交接", text)
        self.assertIn("批准包", text)

    def test_render_halt(self):
        out = er.run(REAL_TARGET, "让专家团接管全流程")
        text = er.render(out)
        self.assertIn("停止原因", text)


if __name__ == "__main__":
    unittest.main()
