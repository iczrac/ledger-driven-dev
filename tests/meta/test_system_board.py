#!/usr/bin/env python3
"""系统级看板生成器的契约测试：幂等、账本投影、兼容锚、趋势、手改检测。"""
MODULE_ID = "meta"
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_system_board as bsb  # noqa: E402


def ledger_payload(code, title, caps, history=None):
    return {
        "title": title,
        "ledger_version": "1.0.0",
        "last_updated": "2026-11-25 12:00 HKT",
        "history": {"events": history or []},
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
        (self.root / "alpha" / "version.txt").write_text("1.2.0", encoding="utf-8")
        self.anchor = {"repo": "../alpha", "min_version": "1.1.0",
                       "version_source": {"file": "version.txt", "regex": "([0-9.]+)"},
                       "note": "测试锚"}
        self.write_spec("beta", [self.anchor])

    def write_spec(self, project, anchors):
        (self.root / project / "spec_check.json").write_text(
            json.dumps({"compat": {"anchors": anchors}}, ensure_ascii=False), encoding="utf-8")

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
        self.assertEqual(data["meta"]["schema"], "system-board-data/3")

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

    def test_compat_projection_and_below_anchor(self):
        c = bsb.build_data(self.root)["compat"]
        self.assertEqual(c["summary"], {"total": 1, "ok": 1, "blocked": 0})
        a = c["anchors"][0]
        self.assertEqual((a["consumer"], a["provider_dir"], a["found_version"], a["status"]),
                         ("beta", "alpha", "1.2.0", "ok"))
        self.assertEqual(c["impact"], [{"provider": "alpha", "consumers": ["beta"]}])
        self.write_spec("beta", [{**self.anchor, "min_version": "1.3.0"}])
        c2 = bsb.build_data(self.root)["compat"]
        self.assertEqual(c2["anchors"][0]["status"], "below_anchor")
        self.assertEqual(c2["summary"]["blocked"], 1)

    def test_compat_version_source_is_cwd_independent(self):
        want = bsb.build_data(self.root)["compat"]
        cwd = os.getcwd()
        try:
            os.chdir(self.root)
            got = bsb.build_data(".")["compat"]
        finally:
            os.chdir(cwd)
        self.assertEqual(got, want)
        self.assertEqual(got["anchors"][0]["status"], "ok")

    def test_history_trend_from_state_digest(self):
        events = [
            {"seq": 1, "ts": "2026-11-24 10:00 HKT", "type": "genesis",
             "changes": {"added": ["A.01"]},
             "state_digest": {"A.01": {"l": 2, "c": 0.4, "t": "declared"}}},
            {"seq": 2, "ts": "2026-11-25 12:00 HKT", "type": "change",
             "changes": {"level_transitions": ["A.01"], "evidence_changes": ["A.01"]},
             "state_digest": {"A.01": {"l": 3, "c": 0.6, "t": "verified"}}},
        ]
        write_project(self.root, "gamma", ledger_payload(
            "GAMMA", "Gamma 项目", [("01", "甲", "verified")], history=events))
        p = [x for x in bsb.discover(self.root) if x["dir"] == "gamma"][0]
        h = p["history"]
        self.assertEqual(h["events"], 2)
        self.assertEqual([s["verified"] for s in h["series"]], [0, 1])
        self.assertEqual(h["series"][1]["avg_level"], 3.0)
        self.assertEqual(h["series"][1]["level_transitions"], 1)
        # as_of 取系统内最新账本更新时间 2026-11-25 12:00 HKT，最后事件同刻 => 0 小时
        self.assertEqual(h["stale_hours"], 0.0)
        self.assertEqual(h["stale_status"], "fresh")

    def test_template_has_three_personas_and_new_views(self):
        tpl = bsb.template_text(ROOT)
        for token in ('id="persona"', 'data-v="compat"', 'data-v="timeline"',
                      "PERSONA_HINT", "renderNovice", "renderCompat", "renderTimeline",
                      'id="drawer"', "data-drill", "renderDrill"):
            self.assertIn(token, tpl)

    def test_project_ledger_detail_projection(self):
        path = self.root / "alpha" / "governance" / "DECISION_LEDGER.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["entries"] = [{"id": "D-TEST", "date": "2026-11-25", "title": "测试决策",
                               "status": "done", "decision": "记录一条决策"}]
        payload["work_items"] = [{"id": "W-TEST", "status": "open", "severity": "med",
                                  "title": "测试工作项", "scope": "ALPHA.MOD.01"}]
        payload["capability_model"]["summary"] = {
            "health_overall": 88, "health_dimensions": {"verified_coverage": 50}}
        write_project(self.root, "alpha", payload)
        p = [x for x in bsb.discover(self.root) if x["dir"] == "alpha"][0]
        d = p["detail"]
        self.assertEqual(d["decisions"][0]["id"], "D-TEST")
        self.assertEqual(d["work_items"][0]["id"], "W-TEST")
        self.assertEqual(d["health"]["health_overall"], 88)
        self.assertEqual(d["health"]["health_dimensions"]["verified_coverage"], 50)

    def test_detect_new_dimension_data_tamper(self):
        bsb.build(self.root, ROOT, apply=True, approved_by="test")
        out = self.root / bsb.OUTPUT_REL
        out.write_text(out.read_text(encoding="utf-8").replace(
            '"found_version":"1.2.0"', '"found_version":"9.9.9"', 1), encoding="utf-8")
        result = bsb.check(self.root, ROOT)
        self.assertFalse(result["match"])
        self.assertTrue(any("账本" in r for r in result["reasons"]))

    def test_check_fails_when_output_missing(self):
        result = bsb.check(self.root, ROOT)
        self.assertFalse(result["match"])
        self.assertIn("缺失", result["reasons"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
