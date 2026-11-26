"""经验层消费路径：任务卡里的 confirmed 经验必须真的到达执行者。

背景
----
经验层的设计闭环是「历史产生信号 → 人确认结论 → 下一轮任务自带结论」。
但主仓曾把 ``next_queue[].lessons`` 直接丢弃在生成任务卡那一步：
经验被生成、被写进任务卡、被看板显示，却没有任何执行者读得到它。

本文件守住三件事：

1. **接得上**：生成器 → 任务卡 → goal_loop → expert_run，逐跳都在；
2. **不外传**：只有 id/title/insight/action 四个字段离开账本，
   scope/source_events/evidence 是账本内部事实；
3. **不污染路由**：经验文本绝不进 intent——route_expert 用子串匹配打分，
   经验里的「经验」「踩坑」「沉淀」会把实现任务误派给 ledger-steward。
"""
MODULE_ID = "core"
import json
import unittest
from contextlib import contextmanager
from pathlib import Path

from _base import ROOT, demo_copy, run_generator
import expert_run
import goal_ledger as gl
import goal_loop

# 目标描述：必须含任务 code（goal_loop 按 code 命中选任务），
# 且**不得**含「经验/踩坑/沉淀」这类路由关键词，否则本文件自己就污染了路由。
GOAL_DESC = "目标循环推进 DEMO.API.QUERY.01 能力补齐"
TASK_CODE = "DEMO.API.QUERY.01"
GOAL_ID = "G-L1"
CRIT = [{"id": "c1", "metric": "queue_empty", "target": "next_queue", "op": "eq"}]


def _lesson() -> dict:
    """一条 confirmed 经验。insight/action 故意含「踩坑」「经验」等路由关键词——
    只要它们被拼进 intent，路由就会被带偏（这正是本文件要防的坑）。"""
    return {
        "id": "L-900",
        "status": "confirmed",
        "created_ts": "2026-11-27 00:00 HKT",
        "title": "测试记录文件名必须命中 registry hints",
        "insight": ("踩坑记录：测试记录文件名不命中 registry hints 时，"
                    "证据不被识别，能力停在 L2，经验沉淀不下来。"),
        "action": ("新增测试记录时以 <hint>_test_record.md 命名，"
                   "并在生成器 dry-run 输出中确认等级跃迁后再提交。"),
        "scope": {"projects": ["DEMO"], "capabilities": [],
                  "domains": [], "levels": []},
    }


def _write_lessons(ledger: Path, items: list[dict]) -> None:
    d = json.loads(ledger.read_text(encoding="utf-8"))
    d.setdefault("lessons", {"spec": {}, "items": [], "candidates": []})
    d["lessons"]["items"] = items
    ledger.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_goal(ledger: Path) -> None:
    d = json.loads(ledger.read_text(encoding="utf-8"))
    gl.create_goal(d, goal_id=GOAL_ID, description=GOAL_DESC,
                   success_criteria=CRIT, max_loops=2,
                   authorized_by="授权人甲", approved_by="批准人乙")
    ledger.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture(root: Path, ledger: Path, reg: Path, board: Path,
             lessons: list[dict]) -> Path:
    """写经验 → 跑生成器 → 落目标，返回被治理项目根目录。"""
    _write_lessons(ledger, lessons)
    res = run_generator(root, ledger, reg, board)
    if res.returncode != 0:
        raise AssertionError(f"生成器失败：{res.stderr}")
    _add_goal(ledger)
    return root / "examples" / "demo-shop"


@contextmanager
def _spy_expert_run():
    """截获 goal_loop 传给 expert_run 的 intent / context。

    经验必须走 context 通道：这里把调用实参原样记下来，供断言证明
    intent 里没有经验文本、经验却在 context 里。
    """
    captured: dict = {}
    original = expert_run.run

    def spy(target, intent, *args, **kwargs):
        captured["intent"] = intent
        captured["context"] = kwargs.get("context")
        return original(target, intent, *args, **kwargs)

    expert_run.run = spy
    try:
        yield captured
    finally:
        expert_run.run = original


class TaskCardLessonTest(unittest.TestCase):
    """第一跳：生成器把 confirmed 经验挂到任务卡上（且只挂白名单字段）。"""

    def test_generator_attaches_confirmed_lesson_to_task_card(self):
        with demo_copy() as (root, ledger, reg, board):
            _write_lessons(ledger, [_lesson()])
            res = run_generator(root, ledger, reg, board)
            self.assertEqual(res.returncode, 0, res.stderr)
            d = json.loads(ledger.read_text(encoding="utf-8"))
            task = next(t for t in d["capability_model"]["next_queue"]
                        if t["code"] == TASK_CODE)
            refs = task.get("lessons") or []
            self.assertEqual([r["id"] for r in refs], ["L-900"])
            # 账本内部事实不得出现在任务卡上
            self.assertEqual(set(refs[0]), {"id", "title", "insight", "action"})

    def test_unconfirmed_lesson_is_not_attached(self):
        draft = dict(_lesson(), status="draft")
        with demo_copy() as (root, ledger, reg, board):
            _write_lessons(ledger, [draft])
            res = run_generator(root, ledger, reg, board)
            self.assertEqual(res.returncode, 0, res.stderr)
            d = json.loads(ledger.read_text(encoding="utf-8"))
            task = next(t for t in d["capability_model"]["next_queue"]
                        if t["code"] == TASK_CODE)
            self.assertEqual(task.get("lessons") or [], [])


class LessonHandoffTest(unittest.TestCase):
    """第二跳：goal_loop 把经验交给执行者（任务卡 → 轮次记录 → expert_run）。"""

    def test_lesson_reaches_round_record_and_executor_context(self):
        with demo_copy() as (root, ledger, reg, board):
            target = _fixture(root, ledger, reg, board, [_lesson()])
            with _spy_expert_run() as cap:
                out = goal_loop.run(target, GOAL_ID)
            self.assertTrue(out["rounds"], "没有任何轮次记录")
            r0 = out["rounds"][0]
            self.assertEqual(r0["task"]["code"], TASK_CODE)
            # 任务卡上的经验没被丢弃
            self.assertIn("L-900", [x["id"] for x in r0["task"]["lessons"]])
            # 执行者真的收到了经验
            ctx = r0["plan"]["task_context"]
            self.assertEqual(ctx["task_code"], TASK_CODE)
            self.assertIn("L-900", [x["id"] for x in ctx["lessons"]])
            # 并且是从独立通道收到的
            self.assertIn("L-900", [x["id"] for x in (cap["context"] or {}).get("lessons", [])])

    def test_without_confirmed_lesson_both_places_are_empty(self):
        """负向：抽掉经验后两处皆空——证明不是硬编码。"""
        with demo_copy() as (root, ledger, reg, board):
            target = _fixture(root, ledger, reg, board, [])
            with _spy_expert_run() as cap:
                out = goal_loop.run(target, GOAL_ID)
            r0 = out["rounds"][0]
            self.assertEqual(r0["task"]["lessons"], [])
            self.assertEqual(r0["plan"]["task_context"]["lessons"], [])
            self.assertEqual((cap["context"] or {}).get("lessons"), [])

    def test_lesson_text_never_enters_intent(self):
        """路由不污染：经验走 context 通道，不进 intent。"""
        lesson = _lesson()
        with demo_copy() as (root, ledger, reg, board):
            target = _fixture(root, ledger, reg, board, [lesson])
            with _spy_expert_run() as cap:
                out = goal_loop.run(target, GOAL_ID)
            intent = cap["intent"]
            self.assertNotIn(lesson["insight"], intent)
            self.assertNotIn(lesson["action"], intent)
            # 「踩坑」「经验」都是 route_expert 的 lesson 意图关键词，
            # 一旦进 intent 就会把实现任务误派给 ledger-steward。
            self.assertNotIn("踩坑", intent)
            self.assertNotIn("经验", intent)
            self.assertNotEqual(out["rounds"][0]["route"]["expert"], "ledger-steward")
            self.assertIn("L-900", [x["id"] for x in cap["context"]["lessons"]])


class LessonRefTest(unittest.TestCase):
    """goal_loop._lesson_refs 的白名单与截断策略（纯函数级）。"""

    def test_whitelist_only(self):
        task = {"code": "C.1", "lessons": [{
            "id": "L-001", "title": "t", "insight": "i", "action": "a",
            "scope": {"projects": ["P"]}, "source_events": [1],
            "from_candidate": "LC-X", "evidence": ["docs/x.md"],
        }]}
        view = goal_loop._lesson_refs(task)
        self.assertEqual(len(view["lessons"]), 1)
        self.assertEqual(set(view["lessons"][0]), {"id", "title", "insight", "action"})

    def test_priority_puts_code_match_first(self):
        task = {"code": "C.1", "project": "P", "domain": "D", "level": "L2",
                "lessons": [
                    {"id": "L-002", "title": "t", "insight": "i", "action": "a",
                     "scope": {"projects": ["OTHER"]}},
                    {"id": "L-001", "title": "t", "insight": "i", "action": "a",
                     "scope": {"capabilities": ["C.1"]}},
                    {"id": "L-003", "title": "t", "insight": "i", "action": "a",
                     "scope": {"domains": ["D"]}},
                ]}
        view = goal_loop._lesson_refs(task)
        self.assertEqual([x["id"] for x in view["lessons"]],
                         ["L-001", "L-003", "L-002"])

    def test_cap_and_visible_truncation(self):
        task = {"code": "C.1", "lessons": [
            {"id": f"L-{i:03d}", "title": "t", "insight": "i", "action": "a"}
            for i in range(1, 16)]}
        view = goal_loop._lesson_refs(task)
        self.assertEqual(view["total"], 15)
        self.assertEqual(len(view["lessons"]), goal_loop.LESSON_MAX_REFS)
        self.assertTrue(view["truncated"])
        # 被截断的条目必须可见，不静默丢
        self.assertEqual(view["dropped"],
                         [f"L-{i:03d}" for i in range(11, 16)])

    def test_malformed_entries_are_skipped(self):
        task = {"code": "C.1", "lessons": [
            "not-a-dict", {"title": "无 id"}, {"id": "L-001", "title": "t",
                                                "insight": "i", "action": "a"}]}
        view = goal_loop._lesson_refs(task)
        self.assertEqual([x["id"] for x in view["lessons"]], ["L-001"])
        self.assertEqual(view["total"], 1)


class ExpertRunContextTest(unittest.TestCase):
    """第三跳：expert_run 的独立 context 通道。"""

    def test_task_context_always_present_even_without_lessons(self):
        out = expert_run.run(ROOT, "校验账本不变量")
        self.assertIn("task_context", out)
        self.assertEqual(out["task_context"]["lessons"], [])
        self.assertTrue(out["task_context"]["note"])
        # intent 保持原样
        self.assertEqual(out["intent"], "校验账本不变量")

    def test_context_does_not_change_intent_or_route(self):
        intent = "补单测：实现 API 查询"
        base = expert_run.run(ROOT, intent)
        with_ctx = expert_run.run(ROOT, intent, context={
            "task_code": "C.1",
            "lessons": [{"id": "L-001", "title": "踩坑：命名不对",
                         "insight": "踩坑记录：经验沉淀不下来",
                         "action": "按 hint 命名后再跑生成器"}],
        })
        self.assertEqual(with_ctx["intent"], base["intent"])
        self.assertEqual(with_ctx["route"]["expert"], base["route"]["expert"])
        self.assertEqual([x["id"] for x in with_ctx["task_context"]["lessons"]], ["L-001"])

    def test_context_whitelist_drops_internal_fields(self):
        out = expert_run.run(ROOT, "校验账本不变量", context={
            "task_code": "C.1",
            "lessons": [{"id": "L-001", "title": "t", "insight": "i", "action": "a",
                         "scope": {"projects": ["P"]}, "source_events": [1],
                         "evidence": ["docs/x.md"]}],
        })
        ref = out["task_context"]["lessons"][0]
        self.assertEqual(set(ref), {"id", "title", "insight", "action"})

    def test_truncated_context_is_visible(self):
        out = expert_run.run(ROOT, "校验账本不变量", context={
            "task_code": "C.1",
            "lessons": [{"id": "L-001", "title": "t", "insight": "i", "action": "a"}],
            "total": 12, "truncated": True, "dropped": ["L-002", "L-003"],
        })
        ctx = out["task_context"]
        self.assertTrue(ctx["truncated"])
        self.assertEqual(ctx["dropped"], ["L-002", "L-003"])
        self.assertIn("截断", ctx["note"])


if __name__ == "__main__":
    unittest.main()
