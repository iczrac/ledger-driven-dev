# DELIVERY 2.8.0 — 看板体验：从「有数据」到「用得顺」

- 版本：v2.8.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过，全量门禁 EXIT=0；主项目推广待用户另行确认（只在干净 clone 操作）

## 一、为什么做这一版

v2.7.0 解决了「账本是否真实、术语是否接本体」，但看板作为每天使用的界面，还有四个体验缺口：

1. 视图平铺，切换后看不到当前所在视图、搜索词与钻取作用域；
2. 统计卡是死数字，看到「待裁决 / 阻塞 / 失败用例」后还要自己找入口；
3. 搜索没有就地清除，钻取与全局搜索容易叠加造成误解；
4. 长列表缺展开状态，窄屏字段挤压，读屏与键盘操作没有明确锚点。

这些都不改变账本事实，却直接决定治理信息能不能被用起来。因此本版只动呈现层：**不改判定规则、不新增账本字段、不复制第二事实源**。

## 二、改了什么

### A · 权威模板 UX 改造

- 顶部改为语义结构：skip link、`nav` / `main` / `footer`；视图按钮改 `button`，带 `aria-current="page"`。
- 新增 `renderContext()` 上下文条：当前视图名、用途提示、搜索词 chip、钻取 chip、展开/收起全部。
- `stat()` 产出可点击统计卡；`bindStats()` 事件委托把 TODO / Issue / 阻塞 / 失败用例 / 待裁决等数字直接映射到对应视图。
- 搜索框加清除按钮；`/` 聚焦、`Esc` 清除（先清搜索，再清作用域）；搜索占位符随视图变化。
- `bindContext()` 统一处理 chip 移除、展开/收起；`card()` 的展开按钮改用 `button` 并维护文字与 `aria-expanded`。
- 卡片展开状态文字化；导航 sticky、hover/focus 反馈、响应式两列、`prefers-reduced-motion`、打印样式。

### B · 治理绑定

- `METHOD_VERSION` 2.7.0 → 2.8.0；新增 `docs/28-看板体验.md` 与本交付卡。
- 方法仓账本补录 D-005 `status=done` 发版决策，证据指向真实 CHANGELOG / 交付卡 / 模板 / 测试。
- 看板骨架摘要变化，通过 `board_contract.normalize --approved-by user-approved-ux --apply` 归一化方法仓与示例看板；
  `upgrade apply` 重绑 `method_version` / `method_assets` / `board_skeleton`。
- 新能力点 `METHOD.GOV.BOARD.11`（看板体验契约）：测试静态 import `board_contract`，实现与测试同链绑定。

### C · 先红后绿

- 新增 `tests/views/test_board_views.py::test_board_ux_contract`，改前失败（缺语义结构、上下文、清除按钮、响应式锚点），改后通过。
- 能力模型 10→11；10 verified + 1 declared（BINDING.07 负向探针仍诚实保留）。
- 全量门禁 EXIT=0、16 阶段；单测 377→378；`账本=f(registry,仓库,报告)` 逐字段可复算。

## 三、守住的纪律

- **体验不覆盖事实**：`VIEW_META` 只描述标题、提示与占位符，不存决策、能力或搜索结果状态。
- **权威模板唯一**：方法仓与示例看板由同一模板归一化；项目内手改 CSS/DOM 仍会被骨架摘要抓出。
- **数据段隔离**：`EMBED` 与 `ONTO_TERMS` 仍是唯一数据入口；UX 改造只动骨架，不动数据来源。
- **写盘需批准**：`normalize` 与 `upgrade apply` 都带 `--approved-by`，写前备份到 `.ledger-upgrade/backups/`。
- **主仓不碰**：主项目工作区既有改动全程未动；v2.4～v2.8 推广仍待单独确认。

## 四、后续

主仓推广（v2.4～v2.8 整包升级）待用户确认——只在干净 clone 操作，`apply` 需 `--approved-by`。
相关：[28-看板体验](../docs/28-看板体验.md)、[27-自举闭环](../docs/27-自举闭环.md)、
[26-来源投影](../docs/26-来源投影与完成定义.md)。
