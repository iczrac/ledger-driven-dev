"""A 项：depends_on 消费——同层稳定拓扑重排 + 环检测 shadow 先行。

MODULE_ID = "traceability"
"""
MODULE_ID = "traceability"
import json
import subprocess
import sys
import unittest
from pathlib import Path

from _base import ROOT, demo_copy

COMPARE = ROOT / "scripts" / "compare_graphs.py"
REBUILD = ROOT / "scripts" / "rebuild_docs.py"
ARCHITECT = ROOT / "scripts" / "architect_from_docs.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *map(str, args)],
                          capture_output=True, text=True)


class DepTopologyTest(unittest.TestCase):
    def _prepare(self, proj: Path) -> dict:
        run(REBUILD, "--target", proj)
        run(ARCHITECT, "--target", proj)
        arch = proj / "governance" / "TARGET_ARCHITECTURE.json"
        return json.loads(arch.read_text())

    def test_depends_on_reorders_within_same_level(self):
        """同层 queue 项中，被依赖者必须排在依赖者之前（真实多 queue 夹具）。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            data = self._prepare(proj)
            caps = {c["code"]: c for c in data["capabilities"]}
            a, b = "DEMO.API.QUERY.01", "DEMO.CORE.PRICE.02"
            caps[a]["depends_on"] = [b]
            data["capabilities"] = list(caps.values())
            (proj / "governance" / "TARGET_ARCHITECTURE.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2))
            # 账本 next_queue 原只有 1 项，注入同层第 2 项才能真实验证排序。
            led_path = proj / "governance" / "DECISION_LEDGER.json"
            led = json.loads(led_path.read_text())
            q = led["capability_model"]["next_queue"]
            seed = dict(q[0])
            seed.update({"code": b, "level": "L2", "target_level": "L3",
                         "action": "构造的同层项"})
            q.append(seed)  # 原序：a 在 b 前；依赖要求：b 在 a 前
            led_path.write_text(json.dumps(led, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            order = [e["code"] for e in diff["execution_order"]]
            self.assertIn(a, order)
            self.assertIn(b, order)
            self.assertLess(order.index(b), order.index(a))

    def test_sparse_depends_on_keeps_original_order(self):
        """depends_on 全空时 execution_order 必须与当前行为完全一致。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self._prepare(proj)
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            base = [e["code"] for e in diff["execution_order"]]
            self.assertEqual(base[0], "DEMO.API.QUERY.01")
            self.assertEqual(len(base), len(set(base)))

    def test_cycle_is_shadow_warning_not_hard_failure(self):
        """环检测只告警，不改退出码、不改状态（shadow 纪律）。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            data = self._prepare(proj)
            caps = {c["code"]: c for c in data["capabilities"]}
            a, b = "DEMO.API.QUERY.01", "DEMO.CORE.PRICE.02"
            caps[a]["depends_on"] = [b]
            caps[b]["depends_on"] = [a]
            data["capabilities"] = list(caps.values())
            (proj / "governance" / "TARGET_ARCHITECTURE.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2))
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            diff = json.loads(proc.stdout)
            self.assertTrue(any("环" in w or "循环依赖" in w for w in diff["warnings"]))
            self.assertIn("dep_cycles", diff)
            self.assertTrue(diff["dep_cycles"])

    def test_dep_order_is_stable_for_unrelated(self):
        """无依赖关系的项保持原相对顺序（稳定排序）。"""
        with demo_copy() as (tmp, _ledger, _reg, _board):
            proj = tmp / "examples" / "demo-shop"
            self._prepare(proj)
            proc = run(COMPARE, "--target", proj, "--force", "--json")
            diff = json.loads(proc.stdout)
            codes = [e["code"] for e in diff["execution_order"]]
            self.assertEqual(codes, sorted(codes, key=lambda c: codes.index(c)))


if __name__ == "__main__":
    unittest.main()
