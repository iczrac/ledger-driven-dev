"""符号级证据绑定 advisory（v2.1.2）：「测试存在」之上再查「调用关系」。

背景：v2.1.0 把证据来源钉死在 registry 声明，但「声明的测试」与「声明的
实现」之间的配对当初是按文件名关键词猜的——词面碰撞（同名 registry、
同名 ledger）会让证据挂错能力，而路径层检查完全看不见。

这组用例钉住 advisory 的判定口径与边界：
1) 直接 import、再导出链、一跳编排层，三种真实耦合都能判 bound；
2) 无调用关系判 unbound，且不改 level / tier——shadow 门禁只晒不否决；
3) impl 为空 / 无测试各归各类，不混进 unbound。
"""
MODULE_ID = "core"

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _base import ROOT  # noqa: F401  确保 sys.path 指向 templates/

_spec = importlib.util.spec_from_file_location(
    "_v212_generator", ROOT / "templates" / "build_capability_model.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


class BindingAdvisoryTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="binding-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _cfg(self, caps):
        return {"project": {
            "code": "APP", "root": ".", "governance_gate": False,
            "contracts_dir": "src/contracts", "unit_test_dir": "tests",
            "test_record_dir": "docs/test_records", "docs_dir": "docs",
            "governance_dir": "governance",
        }, "modules": [
            {"code": "CORE", "name": "核心", "src": ["src/"], "caps": caps},
        ]}

    def _write_impl(self):
        (self.tmp / "src/domain").mkdir(parents=True)
        # 相对导入再导出：__init__ 里的 from .order import … 必须解析到
        # src/domain/order.py（包是 __init__ 所在目录本身，不得多剥一层）。
        (self.tmp / "src/domain/__init__.py").write_text(
            "from .order import place_order\n")
        (self.tmp / "src/domain/order.py").write_text(
            "def place_order(x):\n    return x\n")

    def test_direct_import_is_bound(self):
        self._write_impl()
        (self.tmp / "tests/unit").mkdir(parents=True)
        (self.tmp / "tests/unit/test_order.py").write_text(
            "from src.domain.order import place_order\n\ndef test_p():\n"
            "    assert place_order(1)\n")
        adv = gen.binding_advisory(self.tmp, self._cfg([
            {"name": "下单", "domain": "ORDER", "impl": ["src/domain/order.py"],
             "tests": ["tests/unit/test_order.py"]},
        ]))
        self.assertEqual(adv["rows"][0]["status"], "bound")
        self.assertEqual(adv["rows"][0]["tests_bound"], 1)

    def test_reexport_chain_is_bound(self):
        """``from src.domain import X`` 沿 __init__ 再导出链必须解析到定义文件。

        只按模块路径匹配会把它误判为「无关系」——这是 v2.1.2 前探针犯过的
        错（汇总导出遮住了真实耦合），本用例防止回退。
        """
        self._write_impl()
        (self.tmp / "tests/unit").mkdir(parents=True)
        (self.tmp / "tests/unit/test_api.py").write_text(
            "from src.domain import place_order\n\ndef test_p():\n"
            "    assert place_order(2)\n")
        adv = gen.binding_advisory(self.tmp, self._cfg([
            {"name": "下单", "domain": "ORDER", "impl": ["src/domain/order.py"],
             "tests": ["tests/unit/test_api.py"]},
        ]))
        self.assertEqual(adv["rows"][0]["status"], "bound")

    def test_via_one_hop_is_reported_with_bridge(self):
        self._write_impl()
        (self.tmp / "jobs").mkdir()
        (self.tmp / "jobs/run.py").write_text(
            "from src.domain.order import place_order\n\nJOB = place_order\n")
        (self.tmp / "tests/unit").mkdir(parents=True)
        (self.tmp / "tests/unit/test_job.py").write_text(
            "from jobs.run import JOB\n\ndef test_p():\n    assert JOB\n")
        adv = gen.binding_advisory(self.tmp, self._cfg([
            {"name": "下单", "domain": "ORDER", "impl": ["src/domain/order.py"],
             "tests": ["tests/unit/test_job.py"]},
        ]))
        self.assertEqual(adv["rows"][0]["status"], "via1")
        self.assertEqual(adv["rows"][0]["bridges"], ["jobs/run.py"])

    def test_unrelated_test_is_unbound_and_tier_untouched(self):
        """词面碰撞（同名测试挂在错误能力上）判 unbound；但 level/tier 不动。"""
        self._write_impl()
        (self.tmp / "src/other").mkdir(parents=True)
        (self.tmp / "src/other/registry.py").write_text("def lookup():\n    return {}\n")
        (self.tmp / "tests/unit").mkdir(parents=True)
        # 测的是 src/other/registry.py，与声明的 impl（src/domain/order.py）无关
        (self.tmp / "tests/unit/test_order_registry.py").write_text(
            "from src.other.registry import lookup\n\ndef test_p():\n"
            "    assert lookup()\n")
        cfg = self._cfg([
            {"name": "下单", "domain": "ORDER", "impl": ["src/domain/order.py"],
             "tests": ["tests/unit/test_order_registry.py"]},
        ])
        adv = gen.binding_advisory(self.tmp, cfg)
        self.assertEqual(adv["rows"][0]["status"], "unbound")
        # shadow 门禁的纪律：advisory 不参与判定，账本仍是 f(registry, 仓库, 报告)
        model = gen.build(self.tmp, cfg, {}, test_report=None, scope=None)
        cap = model["projects"][0]["modules"][0]["caps"][0]
        self.assertEqual(cap["level"], 3)
        self.assertEqual(cap["evidence_tier"], "declared")
        self.assertNotIn("binding", cap)

    def test_missing_impl_and_missing_tests_are_classified(self):
        (self.tmp / "tests/unit").mkdir(parents=True)
        (self.tmp / "tests/unit/test_only.py").write_text("def test_p():\n    assert 1\n")
        (self.tmp / "src").mkdir()
        (self.tmp / "src/only.py").write_text("X = 1\n")
        adv = gen.binding_advisory(self.tmp, self._cfg([
            {"name": "无实现", "domain": "A", "impl": [],
             "tests": ["tests/unit/test_only.py"]},
            {"name": "无测试", "domain": "B", "impl": ["src/only.py"], "tests": []},
        ]))
        by_domain = {r["code"]: r["status"] for r in adv["rows"]}
        self.assertEqual(by_domain["APP.CORE.A.01"], "no_impl")
        self.assertEqual(by_domain["APP.CORE.B.02"], "no_tests")


if __name__ == "__main__":
    unittest.main()
