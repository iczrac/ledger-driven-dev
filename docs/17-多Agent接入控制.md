# 17 · 多 Agent 接入控制：把「建议」变成「执行点」

## 一、为什么：声明的权限不是权限

v0.9.0 已经具备专家路由（7 个角色）、技能（12 个动作描述）、场景预检（14 项只读）和
CAS 指纹。看起来"多 Agent 协作"齐了。但把链路摊开会发现一个断点：

```
expert-route  ──建议──>  Agent
scenario_guard ──只读──>  Agent  （可以完全不调用）
EXPERT.md     ──散文──>  Agent  （靠"记得遵守"）
                          │
                          └──直接 python3 scripts/ledger_decide.py ──> 账本 ✗ 无人拦截
```

`ledger_decide.py` / `ledger_lesson.py` / `lifecycle.py` 各自实现「读 JSON → 改 → 写回」，
**没有身份、没有 CAS、没有生命周期检查、没有审计**。只要 Agent 有 shell，
纪律就是一句建议。第一性原理要求的是：

> 判定是否安全的逻辑，必须和写入动作处在同一个不可绕过的执行点。

所以补的不是「再加一个专家」，而是补一层 **策略执行点（PEP）**：
`scripts/agent_gateway.py`。同时把权限数据放进账本内 `access` 字段，
守住 A3 单点写入——不新建 `AGENTS.yaml`、权限表或独立审计日志。

## 二、机制：默认拒绝的九道门

每次请求按固定顺序判定，任一门 `deny` 就整体拒绝，不短路、不留半成品：

| # | 门 | 拒绝条件 | 对应公理 |
|---|---|---|---|
| 1 | `access_registry` | 账本没有 `access` 登记（未升级） | A5 |
| 2 | `known_action` | 动作不在 `ACTIONS` 白名单 | A5 |
| 3 | `agent_identity` | 未登记 / 已禁用 / 换 id 绕过 | A1 |
| 4 | `role_policy` | 角色无权执行该动作 | A3 |
| 5 | `scope_policy` | 能力编码超出该 Agent 的 `scopes` 前缀 | A3 |
| 6 | `cas_fingerprint` | 写入/许可类动作没带指纹，或指纹已漂移 | A4 |
| 7 | `registry_cas` | 依赖手写清单的动作没带 `registry_sha256`，或清单被改 | A3（F7） |
| 8 | `human_approval` | 解冻/归档缺人批准，或 Agent 自我批准 | A1 |
| 9 | `lifecycle_state` / `ledger_version` / `lease_free` / `revision` / `preflight` | 冻结归档、跨版本、他人持租约、revision 漂移、场景预检阻止 | A4/A5/A6 |

`preflight` 直接复用 `scenario_guard.collect()` + `evaluate()`，
不复制一份检查逻辑——证据新鲜度、退役冲突、陈旧任务锁、脱敏、模板漂移这些
**外部上下文**由 guard 回答，网关只负责把它的 `blocked_actions` 映射到本次动作。

### 账本内 `access` 结构（不是文件）

```json
{
  "schema": "access/1",
  "revision": 4,
  "agents": [
    {"id": "ci-agent", "role": "loop-executor", "enabled": true,
     "scopes": ["DEMO.API."], "registered_at": "...", "approved_by": "张三"}
  ],
  "leases": [{"code": "DEMO.API.QUERY.01", "agent": "ci-agent",
              "at": "...", "ttl_minutes": 120}],
  "audit": [
    {"seq": 1, "at": "...", "agent": "human:张三", "action": "register",
     "outcome": "applied", "fingerprint_before": "...", "fingerprint_after": "..."}
  ]
}
```

`revision` 每次写入 +1，让「只改 access、不改能力模型」这类不改变
`current_fingerprint` 的写入也可数、可检测。
`audit` 是 append-only：**许可与拒绝都留痕**，事件带前后指纹、registry 摘要、
批准人与理由。看板 EMBED 由 `ledger_io.write_ledger()` 同步，24 条不变量不破。

### 并发三重锁，各管一件事

| 锁 | 管什么 | 不管什么 |
|---|---|---|
| `fcntl.flock` on `.ledger-write.lock` | 读-判-写的原子性；等待后**锁内重读账本并重新判定** | 跨主机 |
| `current_fingerprint` CAS | 能力状态在 Agent 读取后被人改过 | 只改 `access` 的写入 |
| `access.leases` + `revision` | 两个 Agent 同时改同一能力编码；写入次数可回放 | 自动合并 `registry.json` |

### 角色最小权限（`ROLE_POLICIES`）

| 角色 | 可写账本 | 只签许可 |
|---|---|---|
| `loop-executor` | `claim` / `release` | `code` / `generate` |
| `ledger-steward` | `decide` / `lesson-*` / `retire` / `restore` / `claim` / `release` | `generate` |
| `release-steward` | `freeze` / `unfreeze` / `archive` | — |
| `evidence-auditor` | — | `verify` / `status` |
| `platform-steward` | — | `upgrade-plan` / `status` / `verify` |
| `expert-router` / 其余 | — | `route` / `discover` / `bootstrap` |

**`ledger-write` 动作由网关亲自调用既有纯函数**（`lifecycle.apply`、
`ledger_decide.decide`、`ledger_lesson.*`），不复制业务逻辑；
`permit-only` 动作只签发带指纹的许可，由底层工具用自己的 `--expect-fingerprint` 执行。
`check_definitions()` 强制校验所有写入型动作都落在网关白名单里，防止新增脚本偷偷绕过。

## 三、怎么用：接入一个 Agent 的完整流程

### 第 0 步：项目先升级（人批准）

```bash
python3 scripts/upgrade.py --target P plan --json
python3 scripts/upgrade.py --target P apply --approved-by 张三
# 按 plan.post_upgrade 的 19 步重新取证、核对资产副本/版面/预算/工作台并复验（见 16、18、19、21）
python3 scripts/agent_gateway.py --target P status --json
```

`status` 输出 `registry_sha256` 与 `current_fingerprint`，**这两个值是后续所有请求的票据**。
没有 `access` 登记时所有 `request` 一律 `deny`，提示先升级——这就是「升级 → 接入」的硬耦合。

### 第 1 步：人批准注册（Agent 不得自注册）

```bash
python3 scripts/agent_gateway.py --target P register \
  --agent ci-agent --role loop-executor --approved-by 张三 \
  --scope DEMO.API. --apply
```

`register` 默认 dry-run，必须 `--apply`；`--approved-by` 不得等于 `--agent`。
注册动作本身也写一条 `audit`。

### 第 2 步：Agent 平台只暴露一个写工具

把 [10-AI集成](10-AI集成.md) 的消费路径改成：

```
inject: experts/<role>/EXPERT.md 作为 system prompt
tools:  agent_gateway.py status / request         ← 唯一的写工具
        route_expert.py / scenario_guard.py       ← 只读工具
NOT exposed: ledger_decide.py / ledger_lesson.py / lifecycle.py（人工逃生舱）
```

### 第 3 步：每次写，先 dry-run 再 apply

```bash
FP=$(python3 -c "import json;print(json.load(open('P/governance/DECISION_LEDGER.json'))['capability_model']['history']['current_fingerprint'])")
RS=$(python3 scripts/agent_gateway.py --target P status --json | python3 -c "import json,sys;print(json.load(sys.stdin)['registry_sha256'])")

# 默认 dry-run：只判定，不写
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action claim --code DEMO.API.QUERY.01 --expect-fingerprint "$FP" --json

# 判定 allow 后才 apply
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action claim --code DEMO.API.QUERY.01 --expect-fingerprint "$FP" --apply --json
```

`agent-gate/1` 输出 `decision` / `denied_by` / `checks` / `permit` / `applied` / `audit`。
`deny` 时退出码 1，**不得换 id、换动作重试**——回到 `expert-route` 重新分派或请人裁决。

### 第 4 步：编码动作带许可执行

```bash
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action code --code DEMO.API.QUERY.01 --expect-fingerprint "$FP" \
  --expect-registry-sha "$RS" --json      # permit.kind = permit-only
# Agent 改 src/ 与 tests/ 后：
python3 scripts/run_tests.py --dir tests --out governance/test_report.json
cd P && python3 governance/build_capability_model.py --root . \
  --test-report governance/test_report.json --expect-fingerprint "$FP" --strict-evidence
```

生成器会保留 `access` 与 `governance_meta`（它原地更新账本对象，不重建顶层键），
因此网关审计不会被下一轮生成抹掉。这一步由 `check.sh` 的端到端阶段证明。

### 第 5 步：CI / 交接

```bash
bash scripts/check.sh                 # 含「升级与接入控制」端到端阶段
python3 scripts/agent_gateway.py --target P status --json   # 审计条数、租约、revision
```

## 四、接入后流程（"控制开发"落在哪几处）

```
人：升级批准 → 注册批准 → 冻结/解冻/归档批准
        ↓
Agent：status 取票据 → request dry-run → apply → 改代码 → 重跑报告
        ↓
网关：九道门 → 写入 + 租约 + audit + 看板同步
        ↓
门禁：verify_ledger 24 条 → scenario_guard → layout --diff → check.sh
        ↓
路由：重新 expert-route（状态可能已变），下一轮任务卡由 ledger-steward 分派
```

三个"控制点"是：
1. **谁能动**：`access.agents` + 角色表 + scopes，由人批准；
2. **能动什么**：`ACTIONS` 白名单 + 生命周期态 + 场景预检；
3. **动了之后怎么证明**：`audit` append-only + 双指纹 + `revision` + 看板同步。

## 五、边界与反模式（必须如实告知接入方）

- **策略执行点 ≠ 操作系统沙箱**。若 Agent 同时拿到 shell 和项目目录，仍可直接调用底层脚本。
  强隔离需要容器 / 只读挂载 / CI 只接受网关产物；本项目靠「工具注册白名单 + 门禁」约束，不是安全边界。
- **不自动合并 `registry.json`**：只做内容摘要检测（F7 从 `gap` 升为 `partial`），冲突仍由 git 人工裁决。
- **`fcntl` 是 POSIX**：Windows 上降级为「无 OS 级互斥 + 告警」，与 E6 一致；跨主机分布式锁超出范围。
- **不替人决定优先级、不自动重试 flaky、不持有外部凭据**，沿用 v0.8.0 的 `by-design` 边界。
- **monorepo 多项目 / 跨仓联合门禁（E7）** 仍是 `gap`：每个项目各自 `governance/`，没有 workspace 层。
- 反模式：把 `register` 交给 Agent 自己执行；为图方便不传 `--expect-fingerprint`；
  `deny` 后换一个 agent id 重试；把 `access` 复制成 `AGENTS.md`；
  在 `governance/` 新建审计日志文件；手改 `audit` 或 `revision`。

## 六、关联

- [16 升级与迁移](16-升级与迁移.md) —— 建立 `access` 登记的前置流程与升级后 SOP
- [12 专家路由](12-专家路由.md) —— `platform-steward` 负责升级规划与接入登记协调
- [14 场景矩阵](14-场景矩阵.md) —— F7、G1/G2/U1/U2 的探针与残差
- [10 AI 集成](10-AI集成.md) —— 专家 / 技能资产清单与平台注入方式
- `scripts/agent_gateway.py`（`agent-gate/1`）、`scripts/ledger_io.py`（唯一账本落盘原语）
