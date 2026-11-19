# DELIVERY-2.1.1 · 术语与实现视图

> 日期：2026-11-19 · 批准：用户指令「直接更新现有 HTML 页面，补充专有词汇表、
> 术语释义、编码思路和关键实现解说，保持原有页面结构与风格一致」
> 版本：v2.1.1（补丁版） · 状态：已交付

## 一、结论

看板此前有十个视图，全部回答「账本里有什么」；没有一个视图回答
「这套方法论怎么读」。D-NNN、verified、漂移、M1–M8 这些词对新手是黑话，
只能翻 docs/ 逐个查——而文档与页面分离，注定漂移。

本版把解说放进页面本身：第 11 个视图「术语与实现」，三个分区。
关键纪律是**同源**：解说的是当前实现，不是愿景；页面内容是权威模板的
静态部分（方法论事实对所有项目一致），改实现必须改模板并发版，禁止项目内手改。

## 二、改动清单

| 文件 | 改动 |
|---|---|
| `templates/index.html.template` | 新标签 `data-v="glossary"`；`GLOSSARY`（20 条术语）、`CODING_IDEAS`（6 条思路）、`IMPL_NOTES`（7 条实现解说）与 `renderGlossary()`；搜索框 placeholder 增「术语」 |
| `tests/views/test_board_views.py` | 模板契约锚点增列 4 项（`data-v="glossary"` / `renderGlossary` / 三个内容数组） |
| `docs/18-规模化与版面契约.md` | 「十个视图」→ 十一个；补一段新视图纪律 |
| `docs/23-本体投影.md` | 版本表补 v2.1.1 行；v2.1.0 改「已发布」 |
| `scripts/upgrade.py` | `METHOD_VERSION` 2.1.0 → 2.1.1 |
| `CHANGELOG.md` / `RELEASE_CHECKLIST.md` | 2.1.1 段落与发布检查 |
| `examples/demo-shop/governance/index.html` | 经 `board_contract normalize` 从新模板重建 |

## 三、实现要点

- **不新增 CSS**：全部复用既有类（`card / chead / ctitle / cid / cmeta /
  pill / day / specbox / empty`），骨架变更最小化；
- **分批契约**：三个分区各按 `PAGE_SIZE` 截断，总数走 `moreHtml`「显示更多」；
- **搜索一致**：搜索框可过滤术语（匹配词、短名、释义）；
- **脱敏**：示例编码用 `DEMO.CORE.ORDER.01`，全文不含来源项目内部名词；
- **数据来源**：术语是方法论事实 → 模板静态内容，不是账本数据；
  项目相关数字（能力数、verified 数）一律不硬编码，避免各项目页面失真。

## 四、验证记录

- 方法仓 `scripts/check.sh` EXIT=0（单测、视图契约、脱敏、同步、验收前置全过）；
- 示例看板经 `normalize` 重建，`board_contract check` 骨架摘要与权威模板一致；
- 目标项目在干净检出执行 `upgrade apply`（带 --approved-by 审计）后：
  24 不变量全绿、生成器 `--check` 无漂移、`upgrade verify` 12 项全过；
- 远端 CI `Governance invariants` 与漂移门禁全绿（见目标项目提交）。

## 五、本版边界（不掩盖）

- 术语收录有意克制（20 条）：页面是索引不是教材，完整论述在 docs/；
- 「符号级证据绑定」（声明的测试必须 import 能力实现）已在沙箱完成
  306/307 全绿验证，但**未经用户批准，不在本版**，连同「资产摘要双算法
  统一」一起等独立批准后另发补丁；
- 多副本同步税依旧存在：模板一改，目标项目与示例项目各需重绑一次
  （本次两处都已执行）。
