# v2.0.0 验收契约：registry/2 多项目编码契约

> 性质：`acceptance/1` 第六层（L6）的权威定义书，S2 先红灯、S3 转绿。
> 范围：修主仓 monorepo 的 5 段码问题，使生成器产出 4 段码（`<PROJ>.DATA.READY.01`），
> 保持单项目模板（`DEMO.DATA.READY.01`）双写兼容，并让 P1 的 verified 升级不破坏账本。

## 一、四项机器断言

| id | 判据 | 权威源 |
|---|---|---|
| `code_namespace` | 生成器导出 `code_namespace(project_code, module_code)`：module_code 已含项目段则直接用，否则加 project_code | `templates/build_capability_model.py#code_namespace` |
| `registry2_contract` | `build()` 的 module code 与 cap code 均经 `code_namespace()` 生成，不再裸拼 `{code}.{mcode}` | `templates/build_capability_model.py#build` |
| `no_prefix_leak` | `cap_code` 出现在 4 段（`CODE_RE`），无 `<ROOT>.<ROOT>` / 5 段泄漏 | `tests/core/test_registry2.py` |
| `cap_code_format` | 本契约文档存在且含四锚点字符串 | `feedback/ACCEPTANCE-2.0.0.md` |

四锚点字符串：`code_namespace` / `registry2_contract` / `no_prefix_leak` / `cap_code_format`。

## 二、缺口 → 实现映射

- **缺口（5 段码）**：主仓 registry `project.code=<ROOT>` + `modules[].code=<PROJ>.DATA`，
  生成器 `f"{code}.{mcode}.{domain}.{seq}"` → `<ROOT>.<PROJ>.DATA.READY.01`。
- **修复（code_namespace）**：`module_code` 首段已是项目码（含 `.` 且首段全大写），
  命名空间直接用 `module_code`；否则 `f"{project_code}.{module_code}"`。
  - 主仓 `<PROJ>.DATA` → `<PROJ>.DATA`（4 段）；
  - 模板 `DATA` → `DEMO.DATA`（4 段，双写兼容）。
- **不降级随之简化**：`no_regress()` 用同格式 code 直接比对，不再靠前缀剥离对齐。

## 三、可复算验证（S3 实测基准）

在 `P` 上用真实报告（182 用例）跑新生成器并写盘：

| 指标 | 写盘前（v1.8.0 工具） | 写盘后（v2.0.0） |
|---|---|---|
| cap code | `<PROJ>.DATA.READY.01`（账本存量） | `<PROJ>.DATA.READY.01`（4 段，不变） |
| 24 不变量 | 23 pass/1 na | 24 pass/0 fail（test_results 启用） |
| level 分布 | L5:20/L3:22/L2:5 | L5:20/L3:22/L2:5（不降级） |
| evidence_tier | declared:47 | declared:27/verified:20 |
| test_results | null | 绑定真实报告 hash |

双写回归：用 `templates/registry.example.json`（单项目 DEMO）跑生成器，cap code 必须
仍是 `DEMO.DATA.READY.01`（4 段），不得因本次修复破坏示例项目。

## 四、边界

- L6 只在 full 范围生效；`only_preconditions=True` 仍返回 L1–L5 原样（v1.9.0 前语义不变）。
- 四项断言中 `code_namespace` / `registry2_contract` 针对方法论仓权威源，不读主仓数据；
  `no_prefix_leak` 为 unit test（合成输入 + 真实 P 只读探针）；`cap_code_format` 检查本文件。
- 主仓 registry/capability_model 的实际写盘属 S4 人批准数据迁移。

## 五、转绿判据

`python3 scripts/acceptance.py --check --full` → 十四项 checks 全 PASS（L1×3 + L4×3 + L5×4 + L6×4）；
`bash scripts/check.sh` → 全阶段绿；`unittest discover -s tests` 全绿。
