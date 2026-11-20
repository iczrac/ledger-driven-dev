"""复述门契约：结构化声明锚定、只读越权、意图竞争、fail-closed 与可复算。"""
MODULE_ID = "routing"
import json
import unittest
from pathlib import Path

from _base import ROOT
from intent_restate import SCHEMA, collect_cap_codes, gate, validate

REAL_TARGET = ROOT


def fixture(**over) -> dict:
    d = {
        "schema": SCHEMA,
        "raw_intent": "帮我把能力 DEMO.API.QUERY.01 的测试记录补齐",
        "restatement": "对 DEMO.API.QUERY.01 补 L4 测试记录，不改账本等级字段。",
        "intents": ["code"],
        "capabilities": ["DEMO.API.QUERY.01"],
        "write_scope": ["docs/test_records/**"],
        "open_questions": [],
    }
    d.update(over)
    return d


REGISTRY = {"modules": [{"code": "API", "caps": []}]}
LEDGER = {"capability_model": {
    "projects": [{"code": "DEMO", "modules": [{"code": "DEMO.API", "caps": [
        {"code": "DEMO.API.QUERY.01"}]}]}],
    "next_queue": [],
}, "work_items": []}


class IntentRestateTest(unittest.TestCase):
    def test_schema_and_happy_path(self):
        r = validate(fixture(), REGISTRY, LEDGER)
        self.assertEqual(r["verdict"], "allow")
        self.assertEqual(len(r["checks"]), 8)
        self.assertTrue(all(c["status"] == "pass" for c in r["checks"]))

    def test_restate_cannot_copy_raw(self):
        r = validate(fixture(restatement="帮我把能力 DEMO.API.QUERY.01 的测试记录补齐"),
                     REGISTRY, LEDGER)
        self.assertEqual(r["verdict"], "need_clarification")
        self.assertIn("restate_nonempty", [c["id"] for c in r["checks"]
                                           if c["status"] != "pass"])

    def test_hallucinated_capability_is_rejected(self):
        r = validate(fixture(capabilities=["DEMO.API.FAKE.99"]), REGISTRY, LEDGER)
        self.assertEqual(r["verdict"], "reject")
        bad = next(c for c in r["checks"] if c["id"] == "cap_anchored")
        self.assertEqual(bad["status"], "reject")

    def test_readonly_intent_cannot_write(self):
        r = validate(fixture(intents=["verify"], write_scope=["src/**"]),
                     REGISTRY, LEDGER)
        self.assertEqual(r["verdict"], "reject")
        bad = next(c for c in r["checks"] if c["id"] == "readonly_no_write")
        self.assertEqual(bad["status"], "reject")

    def test_competing_intents_need_clarification(self):
        r = validate(fixture(intents=["new", "adopt", "code"]), REGISTRY, LEDGER)
        self.assertEqual(r["verdict"], "need_clarification")
        bad = next(c for c in r["checks"] if c["id"] == "intent_unambiguous")
        self.assertEqual(bad["status"], "need_clarification")

    def test_meta_needs_open_questions(self):
        r = validate(fixture(intents=["meta"], capabilities=[], write_scope=["none"]),
                     REGISTRY, LEDGER)
        self.assertEqual(r["verdict"], "need_clarification")
        bad = next(c for c in r["checks"] if c["id"] == "meta_disclosed")
        self.assertEqual(bad["status"], "need_clarification")

    def test_invalid_schema_and_intent(self):
        self.assertEqual(validate(fixture(schema="intent-restate/9"), REGISTRY, LEDGER)["verdict"], "reject")
        self.assertEqual(validate(fixture(intents=["bogus"]), REGISTRY, LEDGER)["verdict"], "reject")

    def test_collect_cap_codes_from_all_sources(self):
        codes = collect_cap_codes(REGISTRY, LEDGER)
        self.assertIn("DEMO.API.QUERY.01", codes)
        ledger2 = json.loads(json.dumps(LEDGER))
        ledger2["capability_model"]["next_queue"] = [{"code": "DEMO.API.QUEUE.02"}]
        ledger2["work_items"] = [{"scope": "DEMO.API.WORK.03"}]
        codes = collect_cap_codes(REGISTRY, ledger2)
        self.assertTrue({"DEMO.API.QUERY.01", "DEMO.API.QUEUE.02", "DEMO.API.WORK.03"} <= codes)

    def test_deterministic(self):
        intro = fixture()
        a = validate(intro, REGISTRY, LEDGER)
        b = validate(intro, REGISTRY, LEDGER)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_gate_fail_closed_on_missing_inputs(self):
        r = gate(ROOT, Path("/nonexistent/intent.json"))
        self.assertEqual(r["verdict"], "reject")
        self.assertEqual(r["checks"][0]["id"], "inputs_exist")

    def test_real_project_anchors_real_capability(self):
        real = fixture(raw_intent="给方法资产清单补测试记录",
                       restatement="对 METHOD.GOV.ASSETS.05 补测试记录。",
                       capabilities=["METHOD.GOV.ASSETS.05"])
        r = gate(REAL_TARGET, self._temp_intent(real))
        self.assertEqual(r["verdict"], "allow")

    @staticmethod
    def _temp_intent(data: dict) -> Path:
        import tempfile
        p = Path(tempfile.mkdtemp()) / "intent.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p


if __name__ == "__main__":
    unittest.main()
