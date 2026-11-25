"""schema 登记本体：id 唯一、translates_to 可解析（无孤儿）、负向证明。

登记处是两仓结构化契约的唯一登记点（governance/onto/schemas.json）。
校验复用 spec_check 的 ontology_integrity 判据——不另造第二套校验器。
"""
from __future__ import annotations
MODULE_ID = "meta"

import json
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import spec_check as sc  # noqa: E402

REGISTRY = ROOT / "governance" / "onto" / "schemas.json"

CFG = {"schema": "spec-check/1",
       "ontology": {"files": ["governance/onto/*.json"], "ref_fields": ["translates_to"]}}


def make_registry(tmp: Path, data: dict) -> Path:
    target = tmp / "repo"
    (target / "governance" / "onto").mkdir(parents=True)
    (target / "governance" / "onto" / "schemas.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target


class SchemaRegistryTest(unittest.TestCase):

    def test_registry_valid_zero_hits(self):
        m = sc.check_ontology(ROOT, CFG)
        self.assertTrue(m["applicable"])
        self.assertEqual(m["hits"], 0, f"detail={m.get('detail')}")
        self.assertEqual(m["ids_declared"], 13)

    def test_all_declared_schemas_are_real(self):
        """登记处列出的每个 schema 串必须在其声明文件中真实出现，防登记漂移。"""
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for e in reg["schemas"]:
            rel = e.get("file")
            if not rel or e["id"] == "schema.schema-registry":
                continue  # external_file 不在本仓；登记格式自身免自证
            expected = f"{e['name']}/{e['version']}"
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(expected, text, f"{e['id']} 登记为 {expected} 但 {rel} 中无此串")

    def test_bad_translates_to_ref_hits(self):
        reg = {"schema": "schema-registry/1", "schemas": [
            {"id": "schema.a", "name": "a", "version": "1",
             "translates_to": ["schema.ghost"]}]}
        with tempfile.TemporaryDirectory() as td:
            t = make_registry(Path(td), reg)
            m = sc.check_ontology(t, CFG)
            self.assertEqual(m["hits"], 1)
            self.assertEqual(m["detail"][0]["reason"], "unresolved_ref")

    def test_duplicate_schema_id_hits(self):
        reg = {"schema": "schema-registry/1", "schemas": [
            {"id": "schema.a", "name": "a", "version": "1"},
            {"id": "schema.a", "name": "a2", "version": "1"}]}
        with tempfile.TemporaryDirectory() as td:
            t = make_registry(Path(td), reg)
            m = sc.check_ontology(t, CFG)
            reasons = {x["reason"] for x in m["detail"]}
            self.assertIn("duplicate_id", reasons)


if __name__ == "__main__":
    unittest.main()
