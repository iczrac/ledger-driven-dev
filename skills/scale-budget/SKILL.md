---
name: scale-budget
description: |
  规模预算与基准：只读统计治理层文件数、账本/看板体积、决策/历史事件/能力点、
  测试绑定文件与 DOM 卡片数，按单一阈值表报 ok/warn/exceed；并提供可复现的
  生成器规模基准。
  Triggers: "项目很大", "文件数量大", "生成文件太多", "性能", "账本太大", "分页",
  "规模预算", "容量", "scale", "budget", "benchmark", "PAGE_SIZE"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.7.0"
  risk_level: read_only
  related_skills: [board-layout, layout-inspect, ledger-upgrade, scenario-guard]
---

# 规模预算与基准（scale-budget）

## 输入 / 输出契约

| 命令 | 输入 | 输出 | 副作用 |
|---|---|---|---|
| `scale_budget.py` | `--target P [--json] [--check] [--strict]` | `scale-budget/1`：metrics、10 条预算、status、advice | **无**（只读，不落盘报告） |
| `scale_probe.py` | `--mods M --caps C --files F --entries E --events V [--json]` | `scale-probe/1`：真实生成器耗时、产物体积、事件快照规模 | 仅在临时目录构造并清理 |

退出码：`--check` 超硬阈值 → 2；`--strict` 时 warn 也算失败；其余 0。
阈值只在 `scripts/scale_budget.py` 的 `BUDGETS` 定义；渲染上限 `PAGE_SIZE`
直接从模板解析，两处不允许各写一份。

## 第一性原理：什么会增长，什么不会

治理层**文件数固定**：`registry.json` / `DECISION_LEDGER.json` / `index.html` /
3 个工具副本 / 少量派生报告，不会因为模块多就每模块生成一个文件。
`scale_probe.py` 的两次基准（同样 15 个能力、40 与 160 个业务文件）证明
`governance_files` 完全相同。

真正增长的是六个维度：

1. 账本体积：`capability_model` + `history.events` 的**全量状态快照**；
2. 看板体积：EMBED 把同一份账本再内联一次（离线可看的代价）；
3. 结构数量：`entries` / `history_events` / `capabilities` / `test_inputs`；
4. 浏览器 DOM：已由统一模板按 `PAGE_SIZE=200` 分批渲染；
5. CPU：生成器按能力逐个扫 docs / tests，接近 `O(能力 × 项目文件)`；
6. 工作态数据（v1.2.0）：`work_items` 与 `test_results.cases`；由 `work_items` 预算项约束。

## 实测基准（本机，标准库，仅供参考）

| 能力 / 文件 / 决策 / 事件 | 生成器 | 账本 | 看板 | 治理文件 | 预算 |
|---|---:|---:|---:|---:|---|
| 50 / 100 / 50 / 3 | 0.135s | 184 KiB | 118 KiB | 4 | ok |
| 400 / 500 / 200 / 30 | 0.723s | 2.1 MiB | 0.9 MiB | 4 | warn |
| 1000 / 1500 / 500 / 80 | 4.406s | 9.4 MiB | 3.8 MiB | 4 | warn |

历史事件是 append-only 且每个事件带全量状态快照，因此「事件数 × 能力数」
是体积的主要来源，不能靠删历史解决。

## 步骤

1. **BUDGET**：`scale_budget.py --target P --json --check`。看 `status` 与
   `budgets[].advice`；`warn` 不阻断 CI，`exceed` 必须停下来由人决定。
2. **BOARD**：`board_contract.py --target P check --json`，确认版面仍是统一模板（含分批渲染）。
3. **PROBE**（可选）：`scale_probe.py --mods 50 --caps 20 --files 1500 --events 80 --json`，
   在临时目录复现该规模下的真实耗时与体积，不碰真实项目。
4. **DECIDE**：超阈值时按项目拆分 / 冻结归档后复制新项目，或降低门禁频率；
   都不奏效才考虑给生成器加缓存与分片，且必须保持同一份账本可复算。
5. **HANDOFF**：把 `status`、超标项与基准耗时写进交接卡，交回 `platform-steward`。

## 纪律

- **不拆账本、不删 `history.events`**：append-only 是历史可信的前提；拆开就是第二事实源。
- 不为了「减少文件数」把派生报告合并进账本之外的新文件；治理文件数本来就是固定的。
- 阈值是**告警不是自动降级**：AI 不得替人决定归档、拆项目或跳过门禁。
- 基准只在临时目录跑；不要把合成项目写进仓库，也不要用它替代真实项目的门禁结果。

## 已知残差

生成器没有增量索引（场景矩阵 S2，`partial`）；monorepo 多项目联合门禁仍是
E7 `gap`。超 1 万能力或 2 万文件且门禁耗时不可接受时，才值得引入缓存 / 分片。

详见 [18-规模化与版面契约](../../docs/18-规模化与版面契约.md)、[14-场景矩阵](../../docs/14-场景矩阵.md)。
