"""文档门禁真实性：存在性口径、义务/覆盖判据、时间三态与可解释计数。"""
MODULE_ID = "meta"
import importlib.util
import json
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


def tiny_project() -> Path:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    (root / "governance").mkdir()
    (root / "docs" / "plans").mkdir(parents=True)
    reg = {"project": {"code": "T", "name": "Tiny", "root": "."}, "modules": []}
    ledger = {
        "ledger_version": "1",
        "purpose": "测试",
        "last_updated": "2026-11-24 00:00 HKT",
        "capability_model": {"projects": [], "next_queue": [], "history": {"events": []}},
        "history": {"events": []},
        "entries": [],
    }
    (root / "governance" / "registry.json").write_text(
        json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    (root / "governance" / "DECISION_LEDGER.json").write_text(
        json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    (root / "docs" / "plans" / "T_PLAN.md").write_text(
        "# 计划：T\n\n真人在写。\n", encoding="utf-8")
    _KEEP.append(td)
    return root


def load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DocGateTruthfulnessTest(unittest.TestCase):
    def test_full_rebuild_check_uses_file_layout_presence(self):
        root = tiny_project()
        proc = run("rebuild_docs.py", "--target", root, "--check", "--json")
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(data["ok"])
        self.assertEqual(data["mismatches"], [])
        self.assertEqual(data["counts"]["not_applicable"], 4)
        self.assertEqual(len(data["not_applicable"]), 4)
        self.assertTrue(all("file_layout" in x["reason"] for x in data["not_applicable"]))
        self.assertEqual(run("file_layout.py", "--check").returncode, 0)

    def test_deleted_on_demand_doc_is_not_applicable_not_missing(self):
        root = tiny_project()
        self.assertEqual(run("rebuild_docs.py", "--target", root, "--force").returncode, 0)
        (root / "docs" / "generated" / "PROJECT_STATE.md").unlink()
        data = json.loads(run("rebuild_docs.py", "--target", root, "--check", "--json").stdout)
        paths = {x["path"] for x in data["not_applicable"]}
        self.assertIn("docs/generated/PROJECT_STATE.md", paths)
        self.assertEqual(data["mismatches"], [])

    def test_hand_edited_derived_doc_is_classified_and_blocks_strict(self):
        root = tiny_project()
        self.assertEqual(run("rebuild_docs.py", "--target", root, "--force").returncode, 0)
        p = root / "docs" / "generated" / "PROJECT_STATE.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n手改\n", encoding="utf-8")
        proc = run("rebuild_docs.py", "--target", root, "--check", "--strict", "--json")
        data = json.loads(proc.stdout)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(data["counts"]["hand_edited"], 1)
        self.assertEqual(data["mismatches"][0]["class"], "hand-edited")

    def test_check_sh_stage_reports_full_check_counts(self):
        proc = subprocess.run(["bash", str(SCRIPTS / "check.sh"), "--only-doc-lifecycle"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("派生漂移=", proc.stdout)
        self.assertIn("已判", proc.stdout)
        self.assertIn("not_applicable=", proc.stdout)
        self.assertNotIn("--doc PROJECT_STATE.md", (SCRIPTS / "check.sh").read_text())
        strict = subprocess.run(["bash", str(SCRIPTS / "check.sh"),
                                 "--only-doc-lifecycle", "--strict"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertNotEqual(strict.returncode, 0, strict.stdout + strict.stderr)

    def test_obligation_and_coverage_checks_have_legacy_contrast(self):
        root = tiny_project()
        self.assertEqual(run("doc_lifecycle.py", "seed", "--target", root,
                             "--approved-by", "tester", "--json").returncode, 0)
        mod = load_script("doc_lifecycle.py")
        legacy = mod.lint(root, contracts=set())
        legacy_statuses = {i["status"] for i in legacy["issues"]}
        self.assertNotIn("obligation_missing", legacy_statuses)
        self.assertNotIn("uncovered", legacy_statuses)
        current = mod.lint(root)
        statuses = {i["status"] for i in current["issues"]}
        self.assertIn("obligation_missing", statuses)
        self.assertIn("uncovered", statuses)
        self.assertEqual(current["metrics"]["coverage"]["ratio"], "0/1")

    def test_complete_doc_does_not_report_new_obligation_or_uncovered(self):
        root = tiny_project()
        run("doc_lifecycle.py", "seed", "--target", root,
            "--approved-by", "tester", "--json")
        p = root / "governance" / "DECISION_LEDGER.json"
        ledger = json.loads(p.read_text())
        meta = ledger["docs"]["registry"]["docs/plans/T_PLAN.md"]
        meta.update({"owner": "human-owner", "role": "plan-owner",
                     "stale_after": "2027-01-01",
                     "covers": {"codes": ["T.CORE.X.01"], "decisions": []}})
        p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
        mod = load_script("doc_lifecycle.py")
        statuses = {i["status"] for i in mod.lint(root)["issues"]}
        self.assertNotIn("obligation_missing", statuses)
        self.assertNotIn("uncovered", statuses)

    def test_gate_metrics_distinguish_n_a_from_zero(self):
        root = tiny_project()
        data = json.loads(run("doc_lifecycle.py", "gate", "--target", root, "--json").stdout)
        self.assertTrue(data["metrics"]["suspect"]["n_a"])
        run("doc_lifecycle.py", "seed", "--target", root, "--approved-by", "tester", "--json")
        data = json.loads(run("doc_lifecycle.py", "gate", "--target", root, "--json").stdout)
        self.assertFalse(data["metrics"]["suspect"]["n_a"])
        self.assertEqual(data["metrics"]["suspect"]["checked"], 1)

    def test_unknown_stale_after_is_visible_and_not_counted_as_stale(self):
        root = tiny_project()
        for name in ("A_PLAN.md", "B_PLAN.md"):
            (root / "docs" / "plans" / name).write_text(f"# 计划：{name}\n", encoding="utf-8")
        run("doc_lifecycle.py", "seed", "--target", root, "--approved-by", "tester", "--json")
        p = root / "governance" / "DECISION_LEDGER.json"
        ledger = json.loads(p.read_text())
        values = ["<!-- 待人工填写 -->", "not-a-date", None]
        for path, value in zip(sorted(ledger["docs"]["registry"]), values):
            ledger["docs"]["registry"][path]["stale_after"] = value
        p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
        data = json.loads(run("doc_lifecycle.py", "check", "--target", root,
                              "--as-of", "2026-11-24", "--json").stdout)
        self.assertEqual(data["metrics"]["stale"]["count"], 0)
        self.assertEqual(data["metrics"]["stale_unknown"]["count"], 3)
        self.assertEqual(sum(1 for i in data["issues"] if i["status"] == "stale_unknown"), 3)

    def test_as_of_controls_expired_fresh_split(self):
        root = tiny_project()
        run("doc_lifecycle.py", "seed", "--target", root, "--approved-by", "tester", "--json")
        p = root / "governance" / "DECISION_LEDGER.json"
        ledger = json.loads(p.read_text())
        path = next(iter(ledger["docs"]["registry"]))
        ledger["docs"]["registry"][path]["stale_after"] = "2026-11-01"
        p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
        expired = json.loads(run("doc_lifecycle.py", "check", "--target", root,
                                 "--as-of", "2026-11-24", "--json").stdout)
        self.assertEqual(expired["metrics"]["stale"]["count"], 1)
        fresh = json.loads(run("doc_lifecycle.py", "check", "--target", root,
                               "--as-of", "2026-10-31", "--json").stdout)
        self.assertEqual(fresh["metrics"]["stale"]["count"], 0)
        self.assertEqual(fresh["metrics"]["stale"]["fresh"], 1)

    def test_pending_decisions_have_one_exact_hard_gate_criterion(self):
        metrics = ("orphan", "uncovered", "obligation_missing", "stale_unknown",
                   "suspect", "stale", "信任告警", "派生漂移")
        files = (
            "skills/ledger-verify/SKILL.md",
            "skills/doc-lifecycle/SKILL.md",
            "docs/08-可信性校验.md",
            "docs/STANDARD.md",
            "RELEASE_CHECKLIST.md",
            "README.md",
        )
        for rel in files:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("连续 10 次 CI", text, rel + " 未写连续 10 次 CI")
            self.assertIn("人工书面批准", text, rel + " 未写人工书面批准")
            missing = [name for name in metrics if name not in text]
            self.assertEqual(missing, [], rel + " 缺少硬门指标：" + ", ".join(missing))

    def test_owner_and_approval_decision_is_recorded_without_bulk_fill(self):
        text = (ROOT / "docs/08-可信性校验.md").read_text(encoding="utf-8")
        for phrase in (
            "owner / role / stale_after 只能由人逐篇批准",
            "禁止批量填充占位值或批量置 current",
            "长期批准人：`iczrac`",
            "user-approved-execution-chain 仅作历史一次性会话授权",
        ):
            self.assertIn(phrase, text)

    def test_derived_document_final_decision_stays_on_demand(self):
        text = (ROOT / "docs/15-文件架构.md").read_text(encoding="utf-8")
        for phrase in (
            "最终去留：`docs/generated/` 五份派生文档全部保持 `presence=on-demand`",
            "PROJECT_STATE.md 不改为 required",
            "不为了让检查通过而提交其余四份",
            "删除后落入 not_applicable",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
