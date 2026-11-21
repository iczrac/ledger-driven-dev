# 运行时风险入口 · Slice 2 取证

> 一次性**取证报告**，不是第二事实源。队列的权威源仍是账本 `capability_model`；
> 运行时风险的权威源仍是目标项目的 `STATE/events/*.md`；生成器只把显式传入的
> 信号投影当作 `f(registry, 仓库, test_report, runtime_signals)` 的一个只读输入。
> 全程只读目标项目、内存副本重排、零写盘；报告中的项目与能力名一律脱敏为 `P.*`。

## 一、Slice 2 做了什么

Slice 1 只能把风险按域抬高：命中 `DATA` 域后，该域全部能力点同分。Slice 2 把映射
收窄到**精确能力点**，并接进生成器：

1. **映射优先级（fail-closed）**
   - 事件显式字段 `capability` / `capabilities` / `target`：写的是账本中真实存在的 code 才采信；
   - 原文中的完整能力码：必须命中 `model` 能力码全集；
   - 语义词表：按“更长关键词优先”选 token；同长跨 token 命中视为歧义 → 不进排序；
   - 表外文本不硬塞进任何能力点；`confidence` 非 `fact/inference` 直接丢弃。
2. **投影可序列化**：`project_signals()` 只输出
   `id / source_file / confidence / domain / risk_score / capabilities`，不带时间戳、不写盘。
3. **生成器可选接入**：`build_capability_model.py` 新增 `--runtime-signals <json>`。
   - 不给该参数：队列形状与排序完全保持旧行为；
   - 给出该参数：仅命中的任务卡新增 `risk_score / risk_signal / risk_evidence`，
     排序键变为 `(-risk_score, completion, code)`；
   - `risk_score` **不改** `level` / `completion` / `evidence_tier`——风险是排序信号，不是证据。
4. **可复算门禁**：`--check` 在提供 `--runtime-signals` 时同步比对队列风险注解，
   手改风险字段或删掉信号都会报漂移。

## 二、核心验收

| 项 | 值 |
|---|---|
| 事件解析 | 17 个 `E<n>` 块 |
| 精确投影 | 3 条（`E1` / `E3` / `E4`）；旧批次 14 条仍按 unknown/歧义 fail-closed |
| 满分信号 | `E4` risk=1.0 → `P.DATA.PROVIDER.05` |
| 次级信号 | `E1` / `E3` risk=0.5 → `P.DATA.COVERAGE.04` |
| 基线 rank1 | `P.RS.RSCOV.04`（completion 0.4，补证据） |
| 注入后 rank1 | `P.DATA.PROVIDER.05`（risk=1.0，信号 `E4`） |
| 注入后 rank2 | `P.DATA.COVERAGE.04`（risk=0.5，信号 `E1`） |
| 原 rank1 落点 | `P.RS.RSCOV.04` 降至 rank3，risk=0 |
| 判定 | **通过**——队列头号任务从“补证据”转向有原文可追溯的真实运行时风险 |

切片过程中还修掉一次误伤：`E7` 的“只覆蓋 3 個檔案”曾被裸词「覆蓋」误判成覆盖审计。
语义词表现在只接受 `coverage audit / 覆盖审计 / 覆蓋審計 / gap fill / frontier` 等审计语境，
`E7` 正确回落、不进队列。这是精确映射相对 Slice 1 的关键收益：**同域内也能区分真信号与噪声**。

## 三、生成器闭环（示例项目 dry-run）

- 无信号：`next_queue[0]=P.API.QUERY.01`，无 `risk_*` 字段，账本形状不变。
- 带信号：dry-run 打印 `风险 1.0(E1)`；写回后再跑 `--check` 返回 0，
  账本队列稳定携带 `risk_score=1.0 / risk_signal=E1 / risk_evidence=x.md#E1`。
- 畸形条目（非对象、非法分数）被逐条跳过，不阻断生成器，也不会抬高任何能力点。

## 四、边界与已知限制

- 语义词表是**投影规则**，可审计、可改；它不是事实，也不替代事件作者显式标注能力码。
- 跨项目同 token 的能力点若无法用显式 `domain` 收窄，判歧义并 fail-closed。
- 本切片仍不自动修数据、不写目标项目；`risk_score` 只影响排序与任务卡注解。
- 主仓账本未改；真实项目只有在人批准并把 `--runtime-signals` 接到其生成流程后才会持久化风险注解。

## 五、落点与验证

- `scripts/runtime_signals.py` — 新增 `capability_hits / project_signals / apply_risk_signals_exact`
- `templates/build_capability_model.py` — 新增 `--runtime-signals` / `_runtime_risk_index` /
  `diff_queue_risk`；三份副本（templates、governance、demo）逐字节一致
- `tests/core/test_runtime_signals.py` — 19 个用例（Slice 1 的 9 个 + 精确映射 7 个 + 生成器 3 个）
- `docs/generated/ONTOLOGY.json` / `ONTOLOGY.md` — 因权威源变化按可复算口径重渲染，0 漂移
- 全量测试 437/437；`test_modules` 通过；`check.sh` 16 阶段全绿（EXIT=0）
