---
name: scenario-guard
description: |
  写入前场景预检：检查账本版本契约、冻结/归档状态、证据新鲜度、并发指纹(CAS)、
  能力退役冲突、任务锁、路径脱敏、git 完整性与扫描截断，输出允许/禁止动作清单与专家提示。
  Triggers: "场景预检", "现在能不能写", "冻结了吗", "证据过期", "并发写入",
  "读后写漂移", "版本兼容", "preflight", "scenario guard", "CAS"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.7.0"
  risk_level: read_only
  related_skills: [ledger-verify, ledger-guard, expert-route, graph-compare]
---

# 场景预检（scenario-guard）

## 输入 / 输出契约

| 项 | 说明 |
|---|---|
| 输入 | `--target P`；可选 `--expect-fingerprint FP`、`--test-report R`、`--max-files N`、`--stale-minutes N`、`--json`、`--strict` |
| 输出 | `scenario-preflight/1`：facts、14 项 checks（pass/warn/block）、`allowed_actions`、`blocked_actions`、`route_hint` |
| 副作用 | **无**。只读，不写账本、不写看板、不改源码 |
| 退出码 | 0 = 可读；2 = 输入错误，或 `--strict` 下存在 block |

## 与 verify 的分工

- `verify_ledger.py` → 账本**内部**自洽（24 条不变量），打包一个账本文件就能验。
- `scenario_guard.py` → **外部 / 时间 / 并发 / 生命周期**前置条件，需要当前源码与当前状态。
- 顺序：**先 guard 再 verify 再写入**。只跑 verify 就写入，会漏掉冻结、并发漂移、过期证据。

## 检查项（14）

| id | 公理 | block 时阻止什么 |
|---|---|---|
| `ledger_parseable` | A5 | 所有写动作 |
| `schema_compat` | A5 | 跨版本直写 |
| `lifecycle_writable` | A6 | 冻结/归档期间写动作 |
| `approval_gate` | A1 | 缺批准人时告警 |
| `evidence_bound` | A2 | 未绑定源码的报告不得声称 verified |
| `evidence_fresh` | A2 | 过期报告不得声称 verified |
| `concurrent_write` | A4 | 指纹漂移时禁止 generate/decide/code/lifecycle |
| `retired_caps_consistent` | A1 | 退役编码仍活跃时禁止 generate |
| `execution_resumable` | A4 | 超时任务锁告警 |
| `board_synced` | A3 | 看板漂移告警 |
| `git_history` | A4 | 无 git / 浅克隆告警 |
| `path_hygiene` | A5 | 绝对路径泄露时禁止写入 |
| `template_sync` | A5 | 模板漂移告警 |
| `scan_complete` | A5 | 扫描截断时禁止声称全量 |

## 步骤

1. 读账本 `capability_model.history.current_fingerprint` 作为 CAS 基准。
2. `python3 scripts/scenario_guard.py --target P --expect-fingerprint "$FP" --strict`。
3. 任一 `block` → 按 `fix` 修复，回到第 1 步；**不要跳过**。
4. 全绿后调用 `route_expert.py` 确认负责人，再执行 `allowed_actions` 里的动作。
5. 写入类命令带上同一份指纹：
   `build_capability_model.py --root . --expect-fingerprint "$FP" --strict-evidence`。

## 失败处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `concurrent_write` block | 读后有人写过 | 重新读取账本、合并变更、换指纹重试；不要 `--force` |
| `evidence_fresh` block | 报告生成后源码变了 | 重跑 `run_tests.py` 再生成账本 |
| `lifecycle_writable` block | 冻结 / 归档 | 冻结：人工批准解冻；归档：复制新项目 |
| `retired_caps_consistent` block | 退役能力仍在 registry | 人工从 registry 移除后重跑生成器 |
| `path_hygiene` block | 账本残留绝对路径 | 归一为相对路径，重新生成 |

## 纪律

- guard 永远只读；任何「顺手修一下」的请求都转给对应专家。
- 不把 `warn` 当 `pass`：warn 表示能力降级，必须在交接卡里写明残差。
- 不提供 `--force` 之类的绕过开关；fail-closed 没有例外通道。
- 场景定义改动后跑 `python3 scripts/scenario_matrix.py --check` 并重生成矩阵文档。

详见 [14-场景矩阵](../../docs/14-场景矩阵.md) 与 [08-可信性校验](../../docs/08-可信性校验.md)。
