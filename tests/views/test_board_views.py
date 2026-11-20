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
  querySelectorAll:()=>[],querySelector:()=>null,classList:{remove(){},add(){},contains(){return false;},toggle(){}},
  dataset:{},closest:()=>null};}
global.document={getElementById:id=>_els[id]||(_els[id]=_elem()),
  querySelectorAll:()=>[],querySelector:()=>_elem()};
const _store={};
global.localStorage={getItem:k=>_store[k]||null,setItem:(k,v)=>{_store[k]=String(v);},removeItem:k=>{delete _store[k];}};
global.fetch=()=>Promise.reject(new Error('offline'));
"""


class BoardViewsTest(unittest.TestCase):

    def test_template_has_all_work_views_and_anchors(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        for needle in ('data-v="workbench"', 'data-v="work"', "const PAGE_SIZE=200",
                       "function renderWorkbench(", "function renderWork(",
                       "function workStripHtml(", "function nodeWork(",
                       "function bindWorkLinks(",                        "VIEW_DATA.work_items",
                       "VIEW_DATA.test_results", "workStripHtml(c.code)",
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

    def test_board_ux_contract(self):
        """v2.8.0：体验改进也必须成为可复算契约，不能靠人记得别删。"""
        html = TEMPLATE.read_text(encoding="utf-8")
        for needle in (
            '<nav class="bar" id="nav" aria-label="看板视图">',
            'id="context"', 'aria-live="polite"', 'class="skip-link"',
            'id="qclear"', ",'pending')+", 'data-clear="query"',
            'function renderContext(', 'function setView(',
            "function bindStats(", "function bindContext(",
            '@media (max-width: 760px)', 'prefers-reduced-motion',
            "const VIEW_META=", "window.addEventListener('keydown'",
        ):
            self.assertIn(needle, html, needle)

    def test_board_visual_contract(self):
        """v2.9.0：理念可见、架构与数据流可复算，不能退化成手写装饰图。"""
        html = TEMPLATE.read_text(encoding="utf-8")
        for needle in (
            'data-v="design"', 'data-v="diagram"', 'data-v="flow"',
            'const DESIGN_PRINCIPLES=[', 'function renderDesign(',
            'function renderDiagram(', 'function renderFlow(',
            'function flowData(', 'function bindJumps(',
            'class="navgroup primary"', 'id="navtoggle"',
            '<svg', 'data-jump="\'+esc(jump)+\'"', 'tabindex="0"',
            '账本驱动的实时计数', '数据流 · 实时计数',
        ):
            self.assertIn(needle, html, needle)

    def test_board_workbench_contract(self):
        """v2.10.0：默认落点是工作台，而不是账本列表；工作台必须给结论和入口。"""
        html = TEMPLATE.read_text(encoding="utf-8")
        for needle in (
            "let view='workbench', query='';", 'let DATA_SOURCE=',
            'class="focus-grid"', 'class="trustbar"', 'class="launchpad"',
            'class="diagram-scroll"', '可信度', '下一轮队列', '入口矩阵',
            'DATA_SOURCE', '账本路径', '命中节点将高亮',
        ):
            self.assertIn(needle, html, needle)
        self.assertLess(html.index('data-v="workbench"'),
                        html.index('data-v="all"'),
                        "工作台应排在全部条目之前")
        # 原有 data-v 一个不能少：突破框架不等于拆契约。
        for v in ('all', 'workbench', 'work', 'pending', 'design', 'diagram',
                  'flow', 'timeline', 'modules', 'arch', 'capability',
                  'history', 'lessons', 'glossary'):
            self.assertIn(f'data-v="{v}"', html, v)

    def test_board_analytics_contract(self):
        """v2.11.0：热力图 / 趋势 / 卡片墙 / 证据链 / What-if 都是契约。"""
        html = TEMPLATE.read_text(encoding="utf-8")
        for needle in (
            'data-v="heatmap"', 'data-v="trend"', 'data-v="lineage"', 'data-v="queue"',
            'function renderHeatmap(', 'function renderTrend(',
            'function renderLineage(', 'function renderLineageD3(',
            'function renderQueue(', 'function renderEvidenceChain(',
            'function ensureAnalytics(', 'function recomputeHealth(',
            'function applyWhatIf(', 'function markChanges(',
            'maturity-analytics/1', 'localStorage', 'whatIf',
            'data-tier="', 'data-whatif="', "classList.add('changed')",
            'health-dim', 'class="heat-grid"', 'class="queue-wall"',
        ):
            self.assertIn(needle, html, needle)
        for v in ('workbench', 'heatmap', 'trend', 'lineage', 'queue', 'work',
                  'capability', 'all', 'design', 'diagram', 'flow',
                  'timeline', 'modules', 'arch', 'history', 'lessons', 'glossary', 'pending'):
            self.assertIn(f'data-v="{v}"', html, v)

    def test_local_d3_contract(self):
        """v2.12.0：D3 必须本地、离线、可降级；不允许 CDN 或运行时下载。"""
        html = TEMPLATE.read_text(encoding="utf-8")
        vendor = ROOT / "templates" / "vendor" / "d3.v7.min.js"
        self.assertTrue(vendor.is_file(), "缺少本地 D3 文件")
        self.assertIn('<script src="vendor/d3.v7.min.js"></script>', html)
        self.assertNotIn("https://cdn.jsdelivr.net", html)
        self.assertNotIn("https://d3js.org/d3", html)
        body = vendor.read_text(encoding="utf-8")
        self.assertIn("v7.", body[:120], "D3 版本标记缺失")
        self.assertGreater(len(body), 200_000, "D3 文件疑似截断")
        for needle in ('function hasD3(', 'function renderTrendD3(',
                       'function renderHeatmapD3(', 'function renderLineageD3(',
                       'function deriveLineage(', 'trace-lineage/1'):
            self.assertIn(needle, html, needle)

    def test_work_views_degrade_without_data(self):
        """用最小 DOM stub 在 Node 里真实执行模板 JS，证明空账本不报错。"""
        if not _has_node():
            self.skipTest("node 不可用")
        with tempfile.TemporaryDirectory() as td:
            js = Path(td) / "board.js"
            js.write_text(NODE_HARNESS + script_text() + """
renderWorkbench(document.getElementById('list'));
const a=document.getElementById('list').innerHTML;
if(!a.includes('焦点队列')||!a.includes('下一轮队列')) throw new Error('工作台缺区块');
if(!a.includes('可信度')||!a.includes('入口矩阵')) throw new Error('工作台视角缺可信度/入口');
renderWork(document.getElementById('list'));
const b=document.getElementById('list').innerHTML;
if(!b.includes('TODO / Issue')) throw new Error('工作项缺区块');
workScope='DEMO.CORE.ORDER.01';
const w=nodeWork(workScope);
if(w.health<0||w.health>100) throw new Error('健康度越界');
if(!Array.isArray(w.items)) throw new Error('工作项不是数组');
renderDesign(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('单一事实源')) throw new Error('设计理念缺原则');
renderDiagram(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('<svg')) throw new Error('架构图缺 SVG');
renderFlow(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('数据流 · 实时计数')) throw new Error('数据流缺计数标题');
ensureAnalytics();
renderHeatmap(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('能力成熟度热力图')) throw new Error('热力图缺标题');
renderTrend(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('成熟度趋势')) throw new Error('趋势图缺标题');
renderLineage(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('规划 → 决策 → 证据 → 当前状态')) throw new Error('追溯链缺标题');
renderQueue(document.getElementById('list'));
if(!document.getElementById('list').innerHTML.includes('任务卡片墙')) throw new Error('卡片墙缺标题');
const h=recomputeHealth(VIEW_DATA.capability_model||{},VIEW_DATA);
if(h.overall<0||h.overall>100) throw new Error('模拟健康度越界');
toggleWhatIf();
toggleWhatIfCap('DEMO.API.QUERY.01');
applyWhatIf();
if(!whatIf.active) throw new Error('What-if 未激活');
toggleWhatIf();
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
