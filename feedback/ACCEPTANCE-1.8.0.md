# v1.8.0 验收契约：证据适配与不降级

> 性质：`acceptance/1` 第五层（L5）的权威定义书，S2 先红灯、S3 转绿。
> 范围：把 P1 可达性审计发现的四缺口产品化，**不碰主仓权威数据**（registry / capability_model 由独立迁移方案处理）。

## 一、四项机器断言

| id | 判据 | 权威源 |
|---|---|---|
| `evidence_adapter` | `scripts/work_panel.py` 导出 `default_source_dirs` / `classname_to_file`，含空绑定拒绝与 monorepo 布局 | `scripts/acceptance.py#evidence_adapter` |
| `no_regression_guard` | `templates/build_capability_model.py` 导出 `evidence_hints` / `no_regress`，含 level 降级判据 | `scripts/acceptance.py#no_regression_guard` |
| `l5_contract_doc` | 本文件存在且含四锚点 | `scripts/acceptance.py#l5_contract_doc` |
| `evidence_end_to_end` | 上述 work_panel 函数可按路径加载并调用 | `scripts/acceptance.py#evidence_end_to_end` |

四锚点字符串：`default_source_dirs` / `classname` / `evidence_hints` / `no_regress`。

## 二、缺口 → 实现映射

- **缺口 A（空绑定判绿）**：`default_source_dirs(target)` 探测根 `src/tests` 或 `projects/*/{src,tests}`；`normalize_report()` 在 `evidence_binding.inputs` 为空时把 `overall` 置 `fail` 并写 `load_errors`。默认 CLI `--source-dir` 改为自动探测。
- **缺口 B（JUnit 无 file）**：`classname_to_file(classname, whitelist)` 用 basename 精确匹配账本 `unit_tests` 白名单，命中不到返回空串（不猜路径）；`_cases_from_junit` 在 XML 无 `file` 属性时用它反解。
- **缺口 C（目录失配）**：生成器新增 `_monorepo_dirs()`，把配置的单目录扩展为 `projects/*` 下的同名目录，覆盖 `projects/*` 下全部业务项目。
- **缺口 D（hints 失配）**：生成器新增 `evidence_hints(ledger, cap_code)`，从账本既有 `evidence.unit_test` / `evidence.test_record` 派生文件名 stem，与 registry hints 合并去重。
- **不降级门禁**：`no_regress(old_ledger, new_model)` 比较 `code → level_code`，任何下降即 `[BLOCK]` 拒绝写盘（写盘默认拒绝，`--allow-regress` 仅人批准迁移显式绕过）。

## 三、可复算验证（S3 实测基准）

用真实探针报告（19 用例 pass，能力引用单测）在 `P` 账本上跑新模板 `build()`：

| 指标 | 改前 | 改后 |
|---|---|---|
| level 分布 | L2:46 / L0:1（降级 42） | **L5:20 / L3:22 / L2:5（降级 0）** |
| evidence_tier | declared:47 | **declared:38 / verified:9** |
| `no_regress()` | 42 条降级 | **空** |

注意：早期一次验证误把账本 code（`<PROJ>.x`）与生成 code（`<ROOT>.<PROJ>.x`）当作同 key，得出「降级 0」的假阴性；本表是**剥离 project 前缀后正确对齐**的结果。此纠正本身是「交付成果核实」纪律的一部分。

## 四、边界

- L5 只在 full 范围生效；`only_preconditions=True` 仍返回原 L4 三项，v1.7.0 语义不变。
- 四项断言都针对**方法论仓权威源**，不读主仓数据；主仓 registry / capability_model 的修复另有人批准迁移方案。
- 门禁自测（`tests/meta/test_acceptance.py#L5DetectorTest`）喂合成输入验证判定逻辑，不断言仓库当前红绿。

## 五、转绿判据

`python3 scripts/acceptance.py --check --full` → 十项 checks 全 PASS；
`bash scripts/check.sh` → 全阶段绿；`unittest discover -s tests` 全绿。
