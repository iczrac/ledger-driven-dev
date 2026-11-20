# DELIVERY 2.11.0 — 可视化分析层：从看板数字到工作台判断

- 版本：v2.11.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过；主项目推广仍待确认（只在干净 clone 操作）

## 一、为什么做这一版

用户要求在看板上做能力成熟度热力图、成熟度趋势、证据链钻取、健康度多维仪表盘、
`next_queue` 卡片墙、变更高亮与纯前端 What-if。前几版已经把账本数字画出来，但用户仍要自己
把「数字」翻译成「判断」。本版把这一步也做成可复算投影。

## 二、数据层

- `templates/build_capability_model.py` 新增 `analytics`（`maturity-analytics/1`）：
  每能力点 L0–L5 时间序列、与前一事件快照的差异摘要、健康度五维、推荐行动与健康增益。
- `summary` 新增 `health_dimensions` / `health_overall` / `health_method`。
- `next_queue[]` 新增 `health_impact`，卡片墙直接显示。
- 所有字段可选、可复算；旧账本缺字段时由前端降级派生，不被判伪造。

## 三、前端层

- 新增三个视图：`heatmap` / `trend` / `queue`；原有全部 `data-v` 保留。
- 原生 SVG 趋势图与 CSS 色阶热力图，无第三方运行时、无后端。
- 任一能力点可展开证据链：文档索引、变更历史、关联经验、What-if 入口。
- 工作台可信度条下新增五维健康度进度条。
- `localStorage` 记录上次指纹与工作项签名，变化项加橙色标记；首次打开只建基线。
- What-if 只改内存副本 `VIEW_DATA`，不写账本、不影响不变量。

## 四、治理绑定

- 新决策 `D-008`，状态 `done`，走唯一写入口。
- 新能力点 `METHOD.GOV.ANALYTICS.14`，能力模型 13→14。
- 第 28 条不变量 `analytics_maturity_valid`：序列末点、分数边界、加权和、行动增益全部自证。
- 新增 `docs/31-可视化分析层.md`、`tests/core/test_maturity_analytics.py`。
- 方法仓与 demo 看板骨架一致；demo 用现有账本即可展示全部新视图。

## 五、验证

- 数据层与前端契约均先红后绿。
- `verify_ledger.py --strict`：28 条不变量，旧账本分析层为 `na` 不计绿灯。
- 全量门禁、能力模型可复算、升级绑定与看板一致性见当次运行日志。
