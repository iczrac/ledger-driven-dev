# 黄金范例：一句话走完整条治理链

**可运行、可复算、全程只读**的端到端演示。它证明这个项目「全 AI 驱动」的真实形态：
机器自治编排，人只在批准点拍板——不是拆掉所有门。

## 运行

```bash
# 在 ledger-driven-dev 方法仓根目录
bash examples/golden-walkthrough/run.sh
```

六步链路（全部 `--json` / `--check` / 只读，无 `--apply`、无写盘）：

| 步骤 | 命令 | 说明 |
|---|---|---|
| 1 复述门 | `intent_restate.py --intent-file` | 人话 → 结构化声明 → 真实 registry/账本锚定，8 校验全 pass |
| 2 路由 | `route_expert.py --intent` | 唯一负责人 `loop-executor` / high + 3 跳交接链 |
| 3 编排 | `expert_run.py --intent --json` | 沿链展开逐跳契约，dry-run 零执行，ready |
| 4 批准包 | 同上取 `approval_bundle` | 只列需人 `--approved-by` 的写入点 |
| 5 来源投影 | `provenance_view.py --kind issue` | issue 按 `[AI推断]`/`[人确认]` 分组展示 |
| 6 完成定义 | `provenance_view.py --kind task` | 从 `missing_evidence` 派生 `definition_of_done`，不写回账本 |

## 三个第一性原理在范例里的落点

1. **声明权 ≠ 伪造权**：步骤 1 的能力码 `DEMO.API.QUERY.01` 必须在账本里真实存在，
   否则 `cap_anchored` 拒；人话照抄不算复述，`restate_nonempty` 拦。
2. **零新判定权**：步骤 3 的负责人、交接链、命令全部来自路由与 `EXPERT_CARDS`，
   编排器只展开不裁决；写命令一律进批准包（步骤 4）。
3. **单一事实源**：步骤 5/6 不往账本加 `origin` / `definition_of_done` 字段——
   它们是把既有 `source` / `derived_from` / `owner` / `missing_evidence` 做只读投影。
   同一事实不在两处表达。

## 教学点：fail-closed 不是缺陷

把意图换成 **「补齐 DEMO.API.QUERY.01 的 L4 测试记录」**（未命中意图模式），
步骤 2 会得到 `confidence=low / needs_clarification`，步骤 3 编排 fail-closed 拒绝展开。
这是 P0 修复的正确行为：**意图没被听懂，机器不往下走**。
范例选用能命中的措辞「实现 … 的测试代码」，正是为了展示"听懂后才自治"的对照。

## 可复算验证

```bash
bash examples/golden-walkthrough/run.sh > /tmp/a.log
bash examples/golden-walkthrough/run.sh > /tmp/b.log
diff /tmp/a.log /tmp/b.log   # 无差异
```

前提：账本与源码未变；`run = f(intent, target, ledger, registry, EXPERT_CARDS)`。
