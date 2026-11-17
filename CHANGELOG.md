# Changelog

本项目版本遵循语义化版本（SemVer）。

## [0.6.0] - 2026-11-17

把「谁来动手」纳入同一套可信体系：新增确定性专家路由与两类项目入口。历史项目先盘点、草稿人工确认后才接入；新项目从最小骨架起步。写权限按角色拆分，冲突与损坏一律 fail-closed。

### 新增

- **专家路由** `scripts/route_expert.py`：只读扫描账本/registry/源码/测试/文档状态，结合中英文意图确定性选出唯一负责人；输出 `expert-route/1` JSON，含 `detected_mode`、`needs_clarification`、`handoff` 与建议命令。账本损坏、意图互斥、显式模式与事实冲突时冻结或要求澄清。
- **存量项目发现** `scripts/discover_project.py`：只读盘点历史资产，产出 `registry.draft.json` 与 `ADOPTION_REPORT.md`；文件数/能力数有上限，警告（无测试、无文档、扫描截断）全部保留；既有草稿默认跳过，`--force` 才覆盖；路径相对化，不写账本与源码。
- **双模式初始化** `init_project.py --mode greenfield|adopt --from-draft --intent`：接入模式消费已确认草稿，账本写入 `provenance`（mode/source/intent/discovery）与 `D-001` 接入事实；绝不覆盖既有治理文件，外部路径只保留文件名。
- **六种专家角色**：新增 `expert-router`、`greenfield-architect`、`project-archaeologist`、`evidence-auditor`、`loop-executor`，原 `ledger-steward` 保持 governed 状态默认负责人；每份 `EXPERT.md` 含权限矩阵、停止条件与交接模板。
- **三个技能**：`expert-route`、`project-discover`、`project-bootstrap`，与原有五个技能共同构成八技能接口。
- **文档** `docs/12-专家路由.md`：第一性原理推导、专家名册、路由优先级、新建/接入两条完整路径、交接协议与反模式。
- **测试** 新增 23 个用例（`test_routing` / `test_discovery` / `test_bootstrap`），覆盖状态识别、冲突澄清、fail-closed、输出确定性、只读盘点、非破坏性与接入后生成+21 条校验通过。

### 修复

- 全文过时表述统一为 21 条不变量（此前 README/技能/指南/发布说明仍写 18 条）；校验器 docstring 补齐实际 21 项编号，并同步示例副本。
- `init_project.py` 的草稿缺失/格式错误统一返回退出码 2，便于 CI 与编排层区分「输入不合法」和「运行失败」。

## [0.5.0] - 2026-11-17

从第一性原理修复判定层的根本断裂：原 L0-L5 只看证据文件是否存在，空测试文件也能拿 L3 绿灯——一套宣称消灭假绿灯的方法自己在制造假绿灯。引入正交的证据分层，让完成度能区分"写了测试"与"测试真过了"。

### 新增

- **证据分层** `evidence_tier`：`declared`（文件存在）/ `verified`（有通过的测试报告）。等级回答"做到哪级"，分层回答"证据是声明还是实测"，两者正交。看板每个能力点显示徽章，规模栏显示 verified 覆盖率。
- **`scripts/run_tests.py`**：标准库 unittest 跑测试，产出 `ledger-test-report/1` JSON 报告（每用例文件/状态/耗时）。导入失败计 fail、0 用例计 fail，防止"0 用例假通过"。报告路径归一，不含机器绝对路径。
- **生成器 `--test-report`**：读报告判定 verified（文件名 basename 匹配 + status=pass + overall=pass）；不传则行为与旧版一致。tier 进入历史指纹（真实升级记为事件，报告元数据不进指纹，重跑幂等）。任务卡携带 tier 与 `needs_runtime_verification`。
- **校验器 +3 条不变量**（共 21 条）：`evidence_tier_valid`、`verified_tier_traceable`、`verified_tier_not_premature`，离线验证账本内部自洽，防手改 verified。
- **`docs/11-证据分层.md`**：完整讲清第一性断裂、正交维度、报告格式、判定规则、防腐化与 CI 衔接。
- **check.sh 证据分层阶段**：生成实测报告 → 确认整体通过 → 再进账本校验；幂等阶段带同一份报告保证 verified 稳态不漂移。

### 修复

- 示例 demo-shop 的 3 个测试原为 pytest 函数风格，与"零依赖标准库 unittest"承诺不一致；改为 `unittest.TestCase`，报告现在能捕获它们。
- 历史测试对 schema 迁移（新增 tier 字段）敏感：幂等/新增证据测试改为先跑一次建立基线，再断言稳态，区分"一次性迁移"与"幂等失败"。

## [0.4.0] - 2026-11-17

补齐三份契约：角色（Expert）、动作（Skill）、工程（文档 / 测试 / CI/CD）。方法从"给人读的说明书"变成"AI 可直接接手的接口"。

### 新增

- **账本治理专家** `experts/ledger-steward/EXPERT.md`：角色、五条信念、权限矩阵、标准工作流、决策/经验写入模板、停止条件与边界。
- **五个技能** `skills/`：ledger-scan、ledger-verify、ledger-decide、ledger-lesson、ledger-guard，标准 SKILL.md frontmatter，每个含触发词、输入输出契约、命令、禁止事项与失败处理。
- **可执行脚本** `scripts/ledger_decide.py`（从 next_queue 写 proposed，拒绝重复立项）、`scripts/ledger_lesson.py`（确认/驳回经验，强制 insight + action）、`scripts/check.sh`（本地/CI/发布前统一门禁）。纪律在代码层强制，不依赖 Agent 记得。
- **文档标准化** `CONTRIBUTING.md`、`docs/STANDARD.md`（命名/章节/状态词/更新触发点）、`docs/10-AI集成.md`（安装与平台无关消费路径）。
- **测试套件** `tests/` 30 个 unittest 用例：生成契约、指纹与历史幂等、校验器负向注入、技能纪律；零第三方依赖，全部在临时目录运行。
- **CI/CD** `.github/workflows/ci.yml`（Python 3.10-3.13 矩阵 + 看板 JS 语法）与 `release.yml`（tag 触发，先门禁后打包）。

### 修复

- 看板 EMBED 同步把"状态未变、内容相同"误判为"未找到标记"——跨分钟重跑正常、同分钟重跑失败。改为先检查标记存在，替换用 lambda 避免反斜杠转义。由统一门禁的幂等阶段发现并验证。

## [0.3.0] - 2026-11-17

补齐时间维度：账本不只记录「现在是什么」，还记录「怎么走到今天」与「学到的东西如何复用」。

### 新增

- **历史层**：对派生状态（等级/完成度/证据/文档索引/决策引用）计算稳定指纹；仅真实变化才追加 append-only 事件，重跑幂等。事件含 diff 与完整 `state_digest`，可回放任意时点。
- **经验层**：从历史自动识别 `downgrade` / `stagnation` / `superseded_decision` 三类候选（稳定 id 去重）；人确认后写成 `items`，`next_queue` 任务卡按 scope 自动携带已确认经验。
- **校验扩展到 18 条**：新增历史链连贯、事件指纹自证、末事件与当前状态一致、经验条目合法、候选去重、任务卡只引用 confirmed 经验。校验器独立实现指纹算法，与生成器交叉验证。
- **看板两视图**：「演进历史」时间线（等级迁移红绿高亮、指纹链、状态快照回放）与「经验库」（已确认/候选分区、来源事件可跳转）；能力点展开可见相关经验与变更历史。
- **文档** [09-历史与经验](docs/09-历史与经验.md)，并更新 README / 05-循环协议 / 08-可信性校验。

### 修复

- 经验候选去重曾把所有已存在 open 候选都排除，导致候选在「消失—重现」间交替；改为只排除 dismissed 与已转成条目的候选，连续三次重跑验证幂等。

## [0.2.0] - 2026-11-17

从第一性原理出发，补齐「可信」与「驱动」两个核心承诺的机制。

### 新增

- **可信性校验器** `verify_ledger.py`：11 条不变量机器化检查（编码格式/唯一性、完成度与等级一致、文档与组件路径存在、决策引用与取代链一致、registry 来源真实性、看板与账本同步）。支持 `--json`（CI/AI 可读）与 `--strict`（失败返回非零退出码）。已通过负向测试验证能抓到注入的腐化。
- **SELECT 任务队列** `capability_model.next_queue`：生成器把循环协议的 SELECT 步骤机器化，产出按完成度升序的任务列表，每条含目标编码、等级跃迁、具体动作、缺失证据、关联文档与决策。dry-run 同样打印。
- **文档** [08-可信性校验](docs/08-可信性校验.md)，并更新 05-循环协议（VERIFY 增加账本自洽层、SELECT 改为机器化产出）。
- `init_project.py` 初始化时一并复制校验器，并提示校验步骤。

## [0.1.0] - 2026-11-17

首个可发布版本：从真实项目迭代中沉淀的方法论与可复用模板。

### 新增

- **决策账本**：单一事实源，含状态机（proposed/decided/done/deferred/superseded）与取代链。
- **四段式能力编码** `{项目}.{模块}.{能力域}.{序号}` 与 L0-L5 成熟度判定（证据驱动、禁止手填、可回落）。
- **嵌套组件树**：从真实目录提取 目录→子目录→文件，深度/规模可控，关键模块优先。
- **文档索引**：每个能力点 8 类文档索引 + 关联决策，路径存在性校验，看板可见可点。
- **循环协议**：SCAN→SELECT→PLAN→EXECUTE→VERIFY→VISUALIZE，供 AI 规划与编码消费。
- **可复用模板**：`build_capability_model.py`（仅标准库、路径参数化）、`index.html.template`、`registry.example.json`。
- **一键初始化脚本** `init_project.py`。
- **脱敏示例** `examples/demo-shop`，含已生成的账本与可离线打开的看板。
- **七篇方法论文档** + README + LICENSE。

### 设计取舍

- 只用 Python 标准库，零第三方依赖；
- 看板离线可用（内嵌账本副本），联网时优先 fetch 实时数据；
- 可复算优先于可编辑：只手写 registry，其余自动生成。
