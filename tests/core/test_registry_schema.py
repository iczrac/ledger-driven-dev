"""v2.0.1 registry schema/2 容器契约红灯测试。

覆盖四个锚点：registry/2 · dual_read · stable_code · single_codec。
S2 阶段本文件应失败：权威 codec 尚不存在，trace_common 仍有裸拼码。
"""
from __future__ import annotations
MODULE_ID = "core"

import importlib.util
import re
import unittest
from pathlib import Path

from _base import ROOT

CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")
CODEC_PATH = ROOT / "templates" / "registry_codec.py"


def _codec():
    spec = importlib.util.spec_from_file_location("_registry_codec", CODEC_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("无法加载 registry_codec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _legacy() -> dict:
    return {
        "project": {"code": "PROJ", "root": ".", "governance_gate": True},
        "modules": [{
            "code": "DATA",
            "name": "数据",
            "src": ["src/data"],
            "caps": [
                {"name": "数据就绪", "domain": "READY", "code": "PROJ.DATA.READY.01",
                 "impl": ["src/data/ready.py"], "hints": ["ready"]},
                {"name": "数据质量", "domain": "QUALITY",
                 "impl": ["src/data/quality.py"], "hints": ["quality"]},
            ],
        }],
    }


def _modern() -> dict:
    return {
        "schema": "registry/2",
        "projects": [{
            "code": "PROJ", "name": "项目", "root": ".", "governance_gate": True,
            "modules": [{
                "code": "DATA",
                "name": "数据",
                "src": ["src/data"],
                "caps": [
                    {"name": "数据就绪", "domain": "READY", "code": "PROJ.DATA.READY.01",
                     "impl": ["src/data/ready.py"], "hints": ["ready"]},
                    {"name": "数据质量", "domain": "QUALITY",
                     "impl": ["src/data/quality.py"], "hints": ["quality"]},
                ],
            }],
        }],
    }


class RegistrySchemaTest(unittest.TestCase):
    def test_schema_name_is_registry_2(self):
        codec = _codec()
        self.assertEqual(codec.SCHEMA, "registry/2")

    def test_dual_read_produces_identical_caps(self):
        codec = _codec()
        old = codec.iter_caps(_legacy())
        new = codec.iter_caps(_modern())
        self.assertEqual(old, new)
        self.assertEqual([c["code"] for c in new],
                         ["PROJ.DATA.READY.01", "PROJ.DATA.QUALITY.02"])
        self.assertTrue(all(CODE_RE.match(c["code"]) for c in new))

    def test_normalize_projects_exposes_project_config(self):
        codec = _codec()
        old_projects = codec.normalize_projects(_legacy())
        new_projects = codec.normalize_projects(_modern())
        self.assertEqual(len(old_projects), 1)
        self.assertEqual(old_projects, new_projects)
        self.assertEqual(old_projects[0]["code"], "PROJ")
        self.assertEqual(len(old_projects[0]["modules"]), 1)

    def test_stable_code_keeps_explicit_identity(self):
        codec = _codec()
        reg = _modern()
        reg["projects"][0]["modules"][0]["caps"][0]["code"] = "PROJ.DATA.ALPHA.07"
        codes = [c["code"] for c in codec.iter_caps(reg)]
        self.assertEqual(codes[0], "PROJ.DATA.ALPHA.07")
        self.assertTrue(CODE_RE.match(codes[0]))


class SingleCodecTest(unittest.TestCase):
    def test_generator_consumes_shared_codec(self):
        text = (ROOT / "templates" / "build_capability_model.py").read_text(encoding="utf-8")
        self.assertIn("registry_codec", text)
        self.assertNotIn('f"{code}.{mcode}.{domain}', text)

    def test_verify_ledger_consumes_shared_codec(self):
        text = (ROOT / "templates" / "verify_ledger.py").read_text(encoding="utf-8")
        self.assertIn("registry_codec", text)

    def test_trace_common_has_no_bare_five_segment_code(self):
        text = (ROOT / "scripts" / "trace_common.py").read_text(encoding="utf-8")
        self.assertIn("registry_codec", text)
        self.assertNotIn('f"{code}.{mcode}.{domain}', text)


if __name__ == "__main__":
    unittest.main()
