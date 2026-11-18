---
name: ledger-upgrade
description: |
  治理骨架升级：只读计划、带清单备份、人批准应用、只读复验、升级后重新取证与回滚。
  输出 upgrade-plan/1 / upgrade-apply/1 / upgrade-verify/1，回答「怎么升级、升级后要做什么」。
  Triggers: "升级", "版本迁移", "工具副本漂移", "治理骨架升级", "回滚升级",
  "升级后流程", "重新取证", "upgrade", "migrate", "rollback", "method_version"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.5.0"
  risk_level: write_with_approval
  related_skills: [agent-gate, scenario-guard, ledger-verify, layout-inspect,
                   board-layout, scale-budget, method-assets,
                   asset-install, test-map, work-panel]
---

# 治理骨架升级（ledger-upgrade）

## 输入 / 输出契约

| 命令 | 输入 | 输出 | 副作用 |
|---|---|---|---|
| `plan` | `--target P [--source-root R] [--json]` | `upgrade-plan/1`：版本六轴、迁移列表、工具/资产/骨架状态、blocks、risk、`post_upgrade` | **无**（只读、确定性） |
| `apply` | `--target P --approved-by <人> [--json]` | `upgrade-apply/1`：backup id、迁移 id、批准人 | 备份 + 加字段 + 同步工具 + 骨架归一 + 账本/看板写入 |
| `verify` | `--target P [--json]` | `upgrade-verify/1`：11 项 checks、`upgrade_complete` | **无** |
| `rollback` | `--target P --backup-id <id> --approved-by <人>` | `upgrade-apply/1`：已恢复文件清单 | 从备份还原 + 追加日志 |
| `check` | `--source-root R` | 定义自检结果 | **无** |

退出码：`plan` 有 block → 2；`apply`/`rollback` 被拒 → 1；`verify` 有 block → 2；其余 0。

## 版本六轴

| 轴 | 位置 | 说明 |
|---|---|---|
| `method_version` | `governance_meta.method_version` | 方法论/工具链版本，如 `1.2.0` |
| `ledger_version` | 账本顶层 | 数据契约，只接受 `1.0`；不兼容时 fail-closed，不自动迁移 |
| tool hashes | `governance_meta.tools` | 3 个 `governance/*.py` 副本的 sha256 |
| method assets | `governance_meta.method_assets` | 专家 / 技能 / 路由 / 模板 / 文档整包摘要；随仓库 tag 升级 |
| board skeleton | `governance_meta.board_skeleton` | 去 EMBED 后的看板骨架 sha256；统一 CSS/DOM/JS |
| installed assets | `governance_meta.installed_assets` | `.workbuddy/` 内 28 份只读副本的逐文件摘要；手改即判 drift |

M8 另外初始化两个账本内字段：`work_items` / `test_results`（见 `work-panel` 技能）。

## 步骤（六阶段，顺序不可换）

1. **PLAN**：`upgrade.py --target P plan --json`。看 `blocks`、`risk`、3 个 `tools[].state`、
   `assets`、`board` 与 `installed`（missing / drifted / stale_protected）。
   有 block 就停，按 `fix` 处理；不要 `--force`（不存在这个开关）。
2. **ASK**：把计划摘要、`risk` 与 `--approved-by` 交给人。**AI 不得代填批准人**。
3. **APPLY**：`upgrade.py --target P apply --approved-by <人>`。
   先在 `P/.ledger-upgrade/backups/<id>/` 写清单备份，再按 M1→M8 加字段、同步工具、
   用模板归一骨架（M6 的 index.html 也在备份里）、装只读资产副本（M7）、
   初始化工作台字段（M8）。M7 的安装产物也纳入备份清单，回滚只移除升级前不存在的副本。
4. **VERIFY**：`upgrade.py --target P verify --json`。11 项检查中任一 `warn` 都不得宣布成功。
5. **RE-BASELINE**：逐条执行 `post_upgrade` 的 18 步。核心是**先重跑测试报告，
   再用 `--strict-evidence` 重新生成账本**；随后补 `board_contract` / `scale_budget` /
   `method_assets` / `asset_bundle verify` / `work_panel check` / `test_modules --check` /
   `route_expert --check-assets` 七项契约核对。顺序反了会把过期报告当 `verified`。
6. **AUDIT**：核对 `governance_meta.upgrade_log` 末条、`access` 登记、
   `agent_gateway.py status` 与 `bash scripts/check.sh`；交回 `expert-router` 重新分派。

## 失败处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `unsupported_ledger_version` | 数据契约不兼容 | 导出快照 + 写专用数据迁移 + 人确认；本脚本不猜结构 |
| `lifecycle_not_writable` | 冻结/归档 | 人批准 `unfreeze`；归档项目复制新项目 |
| `future_method_version` | 账本来更新版本方法论 | 升级本仓库，不要降级写新账本 |
| `tool_hashes` warn | 副本漂移 | 重新 `apply` 同步模板 |
| `evidence_rebaseline` warn | 工具源码变了，`evidence_binding` 失配 | 重跑 `run_tests.py` → 生成器 `--strict-evidence` |
| `method_assets` warn | 专家/技能/模板/文档发了新版，项目仍记旧摘要 | 重新 `plan` → 人批准 `apply`（M5） |
| `board_skeleton` warn | 项目改过 CSS/DOM 或用旧模板 | `board_contract.py check` → `apply`（M6）归一，禁止手改 |
| `installed_assets` warn | 副本被手改 / 删除 / 仍是旧版本 | `asset_bundle.py verify --target P --json` 定位 → 重新人批准安装（M7）；禁止在项目里直接编辑 |
| `work_panel` warn | `work_items` 非法或测试投影脱离报告 | `work_panel.py --target P check --json` → `sync-tests --apply --approved-by <人>` |
| 升级后发现改错了 | — | `rollback --backup-id <id> --approved-by <人>`，再跑 VERIFY 与 RE-BASELINE；回滚会把骨架一并恢复，需重新升级 |

## 纪律

- 迁移只允许加字段；`current_fingerprint` 不变，因此**不会追加历史事件**。
- 升级与接入硬耦合：`M2` 建立默认拒绝的 `access` 登记；没有它，网关拒绝一切 Agent 请求。
- `noop` 表示已是当前版本且工具一致，不备份、不写日志、不写盘——幂等是设计，不是异常。
- 不新建 `UPGRADE_LOG.md`；`upgrade_log` 是账本内 append-only 字段。
- `warn` 不等于成功：`upgrade_complete` 要求版本 / 工具 / 接入登记 / 资产 / 骨架 /
  已安装副本 / 工作台 / 证据**八项**全 pass。
- 专家与技能的**权威源**不进目标项目目录，M7 装的是只读部署副本；
  两层绑定见 `method-assets` / `asset-install` 技能。

详见 [16-升级与迁移](../../docs/16-升级与迁移.md)、[17-多Agent接入控制](../../docs/17-多Agent接入控制.md)
与 [18-规模化与版面契约](../../docs/18-规模化与版面契约.md)、
[19-专家与技能可用](../../docs/19-专家与技能可用.md)、[20-测试架构与模块映射](../../docs/20-测试架构与模块映射.md)、
[21-节点工作台与看板视图](../../docs/21-节点工作台与看板视图.md)。
