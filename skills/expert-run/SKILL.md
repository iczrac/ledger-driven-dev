---
name: expert-run
description: |
  专家团自动编排：把路由结果沿交接链展开成逐跳专家契约、分类命令与一份人工批准包，
  默认 dry-run 零执行、零新判定权。人只在带 --approved-by 的写入点逐条批准。
  Triggers: "专家团执行", "自动编排", "全AI驱动", "自动跑完整流程", "交接链",
  "编排器", "谁来做下一步", "批准包", "expert run", "orchestrate", "auto orchestration"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.5.0"
  risk_level: read_only
  related_skills: [expert-route, intent-restate, agent-gate, ledger-upgrade, method-assets]
---

# 专家团自动编排器（Expert Run）

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。


`route_expert` 回答「该谁做」，`expert-run` 回答「这条交接链怎么落地」。
它把 P0 产出的 `route.handoff.chain` 展开成一份可执行分工：

```
人话意图 → (复述门) → route_expert → expert-run → 逐跳契约 + 分类命令 + 批准包
                                                        ↓
                                              人只在批准点 --approved-by
```

## 三条第一性原理

1. **零新判定权**：负责人、置信度、交接链、建议命令全部来自 `route_expert`；
   专家契约（skills/writes/EXPERT.md）来自同一份 `EXPERT_CARDS`。编排器只展开，不裁决。
2. **默认 dry-run、零执行**：不跑任何命令、不写任何文件、不碰账本。
   它产出的是「计划 + 批准包」，不是替人执行。
3. **权限授予者 ≠ 被授权者**：含 `--approved-by` / `--apply` / `register` /
   `unfreeze` 等写动作的命令一律归入批准包，只由人逐条执行。

## 命令分类（fail-closed）

| 类别 | 判据 | 处置 |
|---|---|---|
| `readonly` | 含 `--check` / `--diff` / `--json` / `--dry-run` / `verify` 等只读标志 | 可直接执行 |
| `approval` | 含 `--approved-by` / `--apply` / `register` / 写命令且无只读标志 | 人批准后执行 |
| `manual` | 无法判定（如内联 `python3 -c`） | 默认交人工，不自动执行 |

保守原则：宁可归 `approval`，也不把可能是写的命令判成只读。

## 用法

```bash
# 人类可读：看交接链与批准点
python3 scripts/expert_run.py --target P --intent "校验账本不变量"

# JSON：交给平台/Agent 消费批准包
python3 scripts/expert_run.py --target P --intent "校验账本不变量" --json

# 与复述门联动：先结构化意图，再编排（复述门来源仅作记录）
python3 scripts/expert_run.py --target P --intent-file intent.json --json
```

退出码：`0` ready（可进入人工批准）；`1` blocked / 需澄清（fail-closed，chain 为空）。

## fail-closed

路由未通过（元指令、多意图竞争、生命周期阻塞）时，`chain=[]`、批准包为空，
只给 `halt_reason`——不生成任何可执行动作，与复述门、场景预检同一纪律。

详见 [25-专家团自动编排](../../docs/25-专家团自动编排.md) 与
[12-专家路由](../../docs/12-专家路由.md)。
