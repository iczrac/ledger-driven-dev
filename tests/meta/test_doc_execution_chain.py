"""文档生命周期执行链：门禁接线 / PROJECT_STATE / registry 播种 / 语义修正。"""
MODULE_ID = "meta"
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

SCRIPTS = ROOT / "scripts"
_KEEP: list[tempfile.TemporaryDirectory] = []


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True)


def tiny_project(seed_docs: bool = False) -> Path:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "governance").mkdir()
    (root / "docs" / "plans").mkdir(parents=True)
    reg = {"project": {"code": "T", "name": "Tiny", "root": "."}, "modules": []}
    ledger = {
        "ledger_version": "1", "purpose": "测试",
        "capability_model": {"projects": [], "next_queue": [], "history": {"events": []}},
        "history": {"events": [{
            "seq": 1, "ts": "2026-01-01T00:00:00Z", "type": "seed",
            "fingerprint_before": None, "fingerprint_after": "abcd1234",
            "changes": {}, "state_digest": {},
        }]},
        "entries": [],
    }
    (root / "governance" / "registry.json").write_text(
        json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    (root / "governance" / "DECISION_LEDGER.json").write_text(
        json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    (root / "docs" / "plans" / "T_PLAN.md").write_text(
        "# 计划：T\n\n真人在写。\n", encoding="utf-8")
    # 保持 TemporaryDirectory 引用，避免 GC 提前删除临时目录。
    _KEEP.append(td)
    return root


class DocExecutionChainTest(unittest.TestCase):
    def test_project_state_is_generated_and_deterministic(self):
        root = tiny_project()
        self.assertEqual(run("rebuild_docs.py", "--target", root, "--force").returncode, 0)
        p = root / "docs" / "generated" / "PROJECT_STATE.md"
        self.assertTrue(p.exists(), "PROJECT_STATE.md 未生成")
        a = p.read_bytes()
        self.assertEqual(run("rebuild_docs.py", "--target", root, "--force").returncode, 0)
        self.assertEqual(a, p.read_bytes(), "连续两次生成必须逐字节相同")
        text = p.read_text(encoding="utf-8")
        for section in ("## 能力清单与等级/证据分层", "## 待复核与过期文档",
                        "## next_queue", "## 最近变更"):
            self.assertIn(section, text)

    def test_project_state_check_catches_hand_edit_and_empty_ledger(self):
        root = tiny_project()
        run("rebuild_docs.py", "--target", root, "--force")
        p = root / "docs" / "generated" / "PROJECT_STATE.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n手改一行\n", encoding="utf-8")
        proc = run("rebuild_docs.py", "--target", root, "--check", "--json")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("PROJECT_STATE.md", proc.stdout + proc.stderr)

    def test_project_state_empty_docs_registry_is_fail_closed_hint(self):
        root = tiny_project()
        proc = run("rebuild_docs.py", "--target", root, "--force", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = (root / "docs" / "generated" / "PROJECT_STATE.md").read_text(encoding="utf-8")
        self.assertIn("尚未播种", text)

    def test_gate_reports_orphan_with_file_and_stays_warn(self):
        root = tiny_project()
        proc = run("doc_lifecycle.py", "gate", "--target", root, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = json.loads(proc.stdout)
        self.assertEqual(d["counts"]["orphan"], 1)
        self.assertTrue(any("T_PLAN.md" in i["path"] for i in d["issues"]))
        self.assertEqual(d["status"], "warn")

    def test_gate_strict_fails_on_same_orphan(self):
        root = tiny_project()
        proc = run("doc_lifecycle.py", "gate", "--target", root, "--strict", "--json")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("T_PLAN.md", proc.stdout)

    def test_seed_is_deterministic_and_registers_all_docs_as_draft(self):
        root = tiny_project()
        first = run("doc_lifecycle.py", "seed", "--target", root,
                    "--approved-by", "user-approved-test", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        d = json.loads(first.stdout)
        self.assertEqual(d["status"], "seeded")
        self.assertEqual(d["draft"], 1)
        led = json.loads((root / "governance" / "DECISION_LEDGER.json").read_text())
        entries = led["docs"]["registry"]
        self.assertEqual(set(entries), {"docs/plans/T_PLAN.md"})
        self.assertEqual(entries["docs/plans/T_PLAN.md"]["status"], "draft")
        self.assertFalse(entries["docs/plans/T_PLAN.md"]["verified"])
        self.assertEqual(len(led["history"]["events"]), 2)
        second = run("doc_lifecycle.py", "seed", "--target", root,
                     "--approved-by", "user-approved-test", "--json")
        self.assertEqual(json.loads(second.stdout)["status"], "noop")
        led2 = json.loads((root / "governance" / "DECISION_LEDGER.json").read_text())
        self.assertEqual(led, led2, "播种幂等：第二次不得追加事件或改写登记")

    def test_seed_classifies_generated_as_derived_and_plan_as_plan(self):
        root = tiny_project()
        run("rebuild_docs.py", "--target", root, "--force")
        proc = run("doc_lifecycle.py", "seed", "--target", root,
                   "--approved-by", "user-approved-test", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        led = json.loads((root / "governance" / "DECISION_LEDGER.json").read_text())
        reg = led["docs"]["registry"]
        self.assertEqual(reg["docs/plans/T_PLAN.md"]["kind"], "plan")
        self.assertEqual(reg["docs/generated/PROJECT_STATE.md"]["kind"], "derived")
        self.assertTrue(all(v["status"] == "draft" for v in reg.values()))

    def test_hand_edit_marks_suspect_without_new_orphan(self):
        root = tiny_project()
        run("doc_lifecycle.py", "seed", "--target", root,
            "--approved-by", "user-approved-test", "--json")
        p = root / "docs" / "plans" / "T_PLAN.md"
        p.write_text(p.read_text(encoding="utf-8") + "手改\n", encoding="utf-8")
        proc = run("doc_lifecycle.py", "check", "--target", root, "--json")
        d = json.loads(proc.stdout)
        self.assertTrue(any(i["status"] == "suspect" for i in d["issues"]))
        self.assertEqual(sum(1 for i in d["issues"] if i["status"] == "orphan"), 0)

    def test_current_without_signature_and_source_hash_is_rejected(self):
        root = tiny_project()
        run("doc_lifecycle.py", "seed", "--target", root,
            "--approved-by", "user-approved-test", "--json")
        proc = run("doc_lifecycle.py", "approve", "--target", root,
                   "--doc", "docs/plans/T_PLAN.md", "--status", "current", "--json")
        self.assertNotEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "error")
        self.assertIn("签名", data["reason"])

    def test_current_with_signature_and_recomputable_hash_is_allowed(self):
        root = tiny_project()
        run("doc_lifecycle.py", "seed", "--target", root,
            "--approved-by", "user-approved-test", "--json")
        proc = run("doc_lifecycle.py", "approve", "--target", root,
                   "--doc", "docs/plans/T_PLAN.md", "--status", "current",
                   "--signed-by", "human-owner", "--reason", "人工复核通过", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        led = json.loads((root / "governance" / "DECISION_LEDGER.json").read_text())
        self.assertEqual(led["docs"]["registry"]["docs/plans/T_PLAN.md"]["status"], "current")
        self.assertTrue(led["docs"]["registry"]["docs/plans/T_PLAN.md"]["verified"])

    def test_no_target_does_not_count_as_in_progress(self):
        root = tiny_project()
        reg = json.loads((root / "governance" / "registry.json").read_text())
        reg["modules"] = [{"code": "CORE", "name": "核心", "src": ["src"], "caps": [
            {"code": "T.CORE.X.01", "name": "已存在", "domain": "X",
             "impl": ["src/x.py"], "tests": ["tests/test_x.py"]}]}]
        (root / "governance" / "registry.json").write_text(json.dumps(reg, ensure_ascii=False))
        led = json.loads((root / "governance" / "DECISION_LEDGER.json").read_text())
        led["capability_model"]["projects"] = [{"code": "T", "modules": [{
            "code": "T.CORE", "name": "核心", "caps": [
                {"code": "T.CORE.X.01", "name": "已存在", "level": 2,
                 "evidence_tier": "declared"}]}]}]
        (root / "governance" / "DECISION_LEDGER.json").write_text(
            json.dumps(led, ensure_ascii=False))
        proc = run("compare_graphs.py", "--target", root, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = json.loads(proc.stdout)
        row = next(r for r in d["comparison"] if r["code"] == "T.CORE.X.01")
        self.assertEqual(row["status"], "no_target")
        self.assertEqual(d["summary"].get("no_target"), 1)
        self.assertEqual(d["summary"].get("in_progress", 0), 0)

    def test_registry_declaration_produces_planned_only(self):
        root = tiny_project()
        reg = json.loads((root / "governance" / "registry.json").read_text())
        reg["modules"] = [{"code": "CORE", "name": "核心", "src": ["src"], "caps": [
            {"code": "T.CORE.Y.01", "name": "仅声明未实现", "domain": "Y",
             "committed": True, "target_level": "L3", "depends_on": [],
             "impl": [], "tests": []}]}]
        (root / "governance" / "registry.json").write_text(json.dumps(reg, ensure_ascii=False))
        proc = run("compare_graphs.py", "--target", root, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = json.loads(proc.stdout)
        row = next(r for r in d["comparison"] if r["code"] == "T.CORE.Y.01")
        self.assertEqual(row["status"], "planned_only")
        self.assertGreaterEqual(d["summary"]["planned_only"], 1)


if __name__ == "__main__":
    unittest.main()
