# 交付卡 · v2.15.0

**主题**：运行时风险入口——把现场风险投影成可执行排序，而不让账本只在文件视角里自洽。

## 做了什么

1. **Slice 1（域级验证）**：`scripts/runtime_signals.py` 解析 `STATE/events/*.md` 的
   `## E<n>` 事件块，产出带 `source_file / id / confidence` 的可追溯信号；
   `risk_score` 只表达排序优先级，不改等级与证据；unknown 一律 fail-closed。
   9 个用例锁定解析、评分、域判定与内存副本重排。
2. **Slice 2（精确映射 + 生成器）**：新增 `capability_hits / project_signals /
   apply_risk_signals_exact`。映射优先级为事件显式 code → 原文完整 code → 语义词表；
   歧义即丢弃。`build_capability_model.py` 新增 `--runtime-signals <json>`，
   只在命中时给任务卡加 `risk_score / risk_signal / risk_evidence`，
   排序键改为 `(-risk, completion, code)`；`--check` 同步比对风险注解漂移。
3. **误伤收敛**：裸词「覆蓋」会把“只覆蓋 3 個檔案”误判成覆盖审计；词表收紧为审计语境后
   该事件正确回落。精确映射的价值不是抬高整个域，而是同域内也能区分真信号与噪声。
4. **版本治理**：新能力点 `METHOD.GOV.RUNTIME.16`、文档 `docs/34-运行时风险入口.md`、
   CHANGELOG 与账本发版决策 `D-012`；方法版本升至 2.15.0。

## 验证

- `tests/core/test_runtime_signals.py` 19/19（Slice 1 的 9 + 精确映射 7 + 生成器 3）。
- 全量 437/437；`test_modules` 通过；ontology 0 漂移；`check.sh` 16 阶段全绿。
- 干净快照只读取证：17 个事件块 → 3 条精确投影；队列头号任务由补证据
  转为带 `E4` 原文可追溯的运行时风险点，原 rank1 降至 rank3。
- 示例生成器带信号写回后 `--check` EXIT=0；三份生成器副本逐字节一致。

## 边界与下一步

- 风险只改排序，不改 `level / completion / evidence_tier`；不自动修数据、不写目标项目。
- 主仓账本与业务文件本版未改；真实项目若要持久化风险注解，须人批准接入其生成流程。
- 下一步：把 `--runtime-signals` 接入目标项目的受控生成脚本，先 dry-run 取证，
  再按人批准的命令回流账本。

## 运行方式

```bash
# 1) 从事件原文产出投影（只读）
python3 -c 'import json; from runtime_signals import parse_state_events, project_signals; \
print(json.dumps(project_signals(parse_state_events("<STATE>/events"), model)))' > signals.json

# 2) 生成器 dry-run 看排序变化；确认后再写盘
python3 governance/build_capability_model.py --root <项目根> --runtime-signals signals.json --dry-run
python3 governance/build_capability_model.py --root <项目根> --runtime-signals signals.json --check
```
