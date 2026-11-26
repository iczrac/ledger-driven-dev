---
name: expert-route
description: |
  确定性专家路由：只读扫描项目状态并识别任务意图，输出唯一负责人、置信度、理由、
  交接对象与阻塞条件；冲突时要求澄清，不让多个专家同时改写同一事实源。
  Triggers: "该找谁", "专家路由", "用哪个专家", "路由", "先分析再动手",
  "历史项目还是新项目", "expert route", "which expert", "route"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.0.0"
  risk_level: read_only
  related_skills: [project-discover, project-bootstrap, ledger-guard]
---

# Expert Route

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。


把一句模糊需求和一个陌生目录，变成一条可追踪的路由决定。路由本身不改任何文件。

## When to Use

不知道该用哪个专家；面对历史项目或空目录；任务描述与项目现状可能冲突；多人/多 Agent 可能同时写入前。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--target`（项目根）、`--intent`（用户原话）、`--mode auto\|greenfield\|brownfield`、`--max-files` |
| 输出 | `expert-route/1` JSON：`detected_mode` / `facts` / `intents` / `needs_clarification` / `route` |
| 副作用 | 无；只读扫描，文件数有上限 |

## 步骤

```bash
# 1. 人类可读：先看状态与结论
python3 scripts/route_expert.py --target /path/to/project --intent "历史项目接手，先盘点"

# 2. 机器可读：给编排层消费
python3 scripts/route_expert.py --target /path/to/project --intent "$TASK" --json

# 3. 显式模式：仅在人已确认边界时使用
python3 scripts/route_expert.py --target /path/to/project --mode greenfield --intent "新建项目"
```

## 解读输出

- `detected_mode=corrupt` → 账本损坏，直接冻结，交给 `evidence-auditor`；
- `needs_clarification` 非空 → 把 `question` 与 `options` 原样抛给人，本轮不要继续；
- `route.blocked=true` → 先处理 `handoff.stop_if`，不得写代码或决策；
- `route.confidence=low|medium` → 把 `handoff.open_questions` 一并转交，不要悄悄当高置信执行；
- `route.handoff.next_expert` → 该专家完成后重新路由，不假设一条路由覆盖整轮循环。

## 禁止

- 禁止路由自己写文件、改账本或替人选择业务优先级；
- 禁止在冲突未澄清时按"最像"的意图继续执行；
- 禁止忽略 `detected_mode`，只按 `--intent` 关键词选专家；
- 禁止把绝对路径、机器名写进对外报告（脚本输出已做相对化处理）。

## 失败处理

| 现象 | 处理 |
|---|---|
| 目标目录不存在 | 退出码 2，要求确认路径后重试 |
| 扫描被截断 | 提高 `--max-files` 后重跑，或接受草稿警告 |
| 多个意图并列 | 按 `needs_clarification.options` 请人明确选择 |
| 显式模式与事实冲突 | 先确认是"子目录新建"还是"存量接入"，再决定是否加 `--force` |
