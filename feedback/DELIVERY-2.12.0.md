# DELIVERY 2.12.0 — 本地 D3：把离线看板从“能看”推进到“能追、能试”

- 版本：v2.12.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过；主仓推广仍只在干净 clone、人工批准后进行

## 一、为什么做这一版

v2.11 的图表都是原生 SVG/CSS，够稳但交互表达受限。用户要求引入 D3，同时必须满足
`file://` 离线、无 CDN、无后端、Python 预计算、前端只渲染。因此本版采用“本地 vendor
+ 子 schema 投影 + hasD3 降级”的最小侵入方案，而不是把看板改成前端应用。

## 二、交付内容

- `templates/vendor/d3.v7.min.js`：D3 v7.9.0 本地副本；模板相对引用；缺文件时自动降级。
- Python 新增 `analytics.timeline` 与 `analytics.lineage`（`trace-lineage/1`），均为只读派生。
- 第 29 条不变量 `analytics_d3_projection_valid`：树与时间轴自证，旧账本 `na`。
- D3 强化三个视图：热力图分组网格、趋势轴线/折线/悬停、新增可展开追溯链视图。
- What-if 同步更新趋势末点、追溯状态节点和变更高亮，仍只改内存副本。
- 新增 `docs/32-本地D3可视化.md`、能力点 `METHOD.GOV.D3.15`、决策 `D-009`。

## 三、边界

- D3 不是事实源：`analytics.lineage` 只索引账本已有的 decisions 与 doc/evidence 路径。
- 不引后端、不联网、不 fetch；`file://` 下内嵌数据先渲染。
- 三份看板（模板/方法仓/demo）共用同一骨架，vendor 文件逐字节一致。

## 四、验证口径

- 单测含 Node DOM stub 无 D3 烟测：空账本与 demo 均走降级路径不报错；389/389 passed。
- `verify_ledger --strict`：29 条不变量，伪造 lineage 状态节点被第 29 条抓到。
- `check.sh` 全量门禁 EXIT=0：16 个阶段、29 条不变量（pass/fail/na）、能力模型复算、升级计划/应用/复验与文件布局同步。
