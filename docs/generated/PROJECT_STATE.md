# PROJECT_STATE · METHOD Ledger-Driven Dev 方法论仓库（自举）

> 由 `scripts/rebuild_docs.py` 从账本与 `docs.registry` 渲染；派生文档禁止手改。

## 能力清单与等级/证据分层

| 编码 | 名称 | 当前等级 | 证据分层 | 目标等级 |
|---|---|---|---|---|
| METHOD.GOV.FEEDBACK.01 | 反向回流观察通道 | L3 | verified | L4 |
| METHOD.GOV.UPGRADE.02 | 升级与迁移引擎 | L3 | verified | no_target |
| METHOD.GOV.PANEL.03 | 节点工作台 | L3 | verified | no_target |
| METHOD.GOV.LAYOUT.04 | 文件布局契约 | L3 | verified | L4 |
| METHOD.GOV.ASSETS.05 | 方法资产清单 | L3 | verified | L4 |
| METHOD.GOV.TESTMAP.06 | 测试架构映射 | L3 | verified | no_target |
| METHOD.GOV.BINDING.07 | 符号绑定判据（dogfood 负向探针：测试用动态加载，绑定判据应抓不到） | L3 | declared | L4 |
| METHOD.GOV.RESTATE.08 | 复述门（v2.4.0 补录）：结构化意图声明 + 机器锚定，路由前置 | L3 | verified | no_target |
| METHOD.GOV.ORCH.09 | 专家团编排（v2.5.0 补录）：交接链展开 + 命令分类 + 人工批准包 | L3 | verified | L4 |
| METHOD.GOV.ANNOT.10 | 来源投影（v2.6.0 补录）：AI推断/人确认分组 + 完成定义派生 | L3 | verified | L4 |
| METHOD.GOV.BOARD.11 | 看板体验契约（v2.8.0）：语义结构 + 当前状态可见 + 搜索/跳转可达 + 响应式 | L3 | verified | L4 |
| METHOD.GOV.VISUAL.12 | 架构图与数据流（v2.9.0）：账本驱动 SVG + 实时计数 + 可下钻节点 + 分组导航 | L3 | verified | no_target |
| METHOD.GOV.WORKBENCH.13 | 工作台视角（v2.10.0）：默认落点=工作台 + 今日焦点 + 可信度条 + 下一轮队列 + 入口矩阵 | L3 | verified | no_target |
| METHOD.GOV.ANALYTICS.14 | 可视化分析层（v2.11.0）：热力图 + 趋势 + 证据链 + 健康度多维 + 卡片墙 + What-if | L3 | declared | L4 |
| METHOD.GOV.D3.15 | 本地 D3 离线交互层（v2.12.0）：追溯树 + D3 热力图 + 趋势图 + What-if 联动 | L3 | verified | L4 |
| METHOD.GOV.RUNTIME.16 | 运行时风险入口（v2.15.0）：STATE 事件 → 精确能力点映射 → next_queue 只读重排 | L3 | verified | no_target |
| METHOD.GOV.DOCLIFE.17 | 文档信任硬门（已声明、待人工批准升硬门；尚无证据，不计入完成度） | L0 | declared | L1 |

## 待复核与过期文档

| 文档 | 原因 |
|---|---|
| docs/01-问题与原则.md | status=draft 待人工复核 |
| docs/02-决策账本.md | status=draft 待人工复核 |
| docs/03-编码与成熟度.md | status=draft 待人工复核 |
| docs/04-嵌套组件与文档索引.md | status=draft 待人工复核 |
| docs/05-循环协议.md | status=draft 待人工复核 |
| docs/06-落地指南.md | status=draft 待人工复核 |
| docs/07-反模式与边界.md | status=draft 待人工复核 |
| docs/08-可信性校验.md | status=draft 待人工复核 |
| docs/09-历史与经验.md | status=draft 待人工复核 |
| docs/10-AI集成.md | status=draft 待人工复核 |
| docs/11-证据分层.md | status=draft 待人工复核 |
| docs/12-专家路由.md | status=draft 待人工复核 |
| docs/13-可追溯性.md | status=draft 待人工复核 |
| docs/14-场景矩阵.md | status=draft 待人工复核 |
| docs/15-文件架构.md | status=draft 待人工复核 |
| docs/16-升级与迁移.md | status=draft 待人工复核 |
| docs/17-多Agent接入控制.md | status=draft 待人工复核 |
| docs/18-规模化与版面契约.md | status=draft 待人工复核 |
| docs/19-专家与技能可用.md | status=draft 待人工复核 |
| docs/20-测试架构与模块映射.md | status=draft 待人工复核 |
| docs/21-节点工作台与看板视图.md | status=draft 待人工复核 |
| docs/22-反向回流.md | status=draft 待人工复核 |
| docs/23-本体投影.md | status=draft 待人工复核 |
| docs/24-复述门.md | status=draft 待人工复核 |
| docs/25-专家团自动编排.md | status=draft 待人工复核 |
| docs/26-来源投影与完成定义.md | status=draft 待人工复核 |
| docs/27-自举闭环.md | status=draft 待人工复核 |
| docs/28-看板体验.md | status=draft 待人工复核 |
| docs/29-架构图与数据流.md | status=draft 待人工复核 |
| docs/30-工作台视角.md | status=draft 待人工复核 |
| docs/31-可视化分析层.md | status=draft 待人工复核 |
| docs/32-本地D3可视化.md | status=draft 待人工复核 |
| docs/33-目标编排监督者.md | status=draft 待人工复核 |
| docs/34-运行时风险入口.md | status=draft 待人工复核 |
| docs/35-投影新鲜度不变量.md | status=draft 待人工复核 |
| docs/36-风险下降判据.md | status=draft 待人工复核 |
| docs/STANDARD.md | status=draft 待人工复核 |

## next_queue（前 5 条）

| 编码 | 动作 | 等级 | 目标等级 |
|---|---|---|---|
| METHOD.GOV.DOCLIFE.17 | contracts/ 目录有契约文件 | L0 | L1 |
| METHOD.GOV.ANALYTICS.14 | docs/test_records/ 有测试记录 | L3 | L4 |
| METHOD.GOV.ANNOT.10 | docs/test_records/ 有测试记录 | L3 | L4 |
| METHOD.GOV.ASSETS.05 | docs/test_records/ 有测试记录 | L3 | L4 |
| METHOD.GOV.BINDING.07 | docs/test_records/ 有测试记录 | L3 | L4 |

## 文档生命周期指标口径

> 0 表示「判据已执行且无命中」；n/a 表示前置数据缺失、判据不适用。所有数字都由 `scripts/doc_lifecycle.py gate` 的同名判据复算。

| 指标 | 判据 | 已判 | 计数 |
|---|---|---|---|
| 覆盖完整 | covers.codes / covers.decisions 非空 | 42 | 26（真实覆盖 16/42） |
| 义务已声明 | owner / role / stale_after 已填写 | 42 | 42 |
| 过期 | _stale_after_expired(value, as_of=2026-11-27) | 0 | 0 |
| 无法判过期 | _stale_after_expired(...) == unknown | 42 | 42 |

## 最近变更

| seq | 类型 | 摘要 |
|---|---|---|
| 33 | change | 无结构化变更 |
| 34 | change | 无结构化变更 |
| 35 | change | 无结构化变更 |
