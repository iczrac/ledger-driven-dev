---
name: ledger-decide
description: |
  从 capability_model.next_queue 取一条任务，按纪律生成 proposed 决策写入账本。
  强制"一能力一决策"、证据引用、稳定 id 分配；禁止手改等级、禁止直接 done。
  Triggers: "下一轮做什么", "定个决策", "写一条 proposed", "把任务变决策",
  "立项", "规划下一轮", "create decision", "plan next capability"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "0.8.0"
  risk_level: write_with_guard
  related_skills: [ledger-scan, ledger-verify, ledger-lesson]
---

# Ledger Decide

把 SELECT 的产出（任务卡）转成 PLAN 的产出（一条 `proposed` 决策）。只写决策，不改能力状态。

## When to Use

`ledger-scan` 之后、`next_queue` 非空、需要为某个能力正式立项时。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | 账本路径 + 目标能力 `code`（来自 `next_queue`） |
| 输出 | 在 `entries` 追加一条 `status: proposed` 决策，返回其 id |
| 副作用 | 只写 `entries`；不改 `capability_model` / `history` / `lessons` |

## 步骤

```bash
# 1. 先看任务卡（含缺失证据、文档、经验）
python3 - <<'PY'
import json
d=json.load(open('governance/DECISION_LEDGER.json'))
for t in d['capability_model']['next_queue'][:3]:
    print(t['code'], t['level'], '→', t['target_level'], t['missing_evidence'], t['lessons'])
PY

# 2. 用脚本写入 proposed（自动检查重复、分配 id、填证据）
python3 scripts/ledger_decide.py --ledger governance/DECISION_LEDGER.json \
    --code DEMO.API.QUERY.01 --title "补齐订单查询接口单测" \
    --rationale "next_queue rank 1，缺契约/单测/测试记录"

# 3. 验证（决策变更不应破坏任何不变量）
python3 governance/verify_ledger.py --root . --strict
```

## 硬纪律

1. **一能力一决策**：已有未完结 `proposed` 时拒绝重复立项；
2. **证据必须真实**：`evidence` 引用真实路径或能力 code，不写"稍后补"；
3. **不做价值裁决**：优先级由人定，你只提供任务卡和选项；
4. **状态只能 proposed**：`done` 必须在 `ledger-scan` 达成等级后流转；
5. **取代而非改写**：推翻旧决策用 `supersedes`，不删旧条目。

## 失败处理

| 现象 | 处理 |
|---|---|
| 目标 code 不在 `next_queue` | 先 `ledger-scan`；若已达 L5 则无需立项 |
| 已有未结 `proposed` | 不写新条目，向人报告现有决策 id 与状态 |
| verify 失败 | 停止，按 `ledger-verify` 修复表处理 |
