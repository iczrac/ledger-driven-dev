---
name: graph-compare
description: |
  文档→目标架构、git→决策/迭代追踪、规划图与实际图比对：输出能力级 diff、
  开发顺序、执行专家与前置条件，配套 JSON 与人类可读报告。
  Triggers: "规划图", "实际图", "比对规划", "能力差距", "开发顺序",
  "git 跟进决策", "目标架构", "graph diff", "execution order"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.0.0"
  risk_level: write_draft_only
  related_skills: [doc-rebuild, expert-route, ledger-guard, ledger-scan]
---

# Graph Compare

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 专家路由与资产/账本校验走唯一入口：`python3 scripts/ledger_entry.py --intent "任务描述"` 或 `--check-all`；任一门禁失败即退出码 1（fail-closed）。
- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。


回答四个问题：目标是什么、实际做到哪、差在哪、下一步谁来做。所有结论落到能力编码。

## When to Use

需要向人/AI 解释「规划 vs 现状」；接手历史项目要按 git 变更追决策；要给执行专家一条可开工的顺序。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--target`、可选 `--target-arch` / `--git-trace` / `--registry` / `--ledger` |
| 输出 | `governance/TARGET_ARCHITECTURE.json`、`GIT_TRACE.json`、`GRAPH_DIFF.json`、`docs/generated/GRAPH_DIFF.md` |
| 副作用 | 只写规划/追踪/比对产物；既有文件默认跳过，`--force` 才覆盖 |
| 专家 | 每条差距给 `loop-executor` / `project-archaeologist` / `ledger-steward`，总负责人由 `expert-route` 给出 |

## 步骤

```bash
python3 scripts/architect_from_docs.py --target /path/to/project --dry-run
python3 scripts/architect_from_docs.py --target /path/to/project
python3 scripts/trace_git.py --target /path/to/project --max-count 50
python3 scripts/compare_graphs.py --target /path/to/project \
  --git-trace /path/to/project/governance/GIT_TRACE.json
```

## 解读输出

- `aligned` / `in_progress` / `not_started` / `planned_only` / `actual_only` 五态，不要混成"完成/没完成"；
- `planned_only` 多数是 `impl`/`hints` 未配好，先交给考古专家校准，别急着排开发；
- `actual_only` 是治理缺口：补文档或裁决废弃，由账本治理专家处理；
- `execution_order` 优先取 `next_queue`，已带 `lessons` 与 tier；一条即可开工；
- `iteration_signals` 里的 `L2→L5` 来自历史事件，不是 commit message 自述。

## 禁止

- 禁止用 commit message 替代真实变更路径做映射；
- 禁止跳过 `evidence-auditor` 直接执行 `execution_order`；
- 禁止把 `confidence=low` 的目标架构当确定规划；
- 禁止手改 `GRAPH_DIFF.json` 来"显得没有差距"。

## 失败处理

| 现象 | 处理 |
|---|---|
| 没有目标架构 | 会退回 registry 并给 warning；先跑 `doc-rebuild` + `architect_from_docs` |
| 目标不是 git 仓库 | `trace_git.py` 退出码 2；比对仍可做，但 commit 映射为空 |
| 大量 planned_only | 校准 registry 的 impl / hints，再重跑生成器 |
| 大量 actual_only | 人工裁决：补进规划文档或标记 deferred |
