# 目标项目接入前 dry-run 取证

> 一次性取证，不是第二事实源。权威队列仍来自目标项目账本；
> 运行时事件仍来自目标项目 STATE 事件原文；本报告只记录只读重排结果，
> 项目与能力编码一律脱敏为 `P.*`。

## 一、结论

目标项目当前账本队列与生成器重算完全一致；注入运行时信号后，队列头号任务
从“补证据”转为有原文可追溯的运行时风险点。该结果证明接入方向有效，但本阶段
**未写目标项目账本**。

## 二、输入与投影

- 事件块：17 个 `E<n>`。
- 精确投影：3 条。
  - `E4` risk=1.0 → `P.DATA.PROVIDER.05`，证据 `2026-11-20.md#E4`。
  - `E1` risk=0.5 → `P.DATA.COVERAGE.04`，证据 `2026-11-20.md#E1`。
  - `E3` risk=0.5 → `P.DATA.COVERAGE.04`。
- 其余事件因 unknown / 歧义 / 表外文本 fail-closed，不进入排序。

## 三、队列变化

| 排名 | 基线 | 注入信号后 |
|---:|---|---|
| 1 | `P.RS.RSCOV.04`（completion 0.4） | `P.DATA.PROVIDER.05`（risk=1.0, E4） |
| 2 | `P.PROC.DECIDE.02`（completion 0.4） | `P.DATA.COVERAGE.04`（risk=0.5, E1） |
| 3 | `P.API.API.01`（completion 0.4） | `P.RS.RSCOV.04`（risk=0） |

`LEDGER_QUEUE_MATCH=True`：基线队列与账本当前 `next_queue` 完全一致，
说明变化不是账本漂移，而是新增只读输入导致的排序投影变化。

## 四、纪律

- `risk_score` 只影响排序与任务卡注解，不改 `level / completion / evidence_tier`。
- 目标项目账本与业务文件本阶段未改。
- 正式接入必须经过批准、生成派生信号、重算账本并复跑目标项目全量门禁。
