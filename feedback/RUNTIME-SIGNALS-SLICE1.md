# 运行时风险入口 · Slice 1 取证

> 一次性**取证报告**，不是第二事实源。队列的权威源是账本 `capability_model`；
> 运行时风险的权威源是目标项目的 `STATE/events/*.md`；本报告只回答一件事：
> **把运行时风险投影成信号后，账本的 next_queue 头号任务会不会从「补证据」转向「真实 P0」。**
> 全程只读目标项目、内存副本重排、零写盘；未触碰目标项目工作区任何文件。

## 一、方法

1. 权威工具 `build_capability_model.build_next_queue(limit=10)` 产出基线队列。
2. `scripts/runtime_signals.parse_state_events()` 解析 `STATE/events/*.md` 的 `## E<n>` 块：
   - 字段只取事件原文（time / finding / confidence / action / evidence），带 `source_file + id` 可追溯；
   - `confidence != fact/inference` → `unknown`，`risk_score=0`，不进排序（fail-closed）；
   - 域判定只查内置关键词表，表外 → 无域，不进排序。
3. `apply_risk_signals()` 在内存副本按 `(-risk, completion, code)` 重排；入参队列与账本不变。

## 二、核心验收（Slice 1 唯一判据）

| 项 | 值 |
|---|---|
| 基线 rank1 | `P.RS.RSCOV.04`（completion 0.4，补契约+单测） |
| 注入后 rank1 | `P.DATA.ADJUSTED.03`（risk=1.0，信号 `E4`） |
| rank2/3 | `P.DATA.COVERAGE.04` / `P.DATA.PROVIDER.05`（同 `E4`） |
| 原 rank1 落点 | `P.RS.RSCOV.04` 降至 rank4，risk=0 |
| 判定 | **通过** — 队列头号任务从补证据转向真实 P0 seam |

信号分布（17 个 E 块，来自 3 个事件文件）：

- `fact` 且可判域 7 个；其中 `E4`（HK momentum seam 单调上升 27.3%→32.24%，action=none）risk=1.0，是唯一满分信号。
- 旧批次 10 个 E 块 `confidence=unknown`（字段格式不同），正确回落、不进排序——fail-closed 生效。
- `E2`（磁碟）、`E7`（已收敛）虽为 fact，但无域关键词命中，不干扰队列。

## 三、边界与已知限制

- **域级而非能力点级**：信号命中 `DATA` 域后，该域全部能力点均带同一 `risk_score`。精确映射到单个能力点需 Slice 2 的输入契约扩展。
- **未接生成器**：本次只在独立纯函数模块验证，未改 `build_capability_model.py`，故三处工具副本无漂移、账本未动。把投影接入生成路径属 Slice 2。
- **风险分是排序信号，不是完成度**：`risk_score` 只影响队列顺序，不写 `level` / `completion`，符合「完成度从证据算」的铁律。

## 四、落点

- `scripts/runtime_signals.py` — 纯函数投影器（core 模块，已登记 `tests/MODULES.json`）
- `tests/core/test_runtime_signals.py` — 9 个契约用例（解析 / fail-closed / 单调上升 / 重排 / 入参不变）
- `docs/generated/TEST_MODULES.md` — 测试模块生成物已重渲染
