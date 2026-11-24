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
| 改看板视图 | `04-嵌套组件与文档索引`、`README` 视图清单、`board_contract.py` 骨架摘要（必变） |
| 改节点工作台 / `work_items` / `test_results` | `21-节点工作台与看板视图`、`work_panel.py`、`verify_ledger.py` 三条不变量、`scale_budget.py` 的 `work_items` 阈值 |
| 改技能 / 专家 | `10-AI集成`、`README` 目录结构 |
| 新增不变量 | `08-可信性校验` 表格 + 负向测试 |
| 文档生命周期升硬门 | `skills/ledger-verify`、`docs/08`、`RELEASE_CHECKLIST`；条件：连续 10 次 CI orphan=0 且 warn=0 + 人工批准 |
| 新增 / 改名产物路径 | `15-文件架构`、`scripts/file_layout.py`、重新 `--emit-md`、`CHANGELOG` |
| 改账本字段结构 | `02-决策账本`、`15-文件架构` 的 LEDGER_FIELDS、`09-历史与经验` |
| 改工具副本 / 版本契约 | `16-升级与迁移`、`upgrade.py` 的 TOOLING / MIGRATIONS、`CHANGELOG` |
| 改专家 / 技能 / 路由卡 / 编号文档 | `method_assets.py --check` 与 `asset_bundle.py --check`（两个摘要必变）、`10-AI集成`、`12-专家路由`、`16-升级与迁移`、`18-规模化与版面契约`、`19-专家与技能可用`；所有目标项目需重新批准升级（M5 + M7） |
| 改测试模块归属 | `tests/MODULES.json`、`MODULE_ID`、`test_modules.py --check`、`20-测试架构与模块映射`、重跑 `--emit-md` 提交 `TEST_MODULES.md` |
| 改看板模板 / CSS / DOM / `PAGE_SIZE` | 归一化示例看板、`board_contract.py` 骨架摘要、`scale_budget.py` 预算、`15-文件架构`、`18-规模化与版面契约`、`CHANGELOG` |
| 改规模阈值 / 基准口径 | `scale_budget.py` 的 `BUDGETS`、`scale_probe.py`、`18-规模化与版面契约`、`14-场景矩阵` |
| 改角色 / 动作 / 权限 | `10-AI集成`、`12-专家路由`、`17-多Agent接入控制`、`route_expert.py`、`agent_gateway.py` |
| 改场景定义 | 重新 `--emit-md` 渲染 `SCENARIO_MATRIX.md`，同步 `14-场景矩阵` 与探针 |
| 任何发布 | `CHANGELOG`、`RELEASE_CHECKLIST` |

代码变了文档没变，视为改动未完成。`scripts/check.sh` 的文档内链检查能保证链接有效，但**不能保证内容同步**——这仍需人判断。

## 四、词表：按实体分型的状态机

**「状态词全项目统一」是错的**。不同实体本来就该有不同的状态机；把它们压成一个
词表会丢掉语义。统一的是**形式**而不是**取值**：任何状态词必须写成
`<Type>.field`，裸 `status` / `level` / `severity` 视为同形异义
（`polyseme_violation`）。`scripts/ontology.py` 同时读本表与各脚本里的真实枚举，
`build` 比对两者，`diff` 把不一致输出成 `affected_axis=ontology` 的观察。

| 实体 | 字段 | 取值域 | 实现来源 |
|---|---|---|---|
| Agent | role | evidence-auditor · expert-router · goal-orchestrator · greenfield-architect · ledger-steward · loop-executor · platform-steward · project-archaeologist · release-steward | scripts/agent_gateway.py#ROLE_POLICIES |
| Capability | evidence_tier | declared · verified | templates/build_capability_model.py#EVIDENCE_TIER_SPEC |
| Capability | level | L0 · L1 · L2 · L3 · L4 · L5 | templates/build_capability_model.py#LEVELS |
| Check | status | fail · na · pass | templates/verify_ledger.py#三态语义 |
| Decision | status | decided · deferred · done · proposed · superseded | entries[].status |
| HistoryEvent | kind | change · genesis · manual | templates/build_capability_model.py#HISTORY_SPEC |
| Lesson | status | confirmed · draft · retired | templates/verify_ledger.py#LESSON_STATUS |
| LessonCandidate | status | dismissed · open | templates/build_capability_model.py#LESSONS_SPEC |
| Observation | affected_axis | access · board_skeleton · evidence · general · hygiene · installed_assets · ledger_version · lifecycle · method_assets · method_version · ontology · registry · scale · test_results · tool_hashes · work_items | scripts/ledger_feedback.py#AXES |
| Observation | disposition | invariant · migration · regression · scenario · wontfix | scripts/ledger_feedback.py#DISPOSITIONS |
| Observation | severity | high · low · med | scripts/ledger_feedback.py#make_obs |
| Observation | status | closed · open | feedback/observations.jsonl |
| Scenario | status | by-design · covered · gap · partial | scripts/scenario_matrix.py#STATUSES |
| TestReport | source_adapter | auto · jest · junit · ledger | scripts/work_panel.py#ADAPTERS |
| TestResult | case_status | error · fail · pass · skip | scripts/work_panel.py#CASE_STATUSES |
| WorkItem | kind | issue · todo | scripts/work_panel.py#KINDS |
| WorkItem | severity | high · low · med | scripts/work_panel.py#SEVERITIES |
| WorkItem | status | blocked · doing · done · open | scripts/work_panel.py#STATUSES |

四条序数尺度互不换算，也不得互相替代：`level`（能力成熟度，完成度恒等于
`level / 5`）、`evidence_tier`（证据层级）、`severity`（风险严重度）、
`confidence`（断言置信度，必须可回溯到 `evidence_binding`）。

新增状态词的正确流程：先改实现里的枚举 → 同步改本表 → 跑
`python3 scripts/ontology.py build --apply --approved-by <人>` → `check`。
只改代码不改本表会被判 `undeclared_value`；只改本表不改代码会被判
`undeclared_entity`。

## 五、路径约定

- 账本中所有路径相对**仓库根**，不用绝对路径、不用 `../` 拼接；
- 看板点击时统一拼接 `../../ + path`（示例位于 `examples/demo-shop/governance/`）；
- 路径必须真实存在，`verify_ledger.py` 会逐条检查；不写空链占位。
- **证据报告**：`governance/test_report.json` 用相对路径（相对运行 cwd），不写机器绝对路径；schema 固定 `ledger-test-report/1`。

## 六、生成文档目录（双作用域）

`docs/generated/` 在两个作用域下都有，但**内容不同，不能混列**——这是「区分」的关键：

| 作用域 | 目录 | 生成物 | 生产者 | 是否入方法资产摘要 |
|---|---|---|---|---|
| 目标项目 | `<project>/docs/generated/` | `PROJECT_BRIEF.md` / `MODULE_MAP.md` / `CAPABILITY_INDEX.md` / `PROJECT_STATE.md` / `GRAPH_DIFF.md` | `rebuild_docs.py` / `compare_graphs.py` | 否（项目派生层） |
| 方法论仓库自身 | `ledger-driven-dev/docs/generated/` | `SCENARIO_MATRIX.md` / `FILE_LAYOUT.md` / `TEST_MODULES.md` / `ONTOLOGY.md` / `ONTOLOGY.json` | `scenario_matrix.py` / `file_layout.py` / `test_modules.py` / `ontology.py` | 否（派生不纳入） |

两类都**不是人工文档**：不要长期手改，改事实源后重跑；需要保留人工补充时用不同文件名。
生成文档必须无机器绝对路径、可逐字节复现，并默认跳过既有文件（`--force` 才覆盖）。
权威的全量目录清单在 [`generated/FILE_LAYOUT.md`](generated/FILE_LAYOUT.md)，由 `scripts/file_layout.py --emit-md` 渲染，
不要在本节手抄第二份清单。

## 七、反模式

- **散落报告**：把决策写进新的 Markdown 而不是账本 —— 账本随即失去唯一性；
- **手写完成度**：看起来美观，实际摧毁可复算性，校验器会抓；
- **手写 verified**：把能力 `evidence_tier` 手改为 `verified` 而无测试报告依据 —— `verified_tier_traceable` 会抓；
- **空链占位**：先写个"待补文档"路径 —— 路径检查失败，且给人虚假完整感；
- **改写历史**：删掉降级事件 —— 历史链断裂，校验器会抓；
- **无行动的经验**：只写"要重视" —— 无法进入任务卡，等于没写；
- **口径分裂**：CI 用一套命令、本地用另一套 —— 必然出现"本地过了 CI 挂了"。
- **治理目录里另起报告**：在 `governance/` 新建自制状态文档 —— 第二事实源，布局 `--diff` 会报越界。
- **把账本内字段当文件找**：`lifecycle.log` / `capability_model` / `governance_meta` / `access` 是 JSON 字段，补建同名文件会分裂状态。
- **把权限写成文档就算完成**：`EXPERT.md` 只是角色说明，必须同时有 `agent_gateway.py` 的执行点；没有默认拒绝，散文不是权限。
- **在项目里改 CSS 追平版面**：模板才是唯一版式事实源；项目内改样式只会制造第二套呈现规则，并被骨架摘要判为漂移。
- **项目变大就拆账本 / 删历史事件**：治理文件数本来就固定，体积靠预算与分批渲染管理；拆账本会破坏单一事实源。
- **升级只跑 apply 不跑 post_upgrade**：工具源码变了但证据过期，`verified` 会静默回落 `declared`。
