---
name: ledger-lesson
description: |
  把 lessons.candidates（机器识别的降级/长期停滞/决策被推翻信号）确认成可复用经验，
  或写明理由驳回。确认后补 insight + action + scope，下一轮任务卡自动携带。
  Triggers: "经验候选", "确认经验", "驳回候选", "踩过的坑", "这个要记下来",
  "为什么一直停在 L2", "lesson learned", "confirm lesson"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "0.7.0"
  risk_level: write_with_guard
  related_skills: [ledger-scan, ledger-verify, ledger-guard]
---

# Ledger Lesson

经验层的"人工确认"入口。机器只识别信号，意义由人/AI 赋予。

## When to Use

`ledger-scan` 后出现新候选；或发现可复用规律需要写进经验库时。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | 候选 id（`LC-XXXXXX`）+ `insight` / `action` / `scope`，或驳回理由 |
| 输出 | `lessons.items` 新增 confirmed 条目，或候选设为 `dismissed` |
| 副作用 | 写 `lessons`；随后必须重跑生成器让任务卡携带新经验 |

## 步骤

```bash
# 1. 看候选与来源事件（事件可到看板「演进历史」对照）
python3 - <<'PY'
import json
d=json.load(open('governance/DECISION_LEDGER.json'))
for c in d['lessons']['candidates']:
    print(c['id'], c['kind'], c['reason'], 'events=', c['source_events'])
PY

# 2a. 确认成经验：必须有 insight 和 action
python3 scripts/ledger_lesson.py --ledger governance/DECISION_LEDGER.json \
    --candidate LC-C1CDBB --confirm \
    --title "长期停滞先查阻塞而非降优先级" \
    --insight "连续两个事件完成度不变通常意味着缺的不是时间，而是明确的下一步证据。" \
    --action "在 next_queue 命中两次仍无进展时，写一条 proposed 决策明确补哪一种证据。"

# 2b. 或驳回：必须给理由
python3 scripts/ledger_lesson.py --ledger governance/DECISION_LEDGER.json \
    --candidate LC-C1CDBB --dismiss --reason "该能力已排期下季度，非阻塞"

# 3. 重跑生成器：让任务卡携带新经验，并刷新候选
python3 governance/build_capability_model.py --root .
python3 governance/verify_ledger.py --root . --strict
```

## 硬纪律

- `confirmed` 必须同时有 `insight`（为什么）与 `action`（下次怎么做），缺一不可；
- `source_events` 必须指向真实事件，可在看板点击跳回；
- 驳回必须写理由，避免同一信号反复打扰；
- 不要写"要重视"这类无法执行的经验——`action` 必须是动作。

## 失败处理

| 现象 | 处理 |
|---|---|
| 候选 id 不存在 | 先 `ledger-scan` 刷新候选 |
| 缺 `insight` / `action` | 脚本拒绝写入，补齐后再试 |
| `queue_lessons_confirmed` FAIL | 任务卡引用了未确认经验，确认或移除引用后重跑生成器 |
