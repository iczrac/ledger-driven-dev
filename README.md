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

并且这套方法**自身可被验证**：`verify_ledger.py` 把 21 条不变量机器化（含历史链、经验引用与证据分层），`next_queue` 把 SELECT 变成机器可读任务队列——「可信」和「驱动」两个核心承诺都不再停留在文字上。

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
│   └── STANDARD.md                   文档命名/章节/状态词规范
├── experts/
│   ├── expert-router/EXPERT.md        路由决策与交接契约（只读调度）
│   ├── greenfield-architect/EXPERT.md 新建项目架构师
│   ├── project-archaeologist/EXPERT.md 存量项目考古专家
│   ├── ledger-steward/EXPERT.md       账本治理专家（默认循环负责人）
│   ├── evidence-auditor/EXPERT.md     证据审计专家（只读门禁）
│   └── loop-executor/EXPERT.md        循环执行专家（一条任务卡）
├── skills/
│   ├── expert-route/                  专家路由
│   ├── project-discover/              存量项目只读发现
│   ├── project-bootstrap/             新建 / 接入初始化
│   ├── ledger-scan/                   重跑生成器
│   ├── ledger-verify/                 21 条不变量 + 修复表
│   ├── ledger-decide/                 任务卡 → proposed 决策
│   ├── ledger-lesson/                 候选 → 已确认经验
│   └── ledger-guard/                  统一质量门禁
├── templates/                        可复用模板（复制到你的项目）
│   ├── build_capability_model.py     核心生成器（含证据分层/历史/经验/任务队列）
│   ├── verify_ledger.py              21 条不变量校验器（可信的基础设施）
│   ├── index.html.template           可视化看板
│   └── registry.example.json         能力注册表样板
├── scripts/
│   ├── route_expert.py               确定性专家路由（只读）
│   ├── discover_project.py           存量项目只读发现（草稿）
│   ├── init_project.py               新建 / 存量接入初始化
│   ├── run_tests.py                  标准库跑测试 → 机器可读报告（verified 证据源）
│   ├── ledger_decide.py              决策写入（纪律由代码保证）
│   ├── ledger_lesson.py              经验确认 / 驳回
│   └── check.sh                      本地 / CI 统一门禁
├── tests/                            标准库 unittest 测试套件
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

直接用浏览器打开 `examples/demo-shop/governance/index.html`。它内嵌了完整账本，离线可看。切换顶部标签体验九个视图：全部条目 / 待裁决 / 时间线 / 模块地图 / 架构钻取 / 能力地图 / **演进历史** / **经验库** / 搜索。示例里有真实的两次生成历史（含一次 L2→L5 跃迁）、一个停滞候选和一条已确认经验。

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

### 验证账本可信

```bash
python3 governance/verify_ledger.py --root . --strict
```

它会检查 21 条不变量：编码唯一且格式正确、完成度与等级一致、文档/组件路径全部存在、决策引用与取代链一致、看板与账本同步；**历史链连续且前后指纹衔接、事件指纹自证、末事件与当前状态一致；经验条目合法、候选去重、任务卡只引用已确认经验；证据分层取值合法、verified 可追溯且不越级**。任何一条失败说明账本已腐化，不能作为决策依据。`--json` 输出机器可读结果，可直接接入 CI。

### 统一质量门禁（提交前 / CI / 发布前）

```bash
bash scripts/check.sh
```

一条命令跑完：标准库单元测试 → 证据分层（生成实测报告并确认 verified 判定）→ 21 条不变量 → 生成器幂等 → 模板/示例同步与看板 EMBED → 脱敏与文档内链。本地与 CI 用同一份脚本，口径一致。单个能力校验用 `verify_ledger.py`，完整交付用 `check.sh`。

### AI 接手：专家路由与技能

- **六个专家**：`expert-router`（调度）、`greenfield-architect`（新建）、`project-archaeologist`（存量）、`ledger-steward`（账本治理）、`evidence-auditor`（只读审计）、`loop-executor`（一条任务卡的编码）。每个都有权限矩阵、停止条件与交接模板。
- **八个技能**：新增 `expert-route` / `project-discover` / `project-bootstrap`，覆盖路由、盘点、初始化；原有五个技能覆盖扫描、校验、立项、经验与门禁。
- 纪律不只写在文档里：`route_expert.py` 对冲突 fail-closed，`discover_project.py` 默认不覆盖草稿，`init_project.py` 跳过既有治理文件，`ledger_decide.py` / `ledger_lesson.py` 在代码层拒绝重复立项与缺行动的经验。

详见 [12-专家路由](docs/12-专家路由.md) 与 [10-AI集成](docs/10-AI集成.md)。

### SELECT 产出：下一轮任务队列

生成器把循环协议的 SELECT 步骤机器化了——`capability_model.next_queue` 是一组按完成度升序排列的任务，每条含目标编码、当前→目标等级、具体动作、缺失证据类型、关联文档与决策，以及**按 scope 匹配的已确认经验**。**人和 AI 拿到一条即可开工，既知道缺什么，也知道前人踩过什么坑**。dry-run 也会打印这个队列。

## 看板九个视图

- **全部条目 / 待裁决 / 时间线**：决策账本的三个切面，取代链可追溯。
- **模块地图**：模块 ↔ 源码 ↔ 文档 ↔ 控制中心 ↔ 决策，一屏对应。
- **架构钻取**：项目 → 模块 → **嵌套组件树**（逐层展开）→ 文档索引 → 能力编码 → 决策控制。
- **能力地图**：每个能力点显示等级、完成度、规划（下一等级）与**可点开的文档索引**；展开可看该能力的相关经验与变更历史；点模块里的能力编码可跳转定位。
- **演进历史**：append-only 事件时间线，等级迁移红绿高亮，指纹链可见，当时状态快照可展开回放。
- **经验库**：已确认经验与待确认候选分区展示，来源事件可点击跳回历史，适用范围一目了然。
- **搜索**：跨决策、模块、能力、历史事件与经验全文检索。

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
8. [可信性校验](docs/08-可信性校验.md) —— 21 条不变量，让「可信」可被验证
9. [历史与经验](docs/09-历史与经验.md) —— 状态指纹驱动的演进历史，以及可被任务卡消费的经验层
10. [文档规范](docs/STANDARD.md) —— 命名、章节、状态词与更新触发点
11. [AI 集成](docs/10-AI集成.md) —— 专家、八个技能与平台无关的最小消费路径
12. [证据分层](docs/11-证据分层.md) —— 区分声明级与验证级证据，消除假绿灯
13. [专家路由](docs/12-专家路由.md) —— 多专家协作、历史/新建双路径与交接协议
14. [贡献指南](CONTRIBUTING.md) —— 开发循环、同步规则与发布流程

## License

MIT —— 可自由用于个人或商业项目。
