#!/usr/bin/env python3
"""系统级看板生成器的契约测试：幂等、账本投影、手改检测。"""
MODULE_ID = "meta"
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_system_board as bsb  # noqa: E402


def ledger_payload(code, title, caps):
    return {
        "title": title,
        "ledger_version": "1.0.0",
        "last_updated": "2026-11-25 12:00 HKT",
        "capability_model": {
            "projects": [{
                "code": code,
                "name": title,
                "completion": 0.5,
                "modules": [{
                    "code": code + ".MOD",
                    "name": "模块一",
                    "completion": 0.5,
                    "caps": [{"code": code + ".MOD." + c[0], "name": c[1], "level": 3,
                              "level_code": "L3", "completion": 0.6,
                              "evidence_tier": c[2], "next_action": "补证据"}
                             for c in caps],
                }],
            }],
        },
    }


def write_project(root: Path, name: str, payload: dict):
    gov = root / name / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    (gov / "DECISION_LEDGER.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (gov / "index.html").write_text("<html>project board</html>", encoding="utf-8")


class SystemBoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="system-board-")
        self.root = Path(self.tmp)
        write_project(self.root, "alpha", ledger_payload(
            "ALPHA", "Alpha 项目", [("01", "甲", "verified"), ("02", "乙", "declared")]))
        write_project(self.root, "beta", ledger_payload(
            "BETA", "Beta 项目", [("01", "丙", "verified")]))

    def test_discover_from_ledgers(self):
        projects = bsb.discover(self.root)
        self.assertEqual([p["dir"] for p in projects], ["alpha", "beta"])
        self.assertEqual([p["code"] for p in projects], ["ALPHA", "BETA"])
        self.assertEqual(projects[0]["summary"]["capabilities"], 2)
        self.assertEqual(projects[0]["summary"]["verified"], 1)
        self.assertEqual(projects[1]["board"], "../beta/governance/index.html")

    def test_build_is_idempotent_and_check_passes(self):
        res = bsb.build(self.root, ROOT, apply=True, approved_by="test")
        self.assertTrue(res["applied"])
        html = (self.root / bsb.OUTPUT_REL).read_text(encoding="utf-8")
        bsb.build(self.root, ROOT, apply=True, approved_by="test-2")
        self.assertEqual((self.root / bsb.OUTPUT_REL).read_text(encoding="utf-8"), html)
        self.assertTrue(bsb.check(self.root, ROOT)["match"])

    def test_meta_digest_matches_template(self):
        bsb.build(self.root, ROOT, apply=True, approved_by="test")
        data = bsb.embedded_data((self.root / bsb.OUTPUT_REL).read_text(encoding="utf-8"))
        self.assertEqual(data["meta"]["skeleton_digest"],
                         bsb.skeleton_digest(bsb.template_text(ROOT)))
        self.assertEqual(data["meta"]["schema"], "system-board-data/1")

    def test_detect_skeleton_tamper(self):
        bsb.build(self.root, ROOT, apply=True, approved_by="test")
        out = self.root / bsb.OUTPUT_REL
        html = out.read_text(encoding="utf-8").replace("font-size:22px", "font-size:23px", 1)
        out.write_text(html, encoding="utf-8")
        result = bsb.check(self.root, ROOT)
        self.assertFalse(result["match"])
        self.assertTrue(any("骨架" in r for r in result["reasons"]))

    def test_detect_data_tamper(self):
        bsb.build(self.root, ROOT, apply=True, approved_by="test")
        out = self.root / bsb.OUTPUT_REL
        html = out.read_text(encoding="utf-8").replace('"evidence_tier":"verified"',
                                                        '"evidence_tier":"declared"', 1)
        out.write_text(html, encoding="utf-8")
        result = bsb.check(self.root, ROOT)
        self.assertFalse(result["match"])
        self.assertTrue(any("账本" in r for r in result["reasons"]))

    def test_check_fails_when_output_missing(self):
        result = bsb.check(self.root, ROOT)
        self.assertFalse(result["match"])
        self.assertIn("缺失", result["reasons"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
