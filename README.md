# Ledger-Driven Dev（账本驱动开发）

> 用**一份可机读的账本**取代散落的报告，把「做了什么、做到什么程度、对应哪些文档、下一步干什么」收敛成单一事实源；再由看板渲染成可视化，供人查阅、供 AI 规划与编码。

这是一套从真实项目迭代中沉淀出来的**开发与方法论 + 可复用模板**。它不绑定任何具体技术栈，只用标准库，复制模板即可接入你自己的项目。

同一套账本要服务两类场景：**历史项目无损接入**与**新项目从零起步**。为此方法内置了专家路由：先只读判定项目状态与任务意图，再把写权限交给唯一合适的专家。

---

## 它解决什么问题

多数项目迭代久了会出现四类熵增：

| 症状 | 后果 |
|---|---|
| 决策散落在聊天、报告、会议纪要 | 无法追溯「当初为什么这么定」，反复推翻 |
| 能力边界不清 | 说不清哪个模块做到什么程度，重复造轮子 |
| 文档与代码脱节 | 索引看不见、点不开，文档成了墓碑 |
| AI 无法接手 | 没有可机读的 next_action，自动编程无从下手 |

本方法用四个机制对应解决：

1. **决策账本** —— 所有重大决策/裁决/待办只写一份 JSON，用取代链表达演进。
2. **能力编码 + 成熟度** —— 四段式编码给每个能力点唯一身份证，L0-L5 由证据自动判定，不允许手填完成度。
3. **嵌套组件树 + 文档索引** —— 项目→模块→嵌套组件→能力→文档，索引可见、可点开。
4. **循环协议** —— SCAN→SELECT→PLAN→EXECUTE→VERIFY→VISUALIZE，把账本变成驱动 AI 迭代的输入。
5. **历史层** —— append-only 事件流，由状态指纹自动侦测真实变化；只有证据/等级/文档真的变了才记一笔，重跑不产生噪音，任意时点可回放。
6. **经验层** —— 从历史自动识别可沉淀信号（降级/长期停滞/决策被推翻），人确认后写成经验，**下一轮任务卡自动携带**。
7. **专家路由** —— 只读扫描项目状态与任务意图，确定性选出唯一负责人：历史项目走考古专家（草稿优先、绝不覆盖），新项目走架构师（最小骨架、来源可追溯），校验与编码各有边界。冲突时要求澄清，**不让多个 Agent 同时改同一份事实源**。
8. **可追溯闭环** —— 事实源可重建规范文档，文档可抽目标架构，git 变更可回连模块决策与历史事件；规划图与实际图按编码逐项比对，由专家给出执行顺序，并用全链路编码索引对齐文档/测试/代码/账本。
9. **场景预检** —— 写入前先判定「现在能不能动」：证据是否过期、有没有并发覆盖、是否冻结/归档、版本是否兼容；60 个场景（10 个轴）的覆盖状态由测试复算，而不是文档自称。
10. **可升级 + 可授权** —— 治理骨架升级有人批准的 plan/备份/回滚与 18 步升级后 SOP；多 Agent 经唯一写入网关接入，默认拒绝、最小权限、CAS、租约与 append-only 审计。
11. **文件架构清单** —— 引入后多出哪些目录、每层归谁写、哪些能改、哪些是账本内字段，由 `file_layout.py` 定义并与产出脚本源码交叉验证；`--diff` 只读检查任意项目的现状。
12. **资产 / 版面 / 规模契约** —— 专家与技能整包摘要绑定进账本（升级 M5），看板 CSS/DOM/JS 骨架与模板强一致（M6），大规模项目有只读预算、统一分页与可复现基准；治理层文件数不随项目规模增长。
13. **专家 / 技能真正可用** —— 升级 M7 把 8 份 `EXPERT.md`、20 份 `SKILL.md` 以**只读部署副本**装进项目 `.workbuddy/`，逐文件摘要写进 `ASSET_MANIFEST.json` 与账本 `governance_meta.installed_assets`；路由改为真实读取资产正文，项目内手改即判 drift。权威源仍是方法论仓库，副本不是第二事实源。
14. **测试按开发模块组织** —— `tests/MODULES.json` 定义 6 个开发模块 / 21 个测试文件，文件内 `MODULE_ID` 自证归属，`rglob` 与 `unittest discover` 双口径交叉验证；`--target P` 能列出目标项目缺单测的能力模块。
15. **节点工作台** —— 账本内 `work_items` / `test_results` 让每个项目、模块、组件、能力点直接显示 TODO、issue、逐用例测试结果与健康度；看板新增工作台 / 工作项两个视图和节点工作条。

并且这套方法**自身可被验证**：`verify_ledger.py` 把 24 条不变量机器化（含历史链、经验引用与证据分层），`next_queue` 把 SELECT 变成机器可读任务队列——「可信」和「驱动」两个核心承诺都不再停留在文字上。

**证据分层**进一步区分「写了测试文件」与「测试真实通过」：`declared`（文件存在）与 `verified`（有通过的测试报告）。一个 L5 能力若从没跑过测试，会显示 `declared`——假绿灯从此可见。详见 [11-证据分层](docs/11-证据分层.md)。

## 核心理念

> **完成度不是写出来的，是从证据里算出来的。**

生成器扫描真实文件系统：契约、实现、单测、测试记录、治理门禁，逐级判定 L0-L5。证据消失，等级自动回落。于是看板上的每一个百分比都能追到具体文件，无法造假。

在此之上，证据分层再问一句「测试真跑过吗」：`declared` 只看文件存在，`verified` 必须有通过的测试报告（`scripts/run_tests.py` 用标准库产出）。等级回答"做到哪一级"，分层回答"证据是声明还是实测"——两者正交，假绿灯无处遁形。

## 目录结构

```
ledger-driven-dev/
├── README.md                         本文件
├── docs/                             方法论文档
│   ├── 01-问题与原则.md
│   ├── 02-决策账本.md
│   ├── 03-编码与成熟度.md
│   ├── 04-嵌套组件与文档索引.md
│   ├── 05-循环协议.md
│   ├── 06-落地指南.md
│   ├── 07-反模式与边界.md
│   ├── 08-可信性校验.md
│   ├── 09-历史与经验.md
│   ├── 10-AI集成.md                  专家与技能的安装与消费
│   ├── 11-证据分层.md                声明级 / 验证级，消除假绿灯
│   ├── 12-专家路由.md                多专家协作、历史/新建双路径
│   ├── 13-可追溯性.md                五项反问、文档/架构/git/图比对闭环
│   ├── 14-场景矩阵.md                第一性原理、60 场景覆盖、生命周期流程
│   ├── 15-文件架构.md                引入前后目录变化、目录含义与所有权
│   ├── 16-升级与迁移.md              版本六轴、六阶段升级、升级后重新取证 SOP
│   ├── 17-多Agent接入控制.md         默认拒绝的网关、租约、审计与接入流程
│   ├── 18-规模化与版面契约.md       资产绑定、看板骨架、规模预算与基准
│   ├── 19-专家与技能可用.md         只读部署副本、清单绑定与路由消费
│   ├── 20-测试架构与模块映射.md     按开发模块组织测试与三方自证
│   ├── 21-节点工作台与看板视图.md   TODO / issue / 测试结果与节点健康度
│   ├── generated/SCENARIO_MATRIX.md  机器渲染的覆盖矩阵（勿手改）
│   ├── generated/FILE_LAYOUT.md      机器渲染的目录全量表（勿手改）
│   ├── generated/TEST_MODULES.md     机器渲染的测试模块映射（勿手改）
│   └── STANDARD.md                   文档命名/章节/状态词规范
├── experts/
│   ├── expert-router/EXPERT.md        路由决策与交接契约（只读调度）
│   ├── greenfield-architect/EXPERT.md 新建项目架构师
│   ├── project-archaeologist/EXPERT.md 存量项目考古专家
│   ├── ledger-steward/EXPERT.md       账本治理专家（默认循环负责人）
│   ├── evidence-auditor/EXPERT.md     证据审计专家（只读门禁）
│   ├── loop-executor/EXPERT.md        循环执行专家（一条任务卡）
│   ├── release-steward/EXPERT.md      生命周期与发布治理专家
│   └── platform-steward/EXPERT.md     升级与多 Agent 接入的规划协调（不替人批准）
├── skills/
│   ├── expert-route/                  专家路由
│   ├── project-discover/              存量项目只读发现
│   ├── project-bootstrap/             新建 / 接入初始化
│   ├── ledger-scan/                   重跑生成器
│   ├── ledger-verify/                 24 条不变量 + 修复表
│   ├── ledger-decide/                 任务卡 → proposed 决策
│   ├── ledger-lesson/                 候选 → 已确认经验
│   ├── ledger-guard/                  统一质量门禁
│   ├── doc-rebuild/                   规范文档 + 编码索引
│   ├── graph-compare/                 目标/实际图比对与执行顺序
│   ├── scenario-guard/                写入前预检、生命周期状态门
│   ├── layout-inspect/                文件架构分层、引入前后差异与只读检查
│   ├── ledger-upgrade/                升级计划、备份、复验、回滚与重新取证
│   ├── agent-gate/                    多 Agent 唯一写入口与默认拒绝门禁
│   ├── method-assets/                 专家/技能/模板/文档整包摘要与升级绑定
│   ├── board-layout/                  看板骨架契约、统一版面与归一化
│   ├── scale-budget/                  规模预算、分批渲染与可复现基准
│   ├── asset-install/                 安装只读专家/技能副本到 .workbuddy/
│   ├── test-map/                      测试模块映射与目标项目单测缺口
│   └── work-panel/                    节点工作项与测试结果投影
├── templates/                        可复用模板（复制到你的项目）
│   ├── build_capability_model.py     核心生成器（含证据分层/历史/经验/任务队列）
│   ├── verify_ledger.py              24 条不变量校验器（可信的基础设施）
│   ├── index.html.template           可视化看板
│   └── registry.example.json         能力注册表样板
├── scripts/
│   ├── route_expert.py               确定性专家路由（只读）
│   ├── discover_project.py           存量项目只读发现（草稿）
│   ├── init_project.py               新建 / 存量接入初始化
│   ├── run_tests.py                  标准库跑测试 → 机器可读报告（verified 证据源）
│   ├── ledger_decide.py              决策写入（纪律由代码保证）
│   ├── ledger_lesson.py              经验确认 / 驳回
│   ├── rebuild_docs.py               规范化文档重建
│   ├── code_index.py                 编码 ↔ artifact 全链路索引
│   ├── architect_from_docs.py        文档 → 目标架构
│   ├── trace_git.py                  git → 模块 / 决策 / 事件
│   ├── compare_graphs.py             规划图 vs 实际图 + 执行顺序
│   ├── scenario_guard.py             场景预检（证据/并发/生命周期/版本）
│   ├── scenario_matrix.py            场景定义单一事实源 → 矩阵文档
│   ├── lifecycle.py                  冻结/归档/退役/任务领用状态机
│   ├── file_layout.py                引入后文件布局单一事实源（check/diff/emit-md）
│   ├── ledger_io.py                  账本 + 看板 EMBED 的唯一落盘原语
│   ├── upgrade.py                    治理骨架升级（plan/apply/verify/rollback/check）
│   ├── agent_gateway.py              多 Agent 唯一写入口（status/register/request/check）
│   ├── method_assets.py              方法论资产整包摘要（只读）
│   ├── asset_bundle.py               专家/技能只读部署副本（install/verify）
│   ├── board_contract.py             看板骨架契约（check/normalize）
│   ├── scale_budget.py               规模预算（只读告警）
│   ├── scale_probe.py                生成器规模基准（临时目录）
│   ├── work_panel.py                 节点工作台（check/nodes/sync-tests/add/close）
│   ├── test_modules.py               测试模块映射与 --target 缺口报告
│   └── check.sh                      本地 / CI 统一门禁
├── tests/                            按 6 个开发模块组织的 unittest 套件
│   ├── MODULES.json                  模块 → 测试文件 → 所属脚本的唯一清单
│   └── core/ adoption/ routing/ meta/ traceability/ views/
├── .github/workflows/                CI 与 release
├── CONTRIBUTING.md                   贡献与同步规则
└── examples/
    └── demo-shop/                    跑通的脱敏示例（含真实产出）
        └── governance/
            ├── registry.json
            ├── DECISION_LEDGER.json   已生成（含 verified 能力）
            ├── test_report.json       实测报告（verified 证据源）
            ├── index.html             可直接打开（徽章显示声明/实测）
            └── build_capability_model.py
```

## 快速开始

### 方式一：看示例（30 秒）

直接用浏览器打开 `examples/demo-shop/governance/index.html`。它内嵌了完整账本，离线可看。切换顶部 10 个标签：全部条目 / 待裁决 / **工作台** / **工作项** / 时间线 / 模块地图 / 架构钻取 / 能力地图 / 演进历史 / 经验库，另有跨条目全文搜索。示例里有真实的两次生成历史（含一次 L2→L5 跃迁）、一个停滞候选、一条已确认经验，以及 4 条挂在模块 / 能力点上的 TODO 与 issue。

### 方式二：接入自己的项目（5 分钟）

先让路由看一眼，不要凭描述猜模式：

```bash
python3 scripts/route_expert.py --target /path/to/your-project --intent "接手现有项目"
# 空目录 → greenfield-architect；有历史代码但无账本 → project-archaeologist
# 加 --json 可拿到机器可读的状态、理由与建议命令
```

**新建项目（空目录）**：

```bash
python3 scripts/init_project.py --target /path/to/new --code MYPROJ --name "我的项目" \
  --intent "新建项目"
```

**历史项目（有代码/测试/文档，无账本）**：

```bash
python3 scripts/discover_project.py --target /path/to/legacy --dry-run   # 先看报告
python3 scripts/discover_project.py --target /path/to/legacy             # 生成草稿
# 人工精简 governance/registry.draft.json（删非能力文件、合并重复域、校准 hints）
python3 scripts/init_project.py --target /path/to/legacy --mode adopt \
  --from-draft /path/to/legacy/governance/registry.draft.json --code LEG
```

两条路径之后相同：编辑 `governance/registry.json`（唯一需要手工维护的清单）→ 试跑 → 生成 → 校验：

```bash
cd /path/to/your-project
python3 governance/build_capability_model.py --root . --dry-run
python3 governance/build_capability_model.py --root .

# 可选：跑测试并升级证据为 verified，区分"写了测试"与"测试真过了"
python3 governance/run_tests.py --dir tests --out governance/test_report.json
python3 governance/build_capability_model.py --root . --test-report governance/test_report.json

python3 governance/verify_ledger.py --root . --strict
open governance/index.html
```

之后每次代码/测试/文档有变更，重跑一次生成器即可——完成度、组件树、文档索引、**历史演进**、**经验候选**与**下一轮任务队列**全部自动刷新。状态没变时重跑不会产生新历史事件（幂等）。存量接入的草稿、源码与既有治理文件不会被自动覆盖。

### 五项反问 → 一条可追溯闭环

```bash
# 1) 规范化文档重建   2) 文档 → 目标架构
python3 scripts/rebuild_docs.py --target /path/to/project
python3 scripts/architect_from_docs.py --target /path/to/project

# 3) git 更新 → 模块 / 决策 / 历史事件
python3 scripts/trace_git.py --target /path/to/project --max-count 50

# 4) 规划图 vs 实际图 → 开发顺序 + 专家
python3 scripts/compare_graphs.py --target /path/to/project \
  --git-trace /path/to/project/governance/GIT_TRACE.json

# 5) 编码 ↔ 文档 / 测试 / 代码 / 账本 / git
python3 scripts/code_index.py --target /path/to/project \
  --git-trace /path/to/project/governance/GIT_TRACE.json
```

产物默认落在 `docs/generated/` 与 `governance/`，全部非破坏性（需 `--force` 才覆盖）。详见 [13-可追溯性](docs/13-可追溯性.md)。

### 引入后文件架构：先看目录再动手

```bash
python3 scripts/file_layout.py --check
python3 scripts/file_layout.py --diff --target /path/to/project
python3 scripts/file_layout.py --diff --target /path/to/project --strict
```

`--diff` 全程只读，返回 `bootstrap / skeleton / governed` 阶段、缺失必需骨架、
`governance/` 下的越界文件（可能是第二事实源）与下一步提示。
完整目录含义、七层所有权、git 策略与账本内字段澄清见
[15-文件架构](docs/15-文件架构.md) 与 [目录全量表](docs/generated/FILE_LAYOUT.md)。

### 任意写入前的场景预检

```bash
FP=$(python3 -c "import json;print(json.load(open('governance/DECISION_LEDGER.json'))['capability_model']['history']['current_fingerprint'])")
python3 scripts/scenario_guard.py --target /path/to/project --expect-fingerprint "$FP" --strict

# 写入时带上同一份指纹与强证据开关
python3 governance/build_capability_model.py --root . \
  --test-report governance/test_report.json \
  --expect-fingerprint "$FP" --strict-evidence
```

`verified` 现在绑定到**当前源码的内容摘要**：跑过测试后再改代码，徽章会自动回落 `declared`。
冻结/归档期间生成器直接拒绝写入；解冻与归档必须有人批准。详见 [14-场景矩阵](docs/14-场景矩阵.md)。

### 升级治理骨架 + 让多个 Agent 接入控制开发

规则本身会过期，已交付项目的 3 个工具副本也会落后于模板。升级是一次**有人批准的写入**，不是覆盖文件：

```bash
python3 scripts/route_expert.py --target P --intent "升级治理骨架" --json  # → platform-steward
python3 scripts/upgrade.py --target P plan --json                          # 只读计划 + 18 步 post_upgrade
python3 scripts/upgrade.py --target P apply --approved-by "审批人姓名"     # 先备份再加字段/归一骨架
# 按 post_upgrade 重跑报告 → 生成器 --strict-evidence → verify/board/budget/assets/guard/layout
python3 scripts/upgrade.py --target P verify --json
python3 scripts/board_contract.py --target P check --json                  # 骨架与样式是否统一
python3 scripts/scale_budget.py --target P --json --check                 # 大项目预算
python3 scripts/method_assets.py --check                                  # 专家/技能资产是否齐备
python3 scripts/asset_bundle.py verify --target P --json                  # 项目内副本是否可用且未漂移
python3 scripts/route_expert.py --target P --check-assets --json           # 路由读的是不是真实资产正文
python3 scripts/work_panel.py --target P check --json                     # 节点工作台字段是否自洽
python3 scripts/test_modules.py --target P --json                         # 哪些能力模块还缺单测
```

升级会建立账本内的 `access` 登记（默认拒绝），这是多 Agent 接入的**前置条件**：

```bash
python3 scripts/agent_gateway.py --target P register \
  --agent ci-agent --role loop-executor --approved-by "审批人姓名" --apply
python3 scripts/agent_gateway.py --target P status --json   # 取 fingerprint / registry_sha256
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action claim --code MYPROJ.CORE.X.01 --expect-fingerprint "$FP" --json       # dry-run
python3 scripts/agent_gateway.py --target P request --agent ci-agent \
  --action claim --code MYPROJ.CORE.X.01 --expect-fingerprint "$FP" --apply      # 才写
```

平台注入时**只把 `agent_gateway.py` 注册为写工具**；`ledger_decide.py` / `ledger_lesson.py` /
`lifecycle.py` 保留为人工逃生舱。网关是策略执行点而非 OS 沙箱，需要强隔离请用容器或只读挂载。
详见 [16-升级与迁移](docs/16-升级与迁移.md) 与 [17-多Agent接入控制](docs/17-多Agent接入控制.md)。

### 节点工作台：在模块 / 组件上看 TODO、issue 与测试结果

升级 M7 会把专家 / 技能装成**项目内只读副本**（见 [19](docs/19-专家与技能可用.md)），
M8 则初始化节点工作台字段。测试是否按模块组织、哪个模块还缺单测，由
[20](docs/20-测试架构与模块映射.md) 描述；看板上的工作态由
[21](docs/21-节点工作台与看板视图.md) 描述。

```bash
python3 scripts/asset_bundle.py install --target P --apply \
    --approved-by "审批人姓名" --json          # 单独补装只读专家/技能副本
python3 scripts/test_modules.py --check                       # 校验测试模块映射
python3 scripts/work_panel.py --target P nodes --json         # 只读取证：每个节点的健康度
python3 scripts/work_panel.py --target P sync-tests \
    --apply --approved-by "审批人姓名"          # 把测试报告投影进账本
python3 scripts/work_panel.py --target P add --kind todo \
    --scope MYPROJ.CORE --title "补齐模块契约" \
    --apply --approved-by "审批人姓名"
```

`work_items` 的 `scope` 可为 `PROJECT` / 项目 / 模块 / 四段式能力编码，上级作用域自动向下覆盖；
`test_results` 用 `source_sha256` 绑定 `test_report.json` 原始字节，手填哈希会被
24 条不变量中的 `test_results_binding_valid` 拦下。派生聚合由 `nodes` 与看板 JS 按同一规则复算，
不落盘、不产生第三份事实源。

### 验证账本可信

```bash
python3 governance/verify_ledger.py --root . --strict
```

它会检查 24 条不变量：编码唯一且格式正确、完成度与等级一致、文档/组件路径全部存在、决策引用与取代链一致、看板与账本同步；**历史链连续且前后指纹衔接、事件指纹自证、末事件与当前状态一致；经验条目合法、候选去重、任务卡只引用已确认经验；证据分层取值合法、verified 可追溯且不越级**。任何一条失败说明账本已腐化，不能作为决策依据。`--json` 输出机器可读结果，可直接接入 CI。

### 统一质量门禁（提交前 / CI / 发布前）

```bash
bash scripts/check.sh
```

一条命令跑完：标准库单元测试（双发现口径）→ 测试架构映射 → 证据分层（生成实测报告并确认 verified 判定）→ 24 条不变量 → 场景矩阵 → 文件布局清单与只读 diff → 升级与多 Agent 接入端到端 → 资产/骨架/规模/节点工作台契约 → 生成器幂等 → 模板/示例同步与看板 EMBED → 脱敏与文档内链。本地与 CI 用同一份脚本，口径一致。单个能力校验用 `verify_ledger.py`，完整交付用 `check.sh`。

### AI 接手：专家路由与技能

- **八个专家**：`expert-router`（调度）、`greenfield-architect`（新建）、`project-archaeologist`（存量）、`ledger-steward`（账本治理）、`evidence-auditor`（只读审计）、`loop-executor`（一条任务卡的编码）、`release-steward`（冻结/归档/退役与批准门）、`platform-steward`（升级与接入的规划协调）。每个都有权限矩阵、停止条件与交接模板。
- **二十个技能**：`expert-route` / `project-discover` / `project-bootstrap` 覆盖路由、盘点、初始化；`doc-rebuild` / `graph-compare` 覆盖规范文档、编码索引与图比对；`scenario-guard` 覆盖写入前预检；`layout-inspect` 覆盖引入后文件架构；`ledger-upgrade` / `agent-gate` 覆盖升级与多 Agent 接入；`method-assets` / `board-layout` / `scale-budget` 覆盖资产摘要、统一版面与规模预算；`asset-install` / `test-map` / `work-panel` 覆盖只读资产安装、测试模块映射与节点工作台；原有五个技能覆盖扫描、校验、立项、经验与门禁。
- 纪律不只写在文档里：`route_expert.py` 对冲突 fail-closed，`discover_project.py` 默认不覆盖草稿，`init_project.py` 跳过既有治理文件，`ledger_decide.py` / `ledger_lesson.py` 在代码层拒绝重复立项与缺行动的经验，`agent_gateway.py` 把权限变成默认拒绝的写入执行点。

详见 [12-专家路由](docs/12-专家路由.md)、[13-可追溯性](docs/13-可追溯性.md)、[14-场景矩阵](docs/14-场景矩阵.md)、[15-文件架构](docs/15-文件架构.md)、[16-升级与迁移](docs/16-升级与迁移.md)、[17-多Agent接入控制](docs/17-多Agent接入控制.md)、[18-规模化与版面契约](docs/18-规模化与版面契约.md)、[19-专家与技能可用](docs/19-专家与技能可用.md)、[20-测试架构与模块映射](docs/20-测试架构与模块映射.md)、[21-节点工作台与看板视图](docs/21-节点工作台与看板视图.md) 与 [10-AI集成](docs/10-AI集成.md)。

### SELECT 产出：下一轮任务队列

生成器把循环协议的 SELECT 步骤机器化了——`capability_model.next_queue` 是一组按完成度升序排列的任务，每条含目标编码、当前→目标等级、具体动作、缺失证据类型、关联文档与决策，以及**按 scope 匹配的已确认经验**。**人和 AI 拿到一条即可开工，既知道缺什么，也知道前人踩过什么坑**。dry-run 也会打印这个队列。

## 看板十个视图

- **全部条目 / 待裁决 / 时间线**：决策账本的三个切面，取代链可追溯。
- **模块地图**：模块 ↔ 源码 ↔ 文档 ↔ 控制中心 ↔ 决策，一屏对应。
- **架构钻取**：项目 → 模块 → **嵌套组件树**（逐层展开）→ 文档索引 → 能力编码 → 决策控制。
- **能力地图**：每个能力点显示等级、完成度、规划（下一等级）与**可点开的文档索引**；展开可看该能力的相关经验与变更历史；点模块里的能力编码可跳转定位。
- **演进历史**：append-only 事件时间线，等级迁移红绿高亮，指纹链可见，当时状态快照可展开回放。
- **经验库**：已确认经验与待确认候选分区展示，来源事件可点击跳回历史，适用范围一目了然。
- **工作台**：按项目 / 模块 / 组件 / 能力点汇总 TODO、issue、逐用例结果与健康度，可下钻到工作项。
- **工作项**：全部 TODO / issue 的状态、severity、scope 与引用，可按节点筛选。
- **节点工作条**：模块地图、架构钻取、能力地图的每个节点都带一条工作条，未关闭问题与失败用例直接可见。
- **搜索**：跨决策、模块、能力、历史事件与经验全文检索。
- **统一版面 / 分批渲染**：CSS/DOM/JS 来自唯一模板（骨架 sha256 可校验），各视图按 `PAGE_SIZE=200` 分批，大项目不会一次渲染上万张卡片；换样式必须改模板并发版，禁止项目内自定义。

## 设计取舍

- **只用标准库**：生成器无第三方依赖，任何有 Python 3 的环境都能跑。
- **离线可用**：看板把账本内嵌为副本，`file://` 直接打开也能看；联网时优先 fetch 实时账本。
- **可复算优先于可编辑**：宁可让人维护一份 `registry.json`，也不让看板数据被手改到失真。
- **如实记录不做**：`deferred` 状态专门记录「暂缓/另案」，避免用假绿灯粉饰未完成的能力。

## 文档导航

1. [问题与原则](docs/01-问题与原则.md) —— 为什么需要这套方法，背后的设计原则
2. [决策账本](docs/02-决策账本.md) —— 账本结构、状态机、取代链
3. [编码与成熟度](docs/03-编码与成熟度.md) —— 四段式编码与 L0-L5 证据规则
4. [嵌套组件与文档索引](docs/04-嵌套组件与文档索引.md) —— 组件树与索引如何生成
5. [循环协议](docs/05-循环协议.md) —— 如何驱动 AI 迭代与自动编程
6. [落地指南](docs/06-落地指南.md) —— 从零接入的分步清单
7. [反模式与边界](docs/07-反模式与边界.md) —— 常见误区与不适用情形
8. [可信性校验](docs/08-可信性校验.md) —— 24 条不变量，让「可信」可被验证
9. [历史与经验](docs/09-历史与经验.md) —— 状态指纹驱动的演进历史，以及可被任务卡消费的经验层
10. [文档规范](docs/STANDARD.md) —— 命名、章节、状态词与更新触发点
11. [AI 集成](docs/10-AI集成.md) —— 专家、二十个技能与平台无关的最小消费路径
12. [证据分层](docs/11-证据分层.md) —— 区分声明级与验证级证据，消除假绿灯
13. [专家路由](docs/12-专家路由.md) —— 多专家协作、历史/新建双路径与交接协议
14. [可追溯性](docs/13-可追溯性.md) —— 五项反问、文档/架构/git/图比对闭环
15. [场景矩阵](docs/14-场景矩阵.md) —— 第一性原理、60 场景、十轴与已知缺漏
16. [文件架构](docs/15-文件架构.md) —— 引入前后目录变化、七层所有权与 git 策略
17. [升级与迁移](docs/16-升级与迁移.md) —— 版本六轴、六阶段升级、升级后重新取证与回滚
18. [多 Agent 接入控制](docs/17-多Agent接入控制.md) —— 默认拒绝的网关、租约、审计与接入流程
19. [规模化与版面契约](docs/18-规模化与版面契约.md) —— 资产绑定、看板骨架、预算与实测基准
20. [贡献指南](CONTRIBUTING.md) —— 开发循环、同步规则与发布流程
21. [专家与技能可用](docs/19-专家与技能可用.md) —— 只读部署副本、清单绑定与路由真实消费
22. [测试架构与模块映射](docs/20-测试架构与模块映射.md) —— 6 个开发模块 / 21 个测试文件与三方自证
23. [节点工作台与看板视图](docs/21-节点工作台与看板视图.md) —— TODO / issue / 测试结果与节点健康度

## License

MIT —— 可自由用于个人或商业项目。
