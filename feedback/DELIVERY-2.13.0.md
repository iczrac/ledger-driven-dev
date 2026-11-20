# 交付 v2.13.0 · 目标编排监督者（Goal Orchestrator）

## 做了什么

- **目标对象 `goals/1`**：账本顶层新增目标一等公民，含方向锁、机读成功判据、
  循环预算、状态机、逐动作审计与调整提议。
- **新专家 + 技能**：`experts/goal-orchestrator/EXPERT.md`（只读监督者）、
  `skills/goal-orchestrate/SKILL.md`（创建/循环/批准/提议工作流）。
- **网关动作**：`agent_gateway` 新增 `goal-create/propose/approve/reject/advance/
  achieve/deactivate/pause/resume`，全部走统一 access/role/CAS/lock/audit；
  create/approve/reject 必须人 `--approved-by`。
- **循环脚本 `goal_loop.py`**：默认 dry-run，每轮重路由 → 取队列 → expert-run 计划 →
  verify_ledger → 方向检查 → 推进 → 判据评估；超预算 `deactivated`，达标 `achieved`。
- **路由**：`goal` 意图高置信路由到 goal-orchestrator，交接链 `[goal-orchestrator,
  evidence-auditor, ledger-steward]`。
- **不变量 30 `goal_loop_valid`** + **升级 M9-goals**：守护方向锁、预算单调、终态纪律。

## 关键设计

- **方向锁**：`sha256(canonical(description + success_criteria))`，唯一解入口是
  `goal-approve`（人批准）。专家私自改目标会被第 30 条不变量抓到。
- **预算即边界**：`max_loops` 用尽未达成即失活；终态不可再推进。
- **dry-run 零写入**：循环在账本内存副本上跑，输出的网关命令由人逐条批准执行；
  验证跳过看板 EMBED 阻塞，避免内存推进与未写看板的假失败。

## 验证

- 目标编排单测 21/21 passed（创建/方向锁/预算/终态/暂停恢复/提议批准/判据/网关分发/路由/不变量）。
- 端到端 dry-run：路线 2 轮全过验证（verify fail=0），预算用尽 → `deactivated`，
  生成 3 条待批准网关命令；方向篡改与验证失败场景均 fail-closed。
- `verify_ledger --strict`：30 条不变量无 fail。
- `check.sh` 全量门禁与账本/看板同步见发布记录。

## 使用入口

- 建目标：`agent_gateway.py request --action goal-create --approved-by <人>`
- 看轨迹：`python3 scripts/goal_loop.py --target P --goal-id G-001 --json`
- 批准推进：逐条执行 `--emit-apply` 导出的网关命令
- 详细说明：`docs/33-目标编排监督者.md`
