---
name: ledger-scan
description: |
  重跑 capability generator，从真实文件系统重算能力等级、完成度、嵌套组件树、
  文档索引、append-only 历史、经验候选与 next_queue 任务队列。
  Triggers: "重跑生成器", "刷新账本", "扫描能力", "看任务队列", "完成度变了",
  "能力到哪了", "recap ledger", "scan capability", "next_queue"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "0.6.0"
  risk_level: write_with_guard
  related_skills: [ledger-verify, ledger-decide, ledger-guard]
---

# Ledger Scan

账本的唯一"写入扫描"入口。所有派生数据只能由它产生，不接受手填。

## When to Use

代码、测试、文档变更后；或需要查看当前能力状态、历史新增事件、下一轮任务时。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--root`（项目或仓库根）、`--registry`、`--ledger`、`--board` |
| 输出 | 写回账本 `capability_model` / `history.events` / `lessons.candidates`；同步看板 EMBED |
| 副作用 | 写文件；**状态未变化时不追加历史事件**（幂等） |

## 步骤

```bash
# 1. 先 dry-run：确认等级与将追加的事件符合预期，不落盘
python3 governance/build_capability_model.py --root . --dry-run

# 2. 正式生成
python3 governance/build_capability_model.py --root .

# 3. 必须紧接着验证（本技能的一半）
python3 governance/verify_ledger.py --root . --strict
```

## 解读输出

- `history` 行显示 `无变化（幂等）` → 正常，说明派生状态未变；
- 显示 `将追加 #N change` → 检查 `level_transitions` 是否是你预期的变化；
- `经验：N 个候选` → 新增候选意味着出现了降级、长期停滞或决策被取代，需交 `ledger-lesson` 处理。

## 禁止

- 手改生成后的 `level` / `completion` / `history.events` / 看板 `EMBED`；
- 为了让历史"好看"而删除事件——用 `supersedes` 表达演进；
- 跳过第 3 步验证。

## 失败处理

| 现象 | 处理 |
|---|---|
| registry 实现路径不存在 | 修正 `registry.json` 的 `impl` 或实际文件路径 |
| `board EMBED 同步失败` | 确认看板含 `const EMBED` / `let DATA` 标记，或用 `--no-board` 后单独同步 |
| verify 报 FAIL | 停止写入，按 `ledger-verify` 的修复表处理 |
