"""看板视图契约：新视图存在、空数据不崩、骨架与预算同步。"""
from __future__ import annotations
MODULE_ID = "views"

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from board_contract import (REQUIRED_IDS, check as board_check,  # noqa: E402
                            template_digest, _layout_facts)
from scale_budget import BUDGETS, report as budget_report

TEMPLATE = ROOT / "templates" / "index.html.template"
SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)


def script_text() -> str:
    return SCRIPT_RE.search(TEMPLATE.read_text(encoding="utf-8")).group(1)


NODE_HARNESS = """
const _els={};
function _elem(){return {innerHTML:'',textContent:'',value:'',onclick:null,oninput:null,
  querySelectorAll:()=>[],querySelector:()=>null,classList:{remove(){},add(){}},
  dataset:{},closest:()=>null};}
global.document={getElementById:id=>_els[id]||(_els[id]=_elem()),
  querySelectorAll:()=>[],querySelector:()=>_elem()};
global.fetch=()=>Promise.reject(new Error('offline'));
"""


class BoardViewsTest(unittest.TestCase):

    def test_template_has_all_work_views_and_anchors(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        for needle in ('data-v="workbench"', 'data-v="work"', "const PAGE_SIZE=200",
                       "function renderWorkbench(", "function renderWork(",
                       "function workStripHtml(", "function nodeWork(",
                       "function bindWorkLinks(", "DATA.work_items",
                       "DATA.test_results", "workStripHtml(c.code)",
                       "workStripHtml(m.code)", "workStripHtml(scope)",
                       'data-v="glossary"', "function renderGlossary(",
                       "const GLOSSARY=[", "const CODING_IDEAS=[",
                       "const IMPL_NOTES=["):
            self.assertIn(needle, html, needle)
        facts = _layout_facts(html)
        self.assertEqual(facts["missing_ids"], [])
        self.assertEqual(facts["tab_count"], html.count('class="tab'))
        self.assertEqual(len(template_digest()), 64)
        for rid in REQUIRED_IDS:
            self.assertIn(f'id="{rid}"', html)

    def test_work_views_degrade_without_data(self):
        """用最小 DOM stub 在 Node 里真实执行模板 JS，证明空账本不报错。"""
        if not _has_node():
            self.skipTest("node 不可用")
        with tempfile.TemporaryDirectory() as td:
            js = Path(td) / "board.js"
            js.write_text(NODE_HARNESS + script_text() + """
renderWorkbench(document.getElementById('list'));
const a=document.getElementById('list').innerHTML;
if(!a.includes('焦点队列')||!a.includes('任务卡')) throw new Error('工作台缺区块');
renderWork(document.getElementById('list'));
const b=document.getElementById('list').innerHTML;
if(!b.includes('TODO / Issue')) throw new Error('工作项缺区块');
workScope='DEMO.CORE.ORDER.01';
const w=nodeWork(workScope);
if(w.health<0||w.health>100) throw new Error('健康度越界');
if(!Array.isArray(w.items)) throw new Error('工作项不是数组');
console.log('OK');
""", encoding="utf-8")
            p = subprocess.run(["node", str(js)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("OK", p.stdout)

    def test_board_contract_and_budget_include_new_views(self):
        r = board_check(ROOT / "examples" / "demo-shop")
        self.assertTrue(r["match"], r["reason"])
        self.assertEqual(r["layout"]["missing_ids"], [])
        ids = [b["id"] for b in BUDGETS]
        self.assertIn("work_items", ids)
        self.assertEqual(len(BUDGETS), 10)
        rep = budget_report(ROOT / "examples" / "demo-shop")
        self.assertIn("work_items", rep["metrics"])
        self.assertGreaterEqual(rep["metrics"]["work_items"], 1)


def _has_node() -> bool:
    try:
        return subprocess.run(["node", "--version"], capture_output=True).returncode == 0
    except (OSError, FileNotFoundError):
        return False


if __name__ == "__main__":
    unittest.main()
