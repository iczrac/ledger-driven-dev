# 升级前后观察 diff —— 目标项目重绑至 v1.5.0

> 本文件是**升级现场证据**，由 `ledger_feedback.py export` 的两个只读快照对比生成，
> 不参与门禁计数，也不是第二事实源。观察内容已匿名化。

## 执行链

| 步 | 动作 | 证据 |
|---|---|---|
| 1 | `PRE_UPGRADE` 基线导出 | `feedback/baseline.jsonl`（phase=`baseline`，12 条，method_version `1.2.1`） |
| 2 | 人批准 `upgrade.py apply` | 备份 `20261118T072013Z-ad0f73f7`；迁移 M3 / M4 / M5 / M7；`1.2.1 → 1.5.0` |
| 3 | `upgrade.py verify` | 12 项：11 pass / 1 na / 0 warn / 0 block，`upgrade_complete=true` |
| 4 | 升级后复验 | 三态不变量 23 pass + 1 na；10/10 看板视图渲染；4 项目 / 47 能力 / 3 工作项 |
| 5 | 复导 | `feedback/post-v150.jsonl`（phase=`after-upgrade`，15 条 = 12 自动 + 3 现场 note，method_version `1.5.0`） |
| 6 | diff + triage | 见下 |

**刻意改写的一处流程**：`POST_UPGRADE` 第 19 步把复导直接写回
`feedback/observations.jsonl`，而 `export --out` 是覆盖写。按字面执行会抹掉既有
13 条观察包中的 4 条已收敛证据。本次改用独立文件，既有观察包 sha256 前后一致
（`e0b313efab94a4c7`），未受影响。

## 严格 diff（排除 3 条人工 note）

- **消失 2 条 —— 升级治愈**
  - 目标项目校验器仍是两态语义、未启用项被记成通过 → 已在基线包 triage 为
    `invariant: templates/verify_ledger.py`
  - 方法版本落后于权威源 → 已在基线包 triage 为 `migration: scripts/upgrade.py`
- **新增 2 条 —— 升级后变得可见**
  - 校验项 `test_results_binding_valid` 状态 `na`（未启用投影被诚实呈现）
    → triage 为 `wontfix`：这是三态设计语义，不是失败
  - 本次迁移日志 `1.2.1 → 1.5.0`（append-only 事实，非缺陷）
- **持续 10 条 —— 不由本次升级解决**，作为 v1.6.0 / v2.0.0 处方：
  多项目契约、实测报告绑定、能力等级仍 `declared`、接入名册未激活、
  生命周期未登记、激活状态占位缺失、经验候选未确认、两条历史迁移日志。
  其中 E7 已由 v1.5.0 本体公理 A4 **命名**为 `cardinality_contradiction`
  并 triage 为 `regression: tests/meta/test_ontology.py`，但数据形状迁移仍需人批准。

## 三条升级现场新摩擦（保持 open）

1. `POST_UPGRADE` 第 19 步覆盖写语义会销毁既有 triage 证据，应改为追加 / 合并。
2. 第 1 / 2 / 15 步对「多项目 + 无实测报告」目标项目不可安全执行：目标项目
   没有 `tests/` 目录、没有 `test_report.json`，`sync-tests` 直接拒绝；
   v1.3.0 已提供 `import-report` 适配器，但流程本身未条件化。
3. M8 未触发时 `activation` 占位仍缺失：已有工作项但无报告的项目不写入该字段，
   只能靠 `evidence_rebaseline=na` 表达未启用。

## 复核发现：资产正文漂移（不落观察包，留 v1.6.0）

升级后复核确认：权威源里 `skills/ledger-upgrade/SKILL.md`、`skills/agent-gate/SKILL.md`、
`experts/platform-steward/EXPERT.md` 与 6 份 `docs/*.md` 正文仍写「版本六轴 / 18 步 /
11 项 checks / 八项判据」，而 `upgrade.py` 实际是 **七轴 / 1 步 pre + 19 步 post /
12 项 checks / 九项判据**。部署副本与权威源逐字节一致，所以问题在权威源本身：
历次发版只批量更新了 frontmatter 的 `version`，没有同步正文。

**本轮刻意不修**：改任一资产字节会改变 `method_assets` 的 84 文件摘要，使刚绑定的
`0bd06f8274e…` 立刻漂移，进而要求重新人批准 M5 + 重装 M7 + 再次复验，形成升级半途的
二次写盘。按「先定版本、再动权威源」的纪律，留作 v1.6.0 首条处方：
批量校正正文计数，并把「正文数字 vs 代码常量」做成门禁断言。

未写进 `post-v150.jsonl` 的原因：重新导出是覆盖写，会抹掉该文件里已完成的 triage 状态。

## 明确跳过的步骤与理由

| 步 | 命令意图 | 跳过理由 |
|---|---|---|
| 1 | 目标项目 `run_tests.py --dir tests` | 目标项目无 `tests/` 目录，且技术栈非标准库 unittest；空报告会被判 `overall=fail` |
| 2 | 生成器 `--strict-evidence` 重算账本 | 单项目 `registry` 契约会把派生模型 4 个项目压成 1 个（E7）；数据迁移留 v2.0.0 人批准 |
| 15 | `work_panel sync-tests --apply` | 无 `test_report.json`，dry-run 已明确拒绝；须先由 `import-report` 导入 CI 报告 |

其余 16 步（契约核对、场景预检、文件布局、接入名册状态、专家路由、资产副本、
工作台、测试架构、本体绑定、看板渲染）均已执行通过。

## 闭环结果

| 观察包 | 总数 | open | closed | 四产物收敛 |
|---|---:|---:|---:|---:|
| `baseline.jsonl` | 12 | 10 | 2 | 2 |
| `post-v150.jsonl` | 15 | 13 | 2 | 1 |
| `observations.jsonl`（既有，未改） | 13 | 9 | 4 | 4 |

相关文档：[22 · 反向回流](../docs/22-反向回流.md)、[23 · 本体投影](../docs/23-本体投影.md)、
[16 · 升级与迁移](../docs/16-升级与迁移.md)。
