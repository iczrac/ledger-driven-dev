# P1 可达性取证与适配缺口审计（v1.8.0 前置）

> 性质：v1.7.0 发版后的**只读取证 + 临时副本复放**，不写目标项目 `P` 的任何权威字节。
> 记号：目标项目一律记作 `P`；`<app>` 是 `P/projects/` 下首个业务项目目录的脱敏代号（该目录唯一含 `pytest.ini` 且 `testpaths=tests/unit`，实际执行时可据此确定）；临时探针目录记作 `<probe>`；本报告不记录任何绝对路径。
> 动机：v1.7.0 结案与 `feedback/DELIVERY-VERIFY-1.7.0.md` 把 P1 表述为「唯一入口是用户侧输入：提供主仓 `P` 的真实 CI 报告」。本轮取证表明该表述**过度保守，须诚实纠正**。

## 一、结论（先给判定）

1. **P1 不是「没有测试」，而是「报告与能力节点对不上」。** `P` 有 **1,248 个自有测试文件**（主业务项目 1,210 / 其余三个项目 26 / 11 / 1）；`projects/<app>` 单测只读收集到 **12,186 个用例**（6.97s，无 import error）；47 个能力共引用 **118 个单测文件，全部在磁盘真实存在**。
2. 真实卡点是方法论仓 v1.7.0 的**两处适配缺口**（第三节），不是数据缺失、更不是「必须等用户造一份报告」。
3. 在合规规范化 + 显式布局参数下，实测 `judge_tier: declared → verified`；临时副本 24 条三态不变量 **24 pass / 0 fail / 0 na**、`all_active=true`。**P1 可以本地解锁**，P2 才有条件重查。
4. 本轮**并未解锁 P1**：所有写盘动作只发生在临时副本，主仓 `P` 的账本字节、报告文件、`verified` 状态全程未动（第六节）。解锁需要人批准，见第七节。

## 二、只读取证（真实数字）

| 项 | 实测 | 口径 |
|---|---|---|
| 自有测试文件 | **1,248** | 全仓 `test_*.py` / `*_test.py`，排除 `site-packages` / `venv` / `__pycache__` / `node_modules` |
| 主业务项目单测用例 | **12,186 collected in 6.97s** | `pytest --collect-only -q`（`projects/<app>/pytest.ini`：`testpaths=tests/unit`, `pythonpath=.`） |
| pytest 环境 | 项目 venv **9.0.3 / py 3.13.12** | 系统 python 无 pytest，必须用项目 venv |
| 能力引用单测 | **118 路径 / 118 存在 / 0 缺失** | 从 `capability_model` 递归取 `unit_tests[].path` |
| `P` 根 `src/` `tests/` | **均 MISSING** | 真实布局是 `projects/<app>/src`、`projects/<app>/tests` |
| `governance/test_report.json` | **不存在** | 与 v1.7.0 记录一致 |
| `test_results` | **null** | 与 v1.7.0 记录一致 |

**真实探针（未挑绿灯，两次如实记录）**：

| 探针 | 命令范围 | 结果 |
|---|---|---|
| 探针 1 | `tests/unit/ui/test_operator_approval_form.py` | 首跑 **4 errors** —— 沙箱 `tmp_path` 的 `FileExistsError`（环境竞态，非主仓测试缺陷）；改用唯一 `--basetemp` 后 **4 passed** |
| 探针 2 | `tests/unit/test_research_scoring_runtime_services.py`（能力节点真实引用的文件） | **1 passed**，产出真实 JUnit XML |

两次都在项目 venv 内真实执行，JUnit XML 由 pytest 原生 `--junitxml` 产出，未手工编辑任何 `status`。

## 三、两处适配缺口（代码级定位）

### 缺口 A：默认 `--source-dir` 对 monorepo 产生**空证据绑定**，却仍判 `overall=pass`

`scripts/work_panel.py` 的 CLI 默认 `--source-dir src,tests`；`_binding_from_dirs()` 对不存在的目录直接 `continue`。`P` 根目录没有 `src/` / `tests/`，于是：

| 参数 | `evidence_binding.inputs` | `source_digest` | `overall` |
|---|---|---|---|
| 默认 `src,tests` | **0** | `e3b0c44298fc1c14` | `pass` |
| 显式 `projects/<app>/src,projects/<app>/tests` | **2,041** | `dd38f38264f4e33a` | `pass` |

`e3b0c44298fc1c14` 正是 `sha256(b"")[:16]`（已独立复算）。也就是说：**默认路径下报告携带的是空绑定，但 `normalize_report` 仍判 `overall=pass`，`sync-tests` 仍可写盘，`test_results_binding_valid` 仍会转 `pass`** —— 后者只校验用例状态合法、`summary.total` 一致、`source_sha256` 与报告文件自身一致，**不校验 `evidence_binding.inputs` 是否非空**。这是「形式合规、实质无绑定」的可适配性缺口，不是伪造，但足以让「证据有效性」被误读。

### 缺口 B：pytest JUnit XML 的 `<testcase>` 无 `file` 属性，导致 `verified` 永远升不上去

`_cases_from_junit()` 取 `tc.get("file") or ""`；pytest 原生 JUnit 的 `testcase` 只带 `classname` / `name` / `time`，**不带 `file`**。于是所有 `cases[].file = ""`。

而 `governance/build_capability_model.py` 的 `judge_tier()` 用 `Path(c["file"]).name` 与能力 `unit_tests` 的文件名做集合匹配：

```python
passed_files = {Path(c.get("file", "")).name for c in report["cases"]
                if c.get("status") == "pass" and c.get("file")}
matched = [Path(u).name for u in unit_tests if Path(u).name in passed_files]
```

`file` 为空 → `passed_files` 空集 → **即便报告是真实全 pass，47 个能力仍全部 `declared`**。这才是 P1 一直「未满足」的技术根因：v1.7.0 把「根目录无 `tests/`」当成了「主仓没有测试能力」，而实际上缺的是**报告字段到能力节点的映射适配**。

## 四、合规规范化与闭环实测

**规范化不等于伪造**：仅把真实用例映射到其真实存在的测试文件路径，`status` / `id` / `seconds` 一字不改，来源仍是 pytest 真实运行产生的 JUnit XML；`import-report` 的契约本身即允许「任意符合契约的 JSON 规范化成同一份报告」。

| 口径 | `cases[0].file` | `judge_tier` |
|---|---|---|
| A：JUnit 直导（现状） | `""` | **`declared`** |
| B：合规映射 + 显式布局 | `projects/<app>/tests/unit/test_research_scoring_runtime_services.py` | **`verified`** |

B 的 `evidence_binding.inputs=2041`、`overall=pass`、`source_adapter=ledger`。

**临时副本完整复放**（`<probe>/P/governance` 复制账本与工具，补只读符号链接使路径类不变量在完整布局下判定）：

```
import-report（规范化报告落副本）→ sync-tests --apply（PROBE 标记，非人批准）
→ verify_ledger.py --json
```

| 不变量阶段 | pass | fail | na | all_active | `test_results_binding_valid` |
|---|---|---|---|---|---|
| `P` 现状（v1.7.0） | 23 | 0 | 1 | false | `na` |
| 副本（无源码布局，中间态） | 21 | 3 | 0 | true | `pass` |
| 副本（完整布局，最终态） | **24** | **0** | **0** | **true** | **`pass`** |

中间态 3 项 fail 已逐条定位：`doc_paths_exist`（缺 530 条文档路径）、`component_paths_exist`（缺 741 条源码路径）、`registry_impls_exist`（空实现）——**全部是副本未带源码/文档导致的路径类检查**，与 `test_results` 无关；补只读符号链接后归零。此项按「交付成果核实」纪律如实记录，未掩盖。

## 五、对 v1.7.0 结案的诚实纠正

| 原表述 | 纠正后 |
|---|---|
| 「P1 唯一入口是用户侧输入：提供主仓 `P` 的真实 CI 报告」 | **错误（过度保守）**。`P` 自带 1,248 个测试文件与 12,186 个可收集用例，真实 CI 报告可本地产出 |
| 「无 `P/tests/`」→ 隐含「没有测试」 | 事实是**根目录无 `tests/`**，测试分布在 `projects/*/tests`；这是布局假设失配，不是能力缺失 |
| 「语义图顺延须先等 P1」 | 顺延结论**不变**，但 P1 的前置从「等外部输入」改为「修两处适配 + 人批准一次证据绑定」 |

v1.7.0 的**发版范围裁定（收敛版 R1–R3）依然正确**：P1 在当时确未满足，`verified` 为 0 是事实，未伪造任何 `verified`。本轮纠正的是「为什么未满足」与「如何满足」，不推翻任何已发布字节。

## 六、边界与未做（诚实清单）

- **未写主仓**：`P/governance/DECISION_LEDGER.json` 的 sha256 全程未变；`P/governance/test_report.json` **仍不存在**；未对 `P` 执行 `import-report --apply` 或 `sync-tests --apply`；`test_results` 仍 `null`；`activation.state` 仍 `unbound`；47 个能力仍全部 `declared`。
- **未改方法论仓任何 ASSET 字节**：`scripts/*.py`、`docs/[0-9][0-9]-*.md`、`templates/*`、28 份 frontmatter 一律未动；`method_assets.digest` 与 `ontology_digest` 不变，因此**不需要重绑、不需要发版、不需要打 tag**。
- **未执行** `registry/2`；**未掩盖** E7 `cardinality_contradiction`、`evidence_rebaseline=na`、`scale_budget` 阈值告警、6 条 `open` 观察。
- 探针只跑 2 个自足文件（5 个用例），**不代表 12,186 个用例全绿**；本报告不宣称主仓 CI 全绿。临时副本的 `24 pass` 只证明「证据绑定链路在三态语义下自洽」，不是对 `P` 真实测试规模的声明。
- 首跑 4 errors 的环境竞态、中间态 3 项 fail 均已如实记录，未回补成绿灯。

## 七、下一步（需一次明确授权，二选一）

**选项 A｜零摘要成本、不发版**：由人批准一次证据绑定，用真实 CI 报告（本地跑出或用户提供均可）+ 显式 `--source-dir` + 合规映射落盘：

```
python3 scripts/work_panel.py --target P import-report \
    --from <真实 JUnit XML> --adapter junit \
    --source-dir projects/<app>/src,projects/<app>/tests \
    --apply --approved-by <人>
python3 scripts/work_panel.py --target P sync-tests \
    --apply --approved-by <人>
```

但**选项 A 在 v1.7.0 脚本下仍受缺口 B 限制**：JUnit 直导的 `file` 为空，`judge_tier` 依旧 `declared`。要真正满足 P1，需先做一次合规映射（不改脚本、只改输入），或走选项 B。

**选项 B｜发版 v1.8.0（修适配，推荐）**：把两处缺口产品化为机器保证 —— ① 自动探测 `src/tests` 与 `projects/*/src|tests` 布局、拒绝空 `evidence_binding.inputs`；② 从 JUnit `classname` 反解测试文件路径并按账本 `unit_tests` 白名单校验；③ 把「报告 cases 的 `file` 必须命中至少一个能力」写成 `acceptance/1` 的新断言与负向回归。这属于 `ASSET` 改动，会改 `method_assets.digest` 并触发主仓 `M4+M5+M7` 重绑，**必须走完整 S1→S2→S3→S4→发版序列并单独授权**。

P1 满足后重查 P2（`ontology.py check --target P` 的 A2 是否可判定）；P1–P3 全满足后，语义图（Statement 再化 / K3 推理机 / 最小割集 RCA）才可纳入再下一次功能发版。

## 八、提交与作用域

仅新增本文件，位于 `feedback/`（`ZERO` 作用域，不在 `ASSET_GROUPS`）。**不改 ASSET 字节、不改 `P` 账本、不升版本、不打 tag**；`tag v1.7.0` 的资产字节与 `ca1f49e` 保持一致，tag 复放结论不受影响。
