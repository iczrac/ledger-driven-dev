---
name: test-map
description: |
  测试架构按开发模块组织并机器校验，含目标项目的能力模块单测覆盖缺口。
  Triggers: "测试架构", "测试模块", "模块重组", "test modules", "MODULE_ID",
  "哪个模块没测试", "unittest discover", "run_tests 口径"
license: MIT
metadata:
  author: iczrac
  version: "1.4.0"
  risk_level: read_only
  related_skills: [ledger-verify, scenario-guard, layout-inspect, asset-install]
---

# Test Map

## When to Use

- 想知道某份测试到底属于哪个开发模块，以及该模块的归属是否还成立；
- 新增 / 移动测试文件后，确认清单、目录、文件内常量、发现口径没有漂移；
- 想知道被治理项目里哪个能力模块还没有单测。

## 为什么

方法论要求「文档 - 测试 - 实际代码 - 账本记录」用四段式编码对应，
但仓库自己的测试原本是扁平的 `tests/test_*.py`：按脚本横切命名，没有模块归属，
也没有任何机器可查的映射。目录好看不等于架构成立。

三处互相自证：

1. `tests/MODULES.json` —— 模块 → 文件 → 所属脚本的唯一清单；
2. 每个测试文件里的 `MODULE_ID` —— 文件自证归属；
3. `scripts/run_tests.py` 的 `sorted(tests.rglob("test_*.py"))` —— 发现口径必须一致。

另有 `unittest discover -s tests -v` 作为第二套交叉验证，两者用例数必须相同。
模块名必须避开 Python 标准库（`platform` / `trace` / `test` / `types` …），
否则 discover 会把顶层模块误当成包而无法导入。

## 步骤

```bash
python3 scripts/test_modules.py --check
python3 scripts/test_modules.py --emit-md docs/generated/TEST_MODULES.md
python3 -m unittest discover -s tests -v
python3 scripts/run_tests.py --dir tests --top . --out /tmp/repo-tests.json --label repo
python3 scripts/test_modules.py --target P --json      # 被治理项目的模块单测缺口
```

`--target` 输出 `test-module-coverage/1`：每个能力模块的
`capabilities` / `unit_tests` / `paths` / `status`，以及 `modules_without_tests[]`。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | 方法论仓库 `tests/`，或目标项目 `governance/DECISION_LEDGER.json`（只读） |
| 输出 | `test-modules-check/1`（ok / errors / modules / test_files）或 `test-module-coverage/1` |
| 失败码 | 2 = 定义自检失败；1 = 目标项目存在无测试模块 |

## 禁止

- 直接改 `docs/generated/TEST_MODULES.md`（生成物，改清单后重新渲染）；
- 只把文件搬进模块目录却不改 `MODULES.json` 与 `MODULE_ID`；
- 用 `platform` / `trace` 这类标准库同名目录；
- 用测试目录重排代替真正的单测补齐（缺口报告只看 `doc_index.unit_tests` 真实路径）。

## 失败处理

| 报错 | 修复 |
|---|---|
| 清单与 rglob 发现结果不一致 | 补/删 `MODULES.json` 的 files |
| 缺少 MODULE_ID / 与清单不一致 | 在 future import 之后补常量 |
| 模块名与标准库冲突 | 改名并同步 `git mv` |
| 所属脚本不存在 | 修 `owner_scripts` 或恢复脚本 |
