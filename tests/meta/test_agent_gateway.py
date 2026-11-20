"""多 Agent 接入网关：默认拒绝、最小权限、CAS、租约、批准门与审计的负向证明。"""
from __future__ import annotations
MODULE_ID = "meta"

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from _base import DEMO, ROOT, run_verify
from ledger_io import (board_synced, current_fingerprint, load_ledger,
                       registry_sha)

sys.path.insert(0, str(ROOT / "scripts"))
from agent_gateway import (ACTIONS, ROLE_POLICIES, check_definitions,  # noqa: E402
                           evaluate, register, request, status)
from upgrade import apply as upgrade_apply  # noqa: E402

GATEWAY = ROOT / "scripts" / "agent_gateway.py"
CODE = "DEMO.API.QUERY.01"


@contextmanager
def governed_copy():
    """升级过的临时项目：access 登记已建立，但没有注册任何 Agent。"""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dst = tmp / "examples" / "demo-shop"
        shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("__pycache__"))
        upgrade_apply(dst, "张三")
        yield tmp, dst


def tree_hash(root: Path) -> dict[str, str]:
    # .ledger-write.lock 是瞬态互斥锁，不属于项目状态，哈希比对时忽略
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
            and p.name != ".ledger-write.lock"}


def ns(**kw) -> argparse.Namespace:
    base = dict(agent="ci-agent", action="claim", code=CODE,
                expect_fingerprint="", expect_registry_sha="", expect_revision=None,
                approved_by="", reason="", title="", rationale="", candidate="",
                insight="", action_text="", superseded_by="", apply=False)
    base.update(kw)
    return argparse.Namespace(**base)


def base_req(target: Path, **kw) -> dict:
    d = load_ledger(target / "governance")
    r = dict(agent="ci-agent", action="claim", code=CODE,
             expect_fingerprint=current_fingerprint(d),
             expect_registry_sha=registry_sha(target / "governance"),
             expect_revision=None, approved_by="", reason="", apply=False)
    r.update(kw)
    return r


class GatewayTest(unittest.TestCase):

    # ---------- 定义 ----------
    def test_definitions_selfcheck(self):
        self.assertEqual(check_definitions(), [])
        self.assertEqual(len(ROLE_POLICIES), 9)  # v2.13.0 + goal-orchestrator
        self.assertIn("platform-steward", ROLE_POLICIES)
        self.assertIn("goal-orchestrator", ROLE_POLICIES)
        for a in ("decide", "lesson-confirm", "freeze", "claim"):
            self.assertEqual(ACTIONS[a]["kind"], "ledger-write")

    # ---------- 默认拒绝 ----------
    def test_default_deny_without_access(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            dst = tmp / "examples" / "demo-shop"
            shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("__pycache__"))
            d = load_ledger(dst / "governance")
            res = evaluate(d, base_req(dst), None, registry_sha(dst / "governance"))
            self.assertEqual(res["decision"], "deny")
            self.assertIn("access_registry", res["denied_by"])
            self.assertIn("agent_identity", res["denied_by"])
            self.assertIn("upgrade.py", " ".join(c["fix"] for c in res["checks"]))

    def test_register_requires_human_and_no_self_approval(self):
        with governed_copy() as (tmp, target):
            d = load_ledger(target / "governance")
            with self.assertRaises(ValueError):
                register(d, "ci-agent", "loop-executor", "")
            with self.assertRaises(ValueError):
                register(d, "ci-agent", "loop-executor", "ci-agent")
            with self.assertRaises(ValueError):
                register(d, "ci-agent", "unknown-role", "张三")
            self.assertEqual(d["access"]["agents"], [])

    def test_register_writes_audit_and_keeps_board_synced(self):
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            item = register(d, "ci-agent", "loop-executor", "张三", ["DEMO.API."])
            from ledger_io import write_ledger
            write_ledger(gov, d)
            d2 = load_ledger(gov)
            self.assertEqual(item["approved_by"], "张三")
            self.assertEqual(d2["access"]["revision"], 1)
            self.assertEqual(len(d2["access"]["audit"]), 1)
            self.assertEqual(d2["access"]["audit"][0]["action"], "register")
            self.assertTrue(board_synced(gov, d2))
            r = run_verify(tmp, gov / "DECISION_LEDGER.json", gov / "registry.json",
                           gov / "index.html")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unregistered_and_unauthorized_denied(self):
        """G1 探针：身份、角色、scopes 三道门互不替代。"""
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三", ["DEMO.API."])
            from ledger_io import write_ledger
            write_ledger(gov, d)
            d = load_ledger(gov)
            digest = registry_sha(gov)
            unknown = evaluate(d, base_req(target, agent="rogue"), None, digest)
            self.assertEqual(unknown["decision"], "deny")
            self.assertIn("agent_identity", unknown["denied_by"])

            wrong_role = evaluate(d, base_req(target, action="archive"), None, digest)
            self.assertIn("role_policy", wrong_role["denied_by"])

            out_scope = evaluate(d, base_req(target, action="code",
                                             code="DEMO.CORE.PRICE.02"), None, digest)
            self.assertIn("scope_policy", out_scope["denied_by"])

    def test_cas_required_and_mismatch(self):
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            d = load_ledger(gov)
            digest = registry_sha(gov)
            no_fp = evaluate(d, base_req(target, expect_fingerprint=""), None, digest)
            self.assertIn("cas_fingerprint", no_fp["denied_by"])
            stale = evaluate(d, base_req(target, expect_fingerprint="deadbeef"), None, digest)
            self.assertIn("cas_fingerprint", stale["denied_by"])

    def test_registry_cas_detects_concurrent_edit(self):
        """F7 探针：手写清单改过即拒绝，但只检测不合并。"""
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            d = load_ledger(gov)
            no_sha = evaluate(d, base_req(target, action="code",
                                          expect_registry_sha=""), None, registry_sha(gov))
            self.assertIn("registry_cas", no_sha["denied_by"])
            stale = evaluate(d, base_req(target, action="code",
                                         expect_registry_sha="0" * 64), None, registry_sha(gov))
            self.assertIn("registry_cas", stale["denied_by"])

    def test_self_approval_and_self_register_denied(self):
        """G3 探针：权限授予者不能是被授权者。"""
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "release-steward", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            d = load_ledger(gov)
            self_approval = evaluate(
                d, base_req(target, action="unfreeze", code="",
                            approved_by="ci-agent"), None, registry_sha(gov))
            self.assertIn("human_approval", self_approval["denied_by"])
            no_approval = evaluate(
                d, base_req(target, action="archive", code=""), None, registry_sha(gov))
            self.assertIn("human_approval", no_approval["denied_by"])

    # ---------- 写入与审计 ----------
    def test_dry_run_does_not_write(self):
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            before = tree_hash(target)
            res = request(target, ns(**base_req(target)))
            self.assertEqual(res["decision"], "allow")
            self.assertFalse(res["applied"])
            self.assertEqual(tree_hash(target), before)

    def test_apply_writes_claim_audit_and_keeps_invariants(self):
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            res = request(target, ns(**{**base_req(target), "apply": True}))
            self.assertEqual(res["decision"], "allow", res)
            self.assertTrue(res["applied"])
            self.assertEqual(res["audit"]["outcome"], "applied")
            d2 = load_ledger(gov)
            self.assertTrue(any(c.get("code") == CODE
                                for c in d2["execution"]["claims"]))
            self.assertEqual(d2["access"]["revision"], 2)  # register + claim
            self.assertTrue(board_synced(gov, d2))
            r = run_verify(tmp, gov / "DECISION_LEDGER.json", gov / "registry.json",
                           gov / "index.html")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_lease_blocks_concurrent_agent(self):
        """G2 探针：同编码租约在 TTL 内只属于先登记的 Agent。"""
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三")
            register(d, "ci-agent-2", "loop-executor", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            first = request(target, ns(**{**base_req(target), "apply": True}))
            self.assertTrue(first["applied"])
            second = request(target, ns(**base_req(target, agent="ci-agent-2")))
            self.assertEqual(second["decision"], "deny")
            self.assertIn("lease_free", second["denied_by"])

    def test_revision_detects_intervening_write(self):
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "loop-executor", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            res = evaluate(load_ledger(gov), base_req(target, expect_revision=99),
                           None, registry_sha(gov))
            self.assertIn("revision", res["denied_by"])

    def test_dispatch_rejects_invalid_lesson_candidate(self):
        """网关调用既有纯函数，不复制业务逻辑：非法候选必须被拒绝且不写盘。"""
        with governed_copy() as (tmp, target):
            gov = target / "governance"
            d = load_ledger(gov)
            register(d, "ci-agent", "ledger-steward", "张三")
            from ledger_io import write_ledger
            write_ledger(gov, d)
            before = tree_hash(target)
            res = request(target, ns(**{**base_req(
                target, action="lesson-confirm", code="", candidate="LC-NOPE",
                title="x", insight="y", action_text="z"), "apply": True}))
            self.assertEqual(res["decision"], "deny")
            self.assertIn("dispatch_rejected", res["denied_by"])
            self.assertEqual(tree_hash(target), before)

    def test_policy_point_boundary_is_declared(self):
        """G4 探针：网关是策略执行点，不冒充 OS 沙箱；编码动作只签许可。"""
        import agent_gateway
        self.assertEqual(ACTIONS["code"]["kind"], "permit-only")
        self.assertIn("不是操作系统沙箱", agent_gateway.__doc__)
        self.assertIn("策略执行点", agent_gateway.__doc__)

    # ---------- CLI ----------
    def test_cli_status_json_is_leak_free(self):
        with governed_copy() as (tmp, target):
            p = subprocess.run([sys.executable, str(GATEWAY), "--target", str(target),
                                "status", "--json"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            d = json.loads(p.stdout)
            self.assertEqual(d["access_schema"], "access/1")
            self.assertTrue(d["registry_sha256"])
            self.assertNotIn("/Users/", p.stdout)
            self.assertNotIn(str(ROOT), p.stdout)

    def test_cli_request_denies_unknown_agent(self):
        with governed_copy() as (tmp, target):
            p = subprocess.run([sys.executable, str(GATEWAY), "--target", str(target),
                                "request", "--agent", "rogue", "--action", "claim",
                                "--code", CODE, "--json"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 1)
            self.assertIn("agent_identity", p.stdout)


if __name__ == "__main__":
    unittest.main()
