---
name: intent-restate
description: |
  复述门：在专家路由之前，把一句模糊的人话意图变成结构化声明并用真实 registry/账本校验，
  冲突或无法锚定时要求澄清，不让没听懂的意图静默进入路由。
  Triggers: "复述", "复述门", "意图对齐", "先确认再动手", "我没听懂", "意图校验",
  "restate", "intent gate", "clarify before routing"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.4.0"
  risk_level: read_only
  related_skills: [expert-route, scenario-guard, ledger-guard]
---

# 复述门（Intent Restate）

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 专家路由与资产/账本校验走唯一入口：`python3 scripts/ledger_entry.py --intent "任务描述"` 或 `--check-all`；任一门禁失败即退出码 1（fail-closed）。
- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。


路由脚本会把「让专家团接管全流程」这类编排指令判成 `intents=[]`，然后照常路由——
**意图没被听懂，机器却往下走了**。复述门补上「人话 → 复述确认 → 意图 → 路由」之间
缺的一环，是路由之前的只读门禁。

## 第一性原理

1. **声明权 ≠ 伪造权**：Agent 的复述只是声明，必须机器校验能锚定回真实证据才放行。
2. **可复算**：`结论 = f(intent.json, registry, 账本)`；同输入必得同输出。
3. **fail-closed**：任何字段无法锚定到真实条目就停下来问人，不猜、不静默继续。
4. **不写盘**：只读校验，不改 registry / 账本 / 源码。

## 输入契约：intent.json

```json
{
  "schema": "intent-restate/0",
  "raw_intent": "用户原话",
  "restatement": "用 agent 自己的话复述的底层目标（不得逐字照抄）",
  "intents": ["code"],
  "capabilities": ["PROJ.MODULE.DOMAIN.NN"],
  "write_scope": ["docs/test_records/**"],
  "open_questions": []
}
```

- `intents`：合法集合 `new/adopt/verify/plan/code/lesson/route/archive/migrate/access/retire/resume/meta`。
  `meta` 表示编排类指令（不指向具体能力），必须带 `open_questions`。
- `capabilities`：每个 code 必须能在 registry 或账本 `capability_model` 中锚定。
- `write_scope`：合法写入范围；只读意图（`verify/route/meta`）必须为 `["none"]`。

## 输出契约：intent-restate/0

```
verdict: allow | need_clarification | reject
checks: [{id, status, reason, fix}, ...]
```

退出码：`0=allow` / `1=need_clarification` / `2=reject` / `3=用法错误`。

## 八道校验

| id | 判定 |
|---|---|
| `schema` | schema 版本匹配 |
| `restate_nonempty` | 复述非空且非原话照抄 |
| `intent_valid` | 意图在合法集合 |
| `cap_anchored` | 能力 code 锚定真实条目（防幻觉） |
| `scope_valid` | 写入范围合法 |
| `readonly_no_write` | 只读意图不声明写入 |
| `intent_unambiguous` | 无多业务意图竞争 |
| `meta_disclosed` | 元指令须带开放问题、须人确认 |

## 用法

```bash
# 独立校验
python3 scripts/intent_restate.py --target . --intent-file intent.json --json

# 作为路由前置（route_expert 检测到 --intent-file 时自动先跑本门）
python3 scripts/route_expert.py --target . --intent-file intent.json --json
```

## 工作流

```
人话 → Agent 结构化复述(intent.json) → 复述门机器校验
  ├─ allow               → 进入 expert-route 正常路由
  ├─ need_clarification  → 把 checks[].fix 抛给人，补 intent.json 重来
  └─ reject              → 锚定失败/幻觉，停止，禁止路由
```

## 纪律

- 禁止为了让门变绿而手改 `capabilities` 填不存在的 code——那正是伪造。
- 禁止把多个竞争意图塞进一个 `intents` 数组蒙混——必须让人明确唯一目标。
- 门通过不等于业务正确，只说明意图被结构化且可锚定。
- 本技能只读；任何写入意图都经 agent-gate 与人批准。

详见 [24-复述门](../../docs/24-复述门.md) 与 [12-专家路由](../../docs/12-专家路由.md)。
