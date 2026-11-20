"""本体投影专项：可复算 / 三类漂移 / 第七轴 / 先失败后通过。"""
from __future__ import annotations
MODULE_ID = "meta"

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

sys.path.insert(0, str(ROOT / "scripts"))
from ledger_feedback import check_rows  # noqa: E402
from ontology import (OUT_JSON, OUT_MD, build, check, emit_md,  # noqa: E402
                      expected_digest, observations_for, source_refs,
                      target_violations)


def inject(ledger_path: Path, mutate) -> Path:
    d = json.loads(ledger_path.read_text(encoding="utf-8"))
    mutate(d)
    ledger_path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return ledger_path.parent.parent


class OntologyTest(unittest.TestCase):

    def test_build_is_deterministic(self):
        a, b = build(ROOT), build(ROOT)
        self.assertEqual(a, b)
        self.assertEqual(a["ontology_digest"], expected_digest(ROOT))
        self.assertEqual(len(a["ontology_digest"]), 64)

    def test_generated_projection_is_read_only_and_synced(self):
        onto = build(ROOT)
        stored = json.loads((ROOT / OUT_JSON).read_text(encoding="utf-8"))
        self.assertEqual(stored, onto)
        self.assertEqual((ROOT / OUT_MD).read_text(encoding="utf-8"), emit_md(onto))
        self.assertTrue(check(ROOT)["ok"])

    def test_value_domains_match_real_code_enums(self):
        onto = build(ROOT)
        self.assertEqual(onto["drift"], [])
        self.assertEqual(onto["summary"]["drift_count"], 0)
        self.assertEqual(onto["summary"]["value_domains"], 18)
        for d in onto["value_domains"]:
            if d["observed_ref"]:
                self.assertEqual(d["observed_values"], d["values"], d["id"])
        self.assertEqual(len(onto["invariant_ids"]), 30)

    def test_polyseme_is_disambiguated_not_unified(self):
        onto = build(ROOT)
        polys = [x for x in onto["ubiquitous_language"] if x["polyseme"]]
        self.assertEqual(sorted(x["term"] for x in polys), ["kind", "severity", "status"])
        for x in polys:
            self.assertTrue(x["qualified_form"].startswith("<Type>."))
        for d in onto["value_domains"]:
            self.assertIn(".", d["id"])

    def test_no_orphan_source_refs_and_relations(self):
        onto = build(ROOT)
        for ref in source_refs(ROOT):
            self.assertFalse(Path(ref["path"]).is_absolute())
            self.assertTrue((ROOT / ref["path"]).is_file())
        for rel in onto["relations"]:
            self.assertTrue(rel["derivation"])
            src = rel["source_ref"].split("#")[0]
            self.assertTrue((ROOT / src).is_file(), src)

    def test_check_catches_illegal_status_and_recovers(self):
        with demo_copy() as (tmp, ledger_path, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            inject(ledger_path, lambda d: d["entries"][0].update(status="rogue-status"))
            bad = check(ROOT, proj)
            self.assertFalse(bad["ok"])
            self.assertIn("undeclared_value",
                          [v["kind"] for v in bad["target"]["violations"]])
            # 修复后必须重新通过：先失败后通过，而不是永远报警。
            inject(ledger_path, lambda d: d["entries"][0].update(status="decided"))
            self.assertTrue(check(ROOT, proj)["ok"])

    def test_check_catches_cardinality_contradiction(self):
        with demo_copy() as (tmp, ledger_path, _reg, _board):
            proj = tmp / "examples" / "demo-shop"

            def duplicate(d):
                first = d["capability_model"]["projects"][0]
                d["capability_model"]["projects"] = [first, json.loads(json.dumps(first))]

            inject(ledger_path, duplicate)
            bad = check(ROOT, proj)
            self.assertFalse(bad["ok"])
            kinds = [v["kind"] for v in bad["target"]["violations"]]
            self.assertIn("cardinality_contradiction", kinds)
            self.assertIn("本体基数违例", " ".join(bad["errors"]))

    def test_check_catches_polyseme_and_undeclared_entity(self):
        with demo_copy() as (tmp, ledger_path, _reg, _board):
            proj = tmp / "examples" / "demo-shop"

            def mutate(d):
                d["status"] = "bare"
                d["rogue_top"] = {"x": 1}

            inject(ledger_path, mutate)
            kinds = [v["kind"] for v in check(ROOT, proj)["target"]["violations"]]
            self.assertIn("polyseme_violation", kinds)
            self.assertIn("undeclared_entity", kinds)
            # 裸 status 只被 polyseme 命名一次，不重复计入未声明实体。
            self.assertEqual(kinds.count("undeclared_entity"), 1)

    def test_diff_emits_valid_ontology_observations(self):
        with demo_copy() as (tmp, ledger_path, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            inject(ledger_path, lambda d: d["entries"][0].update(status="rogue-status"))
            tv = target_violations(ROOT, proj, build(ROOT))
            rows = observations_for(tv)
            self.assertTrue(rows)
            self.assertTrue(all(o["affected_axis"] == "ontology" for o in rows))
            self.assertTrue(check_rows(rows)["ok"])
            self.assertEqual(observations_for(tv), rows)

    def test_unupgraded_project_reports_binding_as_na(self):
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            result = check(ROOT, proj)
            self.assertTrue(result["ok"])
            self.assertEqual(result["target"]["binding"], "na")

    def test_upgrade_binds_seventh_axis(self):
        with demo_copy() as (tmp, ledger_path, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            cmd = [sys.executable, str(ROOT / "scripts" / "upgrade.py"),
                   "--target", str(proj), "apply", "--approved-by", "gate-bot"]
            self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).returncode, 0)
            d = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(d["governance_meta"]["ontology_digest"], expected_digest(ROOT))
            self.assertEqual(check(ROOT, proj)["target"]["binding"], "pass")

    def test_write_requires_human_approval(self):
        cmd = [sys.executable, str(ROOT / "scripts" / "ontology.py"),
               "build", "--apply", "--json"]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 2)
        self.assertIn("approved-by", r.stderr)


if __name__ == "__main__":
    unittest.main()
