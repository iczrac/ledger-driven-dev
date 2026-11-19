"""派生 issue（v2.3.0）：把「非 bound 能力」自动投影成可认领的 issue。

第一性原理：v2.2.0 让 verified⟺bound，14 个能力诚实降级——但只报警不闭环的
红灯会退化成「红灯疲劳」。issue 必须存在，且不能是手工维护的第二事实源：
手工 issue 可被删、可改状态，等于把「声明权=伪造权」又请回来。

本组用例钉住四条契约：
1) 每个非 bound 能力都有唯一派生 issue（固定 id、source=derived、derived_from）；
2) 幂等：重复生成不新增、不改人工补充字段（owner/owner_note/人工 detail）；
3) 能力转 bound 时对应 issue 自动关闭，关闭依据写进 resolution；
4) verifier #27：非 bound 却缺 issue、或已 bound 却仍 open，都必须 fail。
"""
MODULE_ID = "core"

import importlib.util
import sys
import unittest
from pathlib import Path

from _base import ROOT  # noqa: F401  确保 sys.path 指向 templates/

_spec = importlib.util.spec_from_file_location(
    "_v230_derived", ROOT / "templates" / "derived_issues.py")
dv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dv)


def _caps(*rows):
    return [{"code": c, "binding_status": b} for c, b in rows]


class DerivedIssuesTest(unittest.TestCase):

    def test_non_bound_caps_get_one_derived_issue_each(self):
        caps = _caps(("A.UNBOUND.01", "unbound"), ("A.NOIMPL.02", "no_impl"),
                     ("A.BOUND.03", "bound"))
        items = dv.sync_derived_issues([], caps)
        derived = [x for x in items if x.get("source") == "derived"]
        self.assertEqual(len(derived), 2)
        by_scope = {x["derived_from"]["code"]: x for x in derived}
        self.assertIn("A.UNBOUND.01", by_scope)
        self.assertIn("A.NOIMPL.02", by_scope)
        self.assertNotIn("A.BOUND.03", by_scope)
        # 关闭条件必须是机器可判定且复用的既有 kind
        for x in derived:
            self.assertEqual(x["kind"], "issue")
            self.assertEqual(x["status"], "open")
            self.assertEqual(x["close_condition"]["kind"], "capability_verified")
            self.assertEqual(x["close_condition"]["capability"], x["derived_from"]["code"])
            self.assertTrue(x["id"].startswith("W-BIND-"))
            self.assertTrue(x.get("owner_note"), "派生 issue open 必须有 owner_note 满足 #25")

    def test_severity_reflects_binding_status(self):
        caps = _caps(("A.UNBOUND.01", "unbound"), ("A.VIA1.02", "via1"),
                     ("A.NOTESTS.03", "no_tests"), ("A.NOIMPL.04", "no_impl"))
        items = dv.sync_derived_issues([], caps)
        sev = {x["derived_from"]["code"]: x["severity"] for x in items}
        self.assertEqual(sev["A.UNBOUND.01"], "high")
        self.assertEqual(sev["A.NOIMPL.04"], "high")
        self.assertEqual(sev["A.VIA1.02"], "med")
        self.assertEqual(sev["A.NOTESTS.03"], "med")

    def test_idempotent_and_preserves_human_fields(self):
        caps = _caps(("A.UNBOUND.01", "unbound"))
        first = dv.sync_derived_issues([], caps)
        item = first[0]
        item["owner"] = "张三"
        item["owner_note"] = "已认领，正在补单测"
        item["detail"] = "人工补充：测试实测的是 jobs 编排层"
        second = dv.sync_derived_issues(first, caps)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["owner"], "张三")
        self.assertEqual(second[0]["owner_note"], "已认领，正在补单测")
        self.assertEqual(second[0]["detail"], "人工补充：测试实测的是 jobs 编排层")
        self.assertEqual(second[0]["id"], item["id"])

    def test_bound_cap_auto_closes_its_derived_issue(self):
        caps = _caps(("A.UNBOUND.01", "unbound"))
        items = dv.sync_derived_issues([], caps)
        items[0]["owner"] = "李四"
        # 能力修好：转 bound
        closed = dv.sync_derived_issues(items, _caps(("A.UNBOUND.01", "bound")))
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["status"], "done")
        self.assertEqual(closed[0]["owner"], "李四", "人工 owner 不因自动关单丢失")
        self.assertTrue(closed[0].get("resolution"))
        self.assertTrue(closed[0].get("closed_at"))

    def test_check_detects_deleted_derived_issue(self):
        """可复算判据覆盖 issue：手删派生 issue 必须报漂移。"""
        caps = _caps(("A.UNBOUND.01", "unbound"))
        items = dv.sync_derived_issues([], caps)
        self.assertEqual(dv.diff_derived_issues(items, caps), [])
        # 模拟手删：账本里 issue 消失
        drifts = dv.diff_derived_issues([], caps)
        self.assertTrue(any("缺派生 issue" in x for x in drifts), drifts)

    def test_check_detects_stale_binding_status(self):
        """能力已 bound 但 issue 仍标旧状态 → 漂移。"""
        caps = _caps(("A.UNBOUND.01", "unbound"))
        items = dv.sync_derived_issues([], caps)
        # 状态升级为 bound，账本 issue 未同步
        drifts = dv.diff_derived_issues(items, _caps(("A.UNBOUND.01", "bound")))
        self.assertTrue(any("status" in x for x in drifts), drifts)

    def test_manual_items_untouched(self):
        manual = {"id": "W-ISSUE-901", "kind": "issue", "scope": "PROJECT",
                  "status": "open", "severity": "med", "title": "人工项",
                  "detail": "", "owner": "", "refs": []}
        items = dv.sync_derived_issues([manual], _caps(("A.UNBOUND.01", "unbound")))
        self.assertEqual(len(items), 2)
        self.assertEqual([x for x in items if x["id"] == "W-ISSUE-901"][0], manual)


if __name__ == "__main__":
    unittest.main()
