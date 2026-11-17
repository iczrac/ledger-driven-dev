# 文档规范

文档不是装饰。这套方法里，文档与代码、能力点、决策一一对应；写错位置或写错状态，账本就失去可追溯性。

## 一、编号与命名

| 类别 | 规则 | 示例 |
|---|---|---|
| 方法论文档 | `docs/NN-中文标题.md`，NN 两位数字，顺序即阅读顺序 | `docs/09-历史与经验.md` |
| 规划文档 | `<project>/docs/plans/<HINT>_PLAN.md` 或 `*_ROADMAP.md` | `DATA_PIPELINE_PLAN.md` |
| 测试记录 | `<project>/docs/test_records/<HINT>_TEST_RECORD.md` | `PRICE_TEST_RECORD.md` |
| 决策 | 只在账本 `entries`，id `D-NNN`，永不复用 | `D-003` |
| 经验 | 只在账本 `lessons.items`，id `L-NNN`；候选 `LC-XXXXXX` | `L-001` |
| 能力编码 | `{项目}.{模块}.{能力域}.{NN}` | `DEMO.CORE.PRICE.02` |

**文件名里的 HINT 必须与 `registry.json` 中该能力的 `hints` 匹配**，否则生成器识别不到，能力不会升级。这是最容易被忽略的约定，已沉淀为示例经验 `L-001`。

## 二、每篇方法论文档的必备结构

1. **标题** —— `# NN · 主题`；
2. **为什么** —— 不写清动机，读者无法判断是否适用；
3. **机制** —— 可机读的字段、规则、流程，配最小 JSON 示例；
4. **怎么用** —— 命令或步骤，可直接复制；
5. **边界 / 反模式** —— 明确"不保证什么"，避免过度信任；
6. **关联** —— 指向相关文档、技能或账本字段。

禁止只有口号没有机制的文档；禁止复制一段看起来正确但无法执行的描述。

## 三、更新触发点

| 触发 | 必须更新 |
|---|---|
| 改生成器规则 | `03-编码与成熟度`、`08-可信性校验`、`CHANGELOG` |
| 改账本字段结构 | `02-决策账本`、`09-历史与经验` |
| 改看板视图 | `04-嵌套组件与文档索引`、`README` 视图清单 |
| 改技能 / 专家 | `10-AI集成`、`README` 目录结构 |
| 新增不变量 | `08-可信性校验` 表格 + 负向测试 |
| 新增 / 改名产物路径 | `15-文件架构`、`scripts/file_layout.py`、重新 `--emit-md`、`CHANGELOG` |
| 任何发布 | `CHANGELOG`、`RELEASE_CHECKLIST` |

代码变了文档没变，视为改动未完成。`scripts/check.sh` 的文档内链检查能保证链接有效，但**不能保证内容同步**——这仍需人判断。

## 四、状态词（全项目统一，不得自造）

- **决策**：`proposed`（待裁决）/ `decided`（已裁决）/ `done`（已完成）/ `deferred`（暂缓、需理由）/ `superseded`（已被取代）。
- **能力成熟度**：`L0` 规划 → `L1` 契约 → `L2` 实现 → `L3` 单测 → `L4` 运行验证 → `L5` 生产闭环。完成度恒等于 `level / 5`。
- **经验**：`draft` / `confirmed` / `retired`；候选为 `open` / `dismissed`。
- **历史事件**：`genesis`（基线）/ `change`（派生状态变化）/ `manual`（人工标注）。

## 五、路径约定

- 账本中所有路径相对**仓库根**，不用绝对路径、不用 `../` 拼接；
- 看板点击时统一拼接 `../../ + path`（示例位于 `examples/demo-shop/governance/`）；
- 路径必须真实存在，`verify_ledger.py` 会逐条检查；不写空链占位。
- **证据报告**：`governance/test_report.json` 用相对路径（相对运行 cwd），不写机器绝对路径；schema 固定 `ledger-test-report/1`。

## 六、生成文档目录

`docs/generated/` 下的 `PROJECT_BRIEF.md` / `MODULE_MAP.md` / `CAPABILITY_INDEX.md` / `GRAPH_DIFF.md` / `SCENARIO_MATRIX.md` / `FILE_LAYOUT.md`
由 `scripts/rebuild_docs.py` / `compare_graphs.py` / `scenario_matrix.py` / `file_layout.py` 从事实源渲染，
**不是人工文档**：不要长期手改，改事实源后重跑；需要保留人工补充时用不同文件名。
生成文档必须无机器绝对路径、可逐字节复现，并默认跳过既有文件（`--force` 才覆盖）。

## 七、反模式

- **散落报告**：把决策写进新的 Markdown 而不是账本 —— 账本随即失去唯一性；
- **手写完成度**：看起来美观，实际摧毁可复算性，校验器会抓；
- **手写 verified**：把能力 `evidence_tier` 手改为 `verified` 而无测试报告依据 —— `verified_tier_traceable` 会抓；
- **空链占位**：先写个"待补文档"路径 —— 路径检查失败，且给人虚假完整感；
- **改写历史**：删掉降级事件 —— 历史链断裂，校验器会抓；
- **无行动的经验**：只写"要重视" —— 无法进入任务卡，等于没写；
- **口径分裂**：CI 用一套命令、本地用另一套 —— 必然出现"本地过了 CI 挂了"。
- **治理目录里另起报告**：在 `governance/` 新建自制状态文档 —— 第二事实源，布局 `--diff` 会报越界。
- **把账本内字段当文件找**：`lifecycle.log` / `capability_model` 是 JSON 字段，补建同名文件会分裂状态。
