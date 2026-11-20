---
name: goal-orchestrate
description: |
  目标编排技能：在授权预算内对单一目标做受控自动循环。提供目标对象创建、方向锁、
  max_loops 预算控制、每轮重路由+强验证、超预算失活、结构化调整提议（须人批准）。
  默认 dry-run 零写入，所有落盘走 agent_gateway，可中断可审计。
  Triggers: "目标循环", "自动迭代达成", "监督循环", "目标预算", "调整目标",
  "goal loop", "orchestrate goal", "auto iterate", "propose goal change"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.13.0"
  risk_level: read_only
  related_skills: [expert-route, expert-run, agent-gate, ledger-scan, ledger-verify,
                   scenario-guard, work-panel]
---

# Goal Orchestrate（目标编排技能）

把「目标」变成账本里一等公民，并在预算内受控推进。

## 何时使用

- 用户给出**一个明确目标**并要求「自动推进 / 反复迭代 / 直到达成」。
- 需要防止 Agent 在多轮中**改目标 / 超预算 / 跳过验证**。
- 目标需要**调整**但必须由人拍板。

三个前置：账本已有 `access` 登记（upgrade）；有 `goal-orchestrator` 角色的 Agent
已由人 register；目标由人通过 `goal-create` 创建。

## 三步工作流

### 1. 人批准创建目标

```bash
python3 scripts/agent_gateway.py request --target P \
  --agent ledger-steward --action goal-create \
  --goal-id G-001 --title "把 D3 能力点升到 L5" \
  --criteria '[{"id":"c1","metric":"cap_level","target":"METHOD.GOV.D3.15","op":"gte","value":5}]' \
  --max-loops 5 --authorized-by 张三 --approved-by 张三 \
  --expect-fingerprint <fp> --apply
```

`success_criteria` 是机读数组，每项：`id / metric / target / op / value`。
支持 metric：`cap_level`、`queue_empty`、`invariant_all`。
创建即写入 `direction_lock = sha256(description + success_criteria)`。

### 2. dry-run 循环（只读，默认）

```bash
python3 scripts/goal_loop.py --target P --goal-id G-001 --json
```

每轮：取 next_queue 一条 → 重路由 → expert-run 计划 → `verify_ledger --strict`
→ 方向锁检查 → advance（内存副本）→ 判据评估。任一 fail-closed 点即停。
输出 verdict / stop_reason / rounds[] / commands[]（待批准命令，本脚本不执行）。

### 3. 人逐条批准网关命令

```bash
# 预算内推进（由预算授权，仍走网关审计）
python3 scripts/agent_gateway.py request --target P \
  --agent goal-orchestrator --action goal-advance --goal-id G-001 \
  --expect-fingerprint <fp> --apply
# 超预算失活 / 达标
... --action goal-deactivate --reason "max_loops 用尽" --apply
... --action goal-achieve --apply
```

## 调整目标（方向锁升级路径）

Agent **不得**直接改目标。只能提议：

```bash
python3 scripts/agent_gateway.py request --target P \
  --agent goal-orchestrator --action goal-propose --goal-id G-001 \
  --original-goal "..." --proposed-change "..." --rationale "..." --impact "..." \
  --proposed-description "..." --proposed-criteria '[...]' --apply
```

产出 `proposals[]`（pending），随后由**人**批准才重算方向锁：

```bash
... --action goal-approve --goal-id G-001 --proposal-id P-001 --approved-by 张三 --apply
```

`approve_change` 是唯一能重算 `direction_lock` 的入口；`goal-reject` 驳回则目标不变。

## 不变量护栏

第 30 条 `goal_loop_valid` 校验：状态枚举、预算单调（current_loop ≤ max_loops）、
终态不再活跃、已达成不活跃、方向锁与当前描述/判据一致、提议字段完整。
方向锁不匹配即 fail，专权由人 approve 恢复。

## 诚实边界

- 这是**策略性受控循环**，不是操作系统沙箱；能直接写账本的人仍可绕过，
  但绕不过 `check.sh` 的不变量与审计。
- `goal_loop.py` 默认 dry-run，**不执行**专家命令；批准包里的命令由人执行。
- 达成判定是机读判据，不替代 `verify_ledger` 门禁；两者都过才算达标。
