# DELIVERY 2.7.0 — 真实自举 + 看板接本体：让账本重新等于真实开发历史

- 版本：v2.7.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过，全量门禁 EXIT=0；主项目推广待用户另行确认（只在干净 clone 操作）

## 一、为什么做这一版

一次只读检查问了三个问题，答案都是"没有"：

1. **账本记录了 v2.4/2.5/2.6 三次发版吗？** 没有——entries 只有 1 条初始化决策。
2. **方法仓走过自己的 M1-M8 升级迁移吗？** 没有——无 `governance_meta`，`upgrade plan` 显示 `pre-1.0.0 → 2.6.0`。
3. **看板术语来自本体投影吗？** 没有——「术语与实现」是模板写死的 21 条概念，本体 11 条术语无人消费。

根因：v2.4～v2.6 只改代码与文档（`git show --stat` 可证未碰 governance），
沿用"元工具不算能力点"口径把它们排除在 registry 外。没进 registry，
生成器就无从纳入；账本不重算，就留不住真实开发历史。
**方法论仓库没有用自己生产的账本开发自己**——这是最该先修的自举断链。

## 二、改了什么

### A · 补自举三层（账本 = 真实开发历史）

- **决策层**：补录 v2.4.0 / v2.5.0 / v2.6.0 三条 `status=done` 决策，证据指向真实
  CHANGELOG / 交付卡 / 实现脚本；走 `ledger_io.write_ledger` 唯一写入口，
  append-only，不碰生成器维护的 `history.events`。
- **绑定层**：`upgrade apply --approved-by user-approved-A2B` 补齐 `governance_meta`
  的版本轴绑定字段——`method_version=2.7.0` / `method_assets` / `board_skeleton` /
  `installed_assets` / `ontology_digest`（与权威本体 `fb48a6a6…` 一致）。非手填，升级引擎生成。
- **能力层**：三个新元工具登记为能力点 `METHOD.GOV.RESTATE.08` / `ORCH.09` / `ANNOT.10`，
  测试静态 import 实现 → bound → verified。能力模型 **7→10**：
  9 verified + 1 declared（BINDING.07 负向探针诚实保留，不为凑满伪造绑定）。
  `账本 = f(registry, 仓库, 报告)` 逐字段可复算（`--check` 通过）。
- **守门测试** `tests/meta/test_dogfood.py`（6 条）锁定三层，先红（5 fail）后绿（6/6）。

### B · 看板术语接本体（并列，不替换）

- 本体 `ubiquitous_language`（status/level/severity…）是**机器分型词表**，
  看板 GLOSSARY（决策账本/能力点/可复算…）是**人读概念解说**——语义层次不同，
  拿前者顶替后者是错的。做法是在术语视图**并列展示两个来源**。
- 权威模板新增第二数据段 `const ONTO_TERMS = [...]; let ONTO_DATA`（与 EMBED 同范式）；
  `board_contract.normalize` 从 `docs/generated/ONTOLOGY.json` 注入 11 条术语，
  骨架摘要归一化该段——本体内容变化不触发骨架漂移，老看板无该段也兼容。
- 术语视图新增「本体投影词表」区，标注"机器派生，改权威源后重算"。
  `ledger_io.sync_board` 只替换 EMBED、不碰本体段——两写入口职责分离，无冲突。
- 方法仓 + 示例看板骨架统一归一（digest `ba37cd40…`），随 M6 迁移推送。

### 配套门禁修正

- `check.sh` 卫生阶段内链检查跳过 `.workbuddy/`（安装副本）与 `.ledger-upgrade/`（备份）：
  这些是只读派生/历史产物，相对链接按目标项目语境解析，不能拿权威源口径要求它们。
  方法仓自举装了 `.workbuddy` 后若不修，会让自己门禁误报失效链接。

## 三、实证与关键数字

- 守门测试：改前 5 fail（无 governance_meta / 无三条发版决策 / 无 ONTO_TERMS），实现后 6/6 全绿。
- 能力模型：7→10 能力点，9 verified + 1 declared，evidence_bound=true / fresh，
  `--check` 逐字段可复算（含派生 issue）。
- 报告可信度：新测试文件必须先 `git add` 入库，否则 freshness 拒绝采信、
  verified 全回落 declared——fail-closed 正确行为，自举必须付的代价。
- 全量门禁：16 阶段 EXIT=0、377 单测（v2.6 是 371，+6 守门测试）、27 不变量绿。
- 升级链：方法仓 `upgrade apply` M1-M8 + 一次 M5 摘要重绑，`verify` upgrade_complete=true。

## 四、守住的纪律

- **不造第二事实源**：本体术语以 `ONTOLOGY.json` 为权威，看板只是展示投影；
  `ontology_digest` 只存摘要不复制内容；自举决策 append-only 不碰能力指纹链。
- **破坏性动作经人批准**：`upgrade apply` / `board normalize` 均带 `--approved-by`，
  写盘前自动备份到 `.ledger-upgrade/backups/`。
- **诚实 > 绿灯**：BINDING.07 仍 declared/unbound；`upgrade verify` 不通过就不宣布完成。
- **用户工作区不碰**：主仓 100 个既有改动全程未动，本版只在方法仓发版。

## 五、后续

主仓推广（v2.4～v2.7 整包升级）待用户确认——只在干净 clone 操作，`apply` 需 `--approved-by`。
相关：[27-自举闭环](../docs/27-自举闭环.md)、
[23-本体投影](../docs/23-本体投影.md)、
[26-来源投影](../docs/26-来源投影与完成定义.md)。
