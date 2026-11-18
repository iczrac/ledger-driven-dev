"""反向回流专项：只读基线 / 数据驱动脱敏 / 四产物闭环 / 先失败后通过。"""
from __future__ import annotations
MODULE_ID = "meta"

import argparse
import hashlib
import json
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

sys.path.insert(0, str(ROOT / "scripts"))
from ledger_feedback import (check_rows, collect, cmd_export, cmd_triage,  # noqa: E402
                             read_lines, redact, write_lines)


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def run_export(target: Path, **kw) -> dict:
    args = argparse.Namespace(target=str(target), out=None, phase="manual", note=[],
                              terms=None, no_probe=False, apply=False,
                              approved_by=None, json=True)
    for k, v in kw.items():
        setattr(args, k, v)
    return cmd_export(args)


class ExportTest(unittest.TestCase):

    def test_read_only_and_idempotent(self):
        with demo_copy() as (tmp, _ledger, _registry, _board):
            target = tmp / "examples" / "demo-shop"
            before = tree_hash(target)
            a = collect(target, [], True, [], "manual")
            b = collect(target, [], True, [], "manual")
            self.assertEqual(tree_hash(target), before, "export 不得写目标项目")
            self.assertEqual(a["source_ref"], b["source_ref"])
            self.assertEqual(a["observations"], b["observations"])
            self.assertGreater(len(a["observations"]), 0)
            self.assertTrue(all(o["obs_id"].startswith("OBS-") for o in a["observations"]))
            self.assertEqual(len({o["obs_id"] for o in a["observations"]}),
                             len(a["observations"]), "观察 id 必须唯一")

    def test_write_requires_human_approval(self):
        with demo_copy() as (tmp, *_):
            target = tmp / "examples" / "demo-shop"
            out = tmp / "obs.jsonl"
            dry = run_export(target, out=str(out))
            self.assertEqual(dry["mode"], "dry-run")
            self.assertFalse(out.exists())
            dry2 = run_export(target, out=str(out), apply=True)
            self.assertEqual(dry2["mode"], "dry-run", "只有 --apply 没有批准人仍拒绝")
            self.assertFalse(out.exists())
            applied = run_export(target, out=str(out), apply=True, approved_by="张三")
            self.assertEqual(applied["mode"], "apply")
            self.assertTrue(out.exists())
            self.assertEqual(len(read_lines(out)), applied["count"])

    def test_redact_is_data_driven_not_hardcoded(self):
        self.assertIn("PROJ", redact("SECRETCODE 的账本", ["SECRETCODE"], []))
        self.assertNotIn("SECRETCODE", redact("SECRETCODE 的账本", ["SECRETCODE"], []))
        self.assertIn("<abs>", redact("/Users/someone/project/a.json", [], []))
        self.assertIn("<email>", redact("a.b@example.com", [], []))
        self.assertIn("<secret>", redact("ghp_abcdefghijklmnop", [], []))
        self.assertEqual("DB", redact("INTERNALDB", [], [("INTERNALDB", "DB")]))
        with demo_copy() as (tmp, *_):
            target = tmp / "examples" / "demo-shop"
            obs = collect(target, ["/Users/someone/secret.log 出问题"], False, [], "manual")
            joined = json.dumps(obs["observations"], ensure_ascii=False)
            self.assertNotIn("/Users/", joined)
            self.assertNotIn("someone", joined)

    def test_version_gap_and_legacy_verifier_are_observations(self):
        with demo_copy() as (tmp, ledger, *_):
            d = json.loads(ledger.read_text(encoding="utf-8"))
            d["governance_meta"] = {"method_version": "0.0.1"}
            ledger.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            target = tmp / "examples" / "demo-shop"
            obs = collect(target, [], True, [], "manual")
            text = " ".join(o["symptom"] for o in obs["observations"])
            self.assertIn("落后于权威源", text)
            axes = {o["affected_axis"] for o in obs["observations"]}
            self.assertIn("method_version", axes)


class ClosureTest(unittest.TestCase):

    def _rows(self, tmp: Path) -> tuple[Path, list[dict]]:
        out = tmp / "obs.jsonl"
        with demo_copy() as (base, *_):
            target = base / "examples" / "demo-shop"
            run_export(target, out=str(out), apply=True, approved_by="张三")
        return out, read_lines(out)

    def test_closed_without_disposition_fails_then_passes(self):
        """闭环的核心：先失败，补齐四产物后才通过。"""
        with demo_copy() as (tmp, *_):
            out, rows = self._rows(tmp)
            rows[0]["status"] = "closed"
            self.assertFalse(check_rows(rows)["ok"], "关闭但无处置必须通过校验（假绿灯）")
            rows[0]["disposition"] = "regression"
            self.assertFalse(check_rows(rows)["ok"], "缺产物引用必须失败")
            rows[0]["artifact_ref"] = "scripts/ledger_feedback.py"
            self.assertFalse(check_rows(rows)["ok"], "缺理由必须失败")
            rows[0]["reason"] = "已由回归测试覆盖"
            result = check_rows(rows)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["feedback_closed"], 1)
            write_lines(out, rows)
            self.assertEqual(check_rows(read_lines(out))["feedback_closed"], 1)

    def test_artifact_ref_must_exist(self):
        with demo_copy() as (tmp, *_):
            _out, rows = self._rows(tmp)
            rows[0].update({"status": "closed", "disposition": "invariant",
                            "artifact_ref": "scripts/does_not_exist.py",
                            "reason": "占位"})
            errors = check_rows(rows)["errors"]
            self.assertTrue(any("产物引用不存在" in e for e in errors))

    def test_fingerprint_blocks_manual_edit(self):
        with demo_copy() as (tmp, *_):
            _out, rows = self._rows(tmp)
            rows[0]["symptom"] = "手改过的症状"
            self.assertTrue(any("指纹不匹配" in e for e in check_rows(rows)["errors"]))

    def test_triage_requires_artifact_for_four_products(self):
        with demo_copy() as (tmp, *_):
            out, rows = self._rows(tmp)
            oid = rows[0]["obs_id"]
            args = argparse.Namespace(file=str(out), obs_id=oid,
                                      disposition="regression", artifact_ref=None,
                                      reason="说明", apply=True, approved_by="张三",
                                      json=True)
            with self.assertRaises(ValueError):
                cmd_triage(args)
            args.artifact_ref = "scripts/ledger_feedback.py"
            result = cmd_triage(args)
            self.assertEqual(result["mode"], "apply")
            self.assertEqual(result["check"]["feedback_closed"], 1)
            self.assertTrue(result["check"]["ok"])

    def test_wontfix_needs_reason_but_no_artifact(self):
        with demo_copy() as (tmp, *_):
            out, rows = self._rows(tmp)
            oid = rows[0]["obs_id"]
            args = argparse.Namespace(file=str(out), obs_id=oid,
                                      disposition="wontfix", artifact_ref=None,
                                      reason="超出方法论范围", apply=True,
                                      approved_by="张三", json=True)
            result = cmd_triage(args)
            self.assertTrue(result["check"]["ok"])
            self.assertEqual(result["check"]["feedback_closed"], 0)


if __name__ == "__main__":
    unittest.main()
