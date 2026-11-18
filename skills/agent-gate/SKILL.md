---
name: agent-gate
description: |
  多 Agent 接入网关：默认拒绝的身份、角色、scopes、CAS 指纹、registry 摘要、租约、
  人批准门与 append-only 审计。让不同 Agent 只能经唯一写入口控制开发。
  Triggers: "接入 Agent", "注册 Agent", "多 Agent", "权限", "越权", "并发写入",
  "谁能改账本", "审计", "租约", "agent gate", "access control", "register agent"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.8.0"
  risk_level: policy_enforcement
  related_skills: [ledger-upgrade, expert-route, scenario-guard, ledger-verify]
---

# 多 Agent 接入网关（agent-gate）

## 输入 / 输出契约

| 命令 | 输入 | 输出 | 副作用 |
|---|---|---|---|
| `status` | `--target P [--json]` | `agent-gate/1`：access schema、agents、leases、审计条数、`registry_sha256`、`current_fingerprint` | **无** |
| `register` | `--agent id --role r --approved-by <人> [--scope PREFIX] --apply` | 登记结果 | **需人批准**；加一条 audit |
| `request` | `--agent id --action a [--code C] --expect-fingerprint FP [--expect-registry-sha S] [--apply]` | `agent-gate/1`：decision / checks / permit / applied / audit | 默认 dry-run；`--apply` 才写 |
| `check` | — | 角色与动作定义自检 | **无** |

退出码：allow → 0；deny → 1；定义自检失败 → 2。

## 九道门（按顺序，任一 deny 即整体拒绝）

```
access_registry → known_action → agent_identity → role_policy → scope_policy
→ cas_fingerprint → registry_cas → human_approval
→ lifecycle_state / ledger_version / lease_free / revision / preflight
```

`preflight` 复用 `scenario_guard.collect()+evaluate()`，把 `blocked_actions` 映射到本次动作。
`registry_cas` 是 F7 的**检测**：手写清单改过就拒绝，但仍由 git 人工合并，不自动合并。

## 接入流程

```bash
# 0) 前置：项目必须已升级（access 登记由 M2 建立）
python3 scripts/upgrade.py --target P plan --json
python3 scripts/upgrade.py --target P apply --approved-by <人>
# 按 post_upgrade 的 19 步重新取证、核对资产/版面/预算并复验

# 1) 取票据
python3 scripts/agent_gateway.py --target P status --json
FP=<status.current_fingerprint>   RS=<status.registry_sha256>

# 2) 人批准注册（Agent 不得自注册，--approved-by 不得等于 --agent）
python3 scripts/agent_gateway.py --target P register \
  --agent ci-agent --role loop-executor --approved-by <人> --apply

# 3) 先 dry-run，再 apply
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action claim --code DEMO.API.QUERY.01 --expect-fingerprint "$FP" --json
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action claim --code DEMO.API.QUERY.01 --expect-fingerprint "$FP" --apply --json

# 4) 编码类动作只签许可，由底层工具带同一指纹执行
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action code --code DEMO.API.QUERY.01 --expect-fingerprint "$FP" \
  --expect-registry-sha "$RS" --json
```

## 平台注入约定

```
inject : experts/<role>/EXPERT.md 作为 system prompt
tools  : agent_gateway.py status/request（唯一写工具）
         route_expert.py / scenario_guard.py（只读工具）
NOT    : ledger_decide.py / ledger_lesson.py / lifecycle.py（人工逃生舱，不暴露给 Agent）
```

## 角色权限速查

| 角色 | 网关亲写 | 只签许可 |
|---|---|---|
| `loop-executor` | claim / release | code / generate |
| `ledger-steward` | decide / lesson-* / retire / restore / claim / release | generate |
| `release-steward` | freeze / unfreeze / archive | — |
| `evidence-auditor` / `platform-steward` / `expert-router` | — | verify / status / upgrade-plan / route |

`unfreeze` / `archive` 必须 `--approved-by <人>`，且不得等于 `--agent`。

## 失败处理

| denied_by | 处理 |
|---|---|
| `access_registry` | 先跑 `ledger-upgrade` 的 apply（人批准） |
| `agent_identity` | 请人 register；**不要换 id 重试** |
| `role_policy` / `scope_policy` | 回 `expert-route` 重新分派，不借用他人身份 |
| `cas_fingerprint` / `revision` | 重新读账本取新指纹，合并变更后再请求 |
| `registry_cas` | 重读 `registry.json`，用 git 人工合并冲突 |
| `lease_free` | 等对方 `release`，或由人清理超时租约 |
| `human_approval` | 向人要批准人姓名 |
| `lifecycle_state` / `ledger_version` / `preflight` | 按对应 `fix` 处理，无 `--force` 通道 |

## 纪律

- `deny` 后**不得**换 agent id / 换动作 / 直接调底层脚本绕过；回路由重新分派。
- 许可与拒绝都写 `access.audit`（append-only）；`revision` 每次写入 +1。
- 账本 + 看板 EMBED 由 `ledger_io.write_ledger()` 一起写，24 条不变量不破。
- 网关是**策略执行点，不是 OS 沙箱**：有 shell 的 Agent 仍可绕过，强隔离靠容器 / 只读挂载 / CI 白名单。
- 不新建 `AGENTS.yaml` / 独立审计日志；不手改 `audit` 或 `revision`。

详见 [17-多Agent接入控制](../../docs/17-多Agent接入控制.md) 与 [16-升级与迁移](../../docs/16-升级与迁移.md)。
