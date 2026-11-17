---
name: board-layout
description: |
  看板骨架契约：以 templates/index.html.template 为唯一权威，校验并归一化治理看板的
  CSS / DOM / JS，防止不同项目出现差异化版面；数据段 EMBED 仍由账本同步。
  Triggers: "看板样式", "版面差异", "骨架漂移", "改 CSS", "HTML 模板", "统一版面",
  "分页渲染", "board layout", "board-contract", "style drift"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.2.0"
  risk_level: read_only_with_approved_repair
  related_skills: [ledger-upgrade, layout-inspect, ledger-verify, scale-budget]
---

# 看板骨架与统一版面（board-layout）

## 输入 / 输出契约

| 命令 | 输入 | 输出 | 副作用 |
|---|---|---|---|
| `check` | `--target P [--json]` | `board-contract/1`：模板摘要、项目摘要、layout 事实、漂移原因 | **无**（只读） |
| `normalize` | `--target P --apply --approved-by <人>` | `board-normalize/1`：归一化前后摘要、备份路径 | 用模板骨架重建 `governance/index.html` |
| `template-digest` | `--target P`（占位） | 权威模板骨架摘要 | **无** |

退出码：`check` 漂移 → 1；`normalize` 缺批准人 / 模板损坏 → 2；其余 0。
`normalize` **默认 dry-run**，必须同时给 `--apply` 与 `--approved-by`。

## 骨架摘要怎么算

把 HTML 中 `const EMBED = {...};\nlet DATA` 替换为固定占位符，对剩余**全部字节**
取 sha256。于是：

- 账本数据变化 → 摘要不变（数据由 `board_embed_synced` 不变量管）；
- CSS 改一行、删一个 tab、改一处 JS → 摘要必变；
- 摘要写进账本内 `governance_meta.board_skeleton`，**不新建项目文件**。

模板里 `const PAGE_SIZE=200` 是统一分批渲染上限：全部条目 / 待裁决 / 工作台 /
工作项 / 时间线 / 模块地图 / 架构钻取 / 能力地图 / 演进历史 / 经验库**十个视图**
都按它截断并给「显示更多」；节点工作条是卡片内聚合，不额外生成卡片。
`scale_budget.py` 直接解析该常量，避免预算口径与渲染实现漂移。

## 步骤

1. **CHECK**：`board_contract.py --target P check --json`。看 `match`、`layout.missing_ids`、
   `style_bytes`；漂移时读 `reason`。
2. **判定来源**：若 `template_digest` 与项目摘要不同，说明项目改过版面或用了旧模板；
   **不要在项目里手工补 CSS 追平**，那只会产生第二套版面。
3. **ASK**：把归一化会覆盖 `index.html` 骨架（但保留账本数据）告诉人，取得批准人姓名。
4. **REPAIR**：优先走升级流程 `upgrade.py --target P apply --approved-by <人>`，
   由 M6 统一备份并归一；独立修复才用
   `board_contract.py --target P normalize --apply --approved-by <人>`。
5. **VERIFY**：重跑 `check` + `upgrade.py verify --json` + `verify_ledger.py --strict`，
   确认骨架一致且 EMBED 仍与账本等价。
6. **AUDIT**：`governance_meta.board_skeleton.digest` 应等于模板摘要。

## 纪律

- 要换样式：**改方法论模板 → 发 tag → 所有项目经升级获得同一版面**。禁止项目内改 CSS/DOM。
- 归一化只换骨架，数据段用当前账本重新写入；不得借机改决策/历史/能力等级。
- `rollback` 会把看板恢复到升级前骨架，之后必须重新 `plan → apply → verify`，不能只回滚不管版面。
- `board_embed_synced`（24 条不变量之一）与骨架契约是两件事：前者管数据，后者管版面，缺一不可。

## 失败处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `match=false` 且 `missing_ids` 非空 | 项目删过结构锚点 | 归一化重建；不要手工补 id |
| `找不到 const EMBED` | HTML 被改写或不是本模板 | 归一化；先确认账本可读 |
| `board_synced` block | 数据段与账本不等价 | 先 `write_ledger` / 重跑生成器，再谈骨架 |
| 归一化后仍漂移 | 模板与脚本版本不一致 | 升级方法论仓库到同一 tag |

详见 [16-升级与迁移](../../docs/16-升级与迁移.md)、[18-规模化与版面契约](../../docs/18-规模化与版面契约.md)。
