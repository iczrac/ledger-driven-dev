"""方法仓自举闭环守门测试（A→B）。

A：账本必须反映真实开发历史——含治理版本绑定 + v2.4/2.5/2.6 三条发版决策。
B：看板术语视图必须消费本体投影，而非纯硬编码常量。

这两条在 v2.7.0 之前都是红的：账本停在 v2.3.0、无 governance_meta，
看板 GLOSSARY 是模板内写死的 21 条概念解说。
"""
MODULE_ID = "meta"
import json
import re
import sys
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from upgrade import METHOD_VERSION  # noqa: E402

GOV = ROOT / "governance"
LEDGER = GOV / "DECISION_LEDGER.json"
BOARD = GOV / "index.html"
TEMPLATE = ROOT / "templates" / "index.html.template"
ONTO_JSON = ROOT / "docs" / "generated" / "ONTOLOGY.json"


class SelfHostingLedger(unittest.TestCase):
    """A：账本 = 真实开发历史。"""

    def _ledger(self):
        return json.loads(LEDGER.read_text(encoding="utf-8"))

    def test_governance_meta_bound(self):
        d = self._ledger()
        gm = d.get("governance_meta")
        self.assertIsInstance(gm, dict, "方法仓账本缺 governance_meta（未走过 M1-M8）")
        self.assertEqual(gm.get("method_version"), METHOD_VERSION)
        for key in ("method_assets", "board_skeleton", "installed_assets", "ontology_digest"):
            self.assertIn(key, gm, f"governance_meta 缺绑定轴 {key}")

    def test_release_decisions_recorded(self):
        d = self._ledger()
        titles = " | ".join(str(e.get("title", "")) for e in d.get("entries", []))
        for ver in ("2.4.0", "2.5.0", "2.6.0", "2.8.0", "2.9.0", "2.10.0", "2.11.0"):
            self.assertIn(ver, titles, f"账本未记录发版决策 {ver}")

    def test_release_decisions_are_done(self):
        d = self._ledger()
        rel = [e for e in d.get("entries", [])
               if any(v in str(e.get("title", "")) for v in
                      ("2.4.0", "2.5.0", "2.6.0", "2.8.0", "2.9.0", "2.10.0", "2.11.0"))]
        self.assertEqual(len(rel), 7, "应有七条发版决策")
        for e in rel:
            self.assertEqual(e.get("status"), "done", f"{e['id']} 未完成流转")

    def test_board_embed_matches_ledger(self):
        d = self._ledger()
        html = BOARD.read_text(encoding="utf-8")
        embed = json.loads(re.search(r"const EMBED = (\{.*?\});\nlet DATA", html, re.S).group(1))
        self.assertEqual(embed, d, "看板 EMBED 与账本不一致")


class SelfHostingBoardOntology(unittest.TestCase):
    """B：术语视图消费本体投影。"""

    def test_template_has_ontology_terms_marker(self):
        tpl = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("ONTO_TERMS", tpl, "权威模板缺 ONTO_TERMS 注入标记")
        self.assertIn("本体投影词表", tpl, "术语视图缺本体投影词表区")

    def test_board_embeds_ontology_terms(self):
        html = BOARD.read_text(encoding="utf-8")
        m = re.search(r"const ONTO_TERMS = (\[.*?\]);\nlet ONTO_DATA", html, re.S)
        self.assertIsNotNone(m, "看板缺 ONTO_TERMS 内嵌数据")
        terms = json.loads(m.group(1))
        onto = json.loads(ONTO_JSON.read_text(encoding="utf-8"))
        want = {x["term"] for x in onto["ubiquitous_language"]}
        got = {x["term"] for x in terms}
        self.assertEqual(got, want, "看板本体术语与权威投影不一致")


if __name__ == "__main__":
    unittest.main()
