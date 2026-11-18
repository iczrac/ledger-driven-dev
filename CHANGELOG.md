# Changelog

本项目版本遵循语义化版本（SemVer）。

## [1.4.0] - 2026-11-18

反向回流闭环（L0 元层）落地。**只改方法论仓库权威源，不触碰任何已引入项目的账本
数据契约、不自动升级任何项目。**

### 决策依据

升级链原本是单向的：方法论仓库 → M1–M8 → 目标项目。真实试用踩到的坑如果只落在
目标项目的 `work_items` 里，下一个项目会重踩。两条判据决定顺序：

1. 治理系统的产出不是版本号，而是「下一个项目不再重踩」；测试全绿只证明自洽，
   不证明有效。
2. **基线不可后补**：升级后再采集，就永久丢掉了「升级前有哪些摩擦」。

因此「建反馈通道」必须排在「升级某个具体项目」之前，且两者不是二选一。

### 新增：`scripts/ledger_feedback.py`

- `export`：只读采集 `work_items` / `lessons.candidates` / `upgrade_log` /
  结构字段缺口 / 目标项目校验器的 `fail|na|warn` / 版本落差 / 校验器代际 /
  `--note` 人工补充，产出 `ledger-observations/1` JSONL。
- **绝不写目标项目**；写观察包需 `--apply --approved-by <人>`；
  `obs_id` 由内容派生，重复导出幂等，不含时间戳。
- 脱敏为数据驱动：项目标识从目标项目自己的 registry / 账本提取，代码里零硬编码
  项目名词；额外词表由 `--terms` 注入且不进仓库；绝对路径 / 邮箱 / 密钥按形状替换。
- `triage` 把观察收敛为四产物（`invariant` / `scenario` / `migration` /
  `regression`）或 `wontfix`；`check` 校验内容指纹、**产物引用必须指向真实文件**、
  关闭理由非空；`report` 按轴聚合。

### 升级流程变为「前 1 步 + 后 19 步」

- 新增 `PRE_UPGRADE`：升级动作之前导出 `feedback/baseline.jsonl`。
- `POST_UPGRADE` 末步（第 19 步）导出 `feedback/observations.jsonl`，供 diff 与 triage。
- `plan()` 输出新增 `pre_upgrade`；`check_definitions()` 校验首步 / 末步均为观察导出。

### 第一个真实观察包

`feedback/observations.jsonl`：12 条来自真实存量项目（多项目 monorepo、混合测试栈）
的匿名观察，`feedback_closed=3`（三态校验器、激活状态、外部报告适配器各自指向
真实产物），其余 9 条保持 `open` 作为后续版本处方。契约与协议见
`docs/22-反向回流.md`。

### 门禁与测试

- `check.sh` 新增 `反向回流` 阶段：闭环校验、`feedback_closed ≥ 1`、导出幂等。
- 新增 9 个回归（只读与幂等 / 写盘纪律 / 数据驱动脱敏 / 版本落差可观察 /
  **先失败后通过**的闭环 / 产物引用存在性 / 内容指纹 / 四产物必填 / wontfix），
  测试架构清单同步纳管 `tests/meta/test_feedback.py`。
- 28 份专家 / 技能资产 frontmatter 统一 1.4.0；`METHOD_VERSION` 同步。

## [1.3.0] - 2026-11-18

从「引入试用」反向回流的第一批：修掉假绿灯、永久待办与取证入口错配。
只改方法论仓库权威源，**不触碰任何已引入项目的账本数据契约**。

### R1 绿灯三态：`na` 不再算 `pass`

- 现象：校验器第 24 条在 `test_results` 缺失时直接记通过；`upgrade.py verify()`
  在「无实测报告」时同样记 `pass`。于是「24/24 全绿」可以出现在证据根本
  没接上的项目上——与 v0.5.0 修过的假绿灯属同一类。
- 修复：每条不变量返回 `status = pass | fail | na`，保留 `ok` 兼容旧调用方；
  `--strict` 只对 `fail` 返回 1；新增 `--require-active` 让 `na` 也算失败；
  `--json` 增加 `na` / `all_active` / `activation.inactive` 明示未启用项。
  `upgrade.py verify()` 的 `evidence_rebaseline` 无报告时改记 `na`，
  `summary` 增加 `na` 计数；`upgrade_complete` 明确只回答「升级动作是否完成」，
  不再被误读为「证据已激活」。

### R2 M8 永久 pending：迁移判定与写盘行为对齐

- 现象：`plan()` 把 `test_results` 键缺失当作待办，`apply()` 在没有实测报告时
  又不写这个键，于是每次升级都判 M8、`noop` 永假（v1.2.0 → v1.2.1 已重现）。
- 修复：新增 `_projection_stale()`——只有「报告存在但投影缺失 /
  `source_sha256` 过期」才需要 M8；无报告是合法的 `declared` 状态（E2），
  不再构成永久待办。无报告项目的第二次 `plan` 现在收敛为 `noop=True`。

### R3 取证入口：报告契约开放化

- 现象：`POST_UPGRADE` 第 1 步跑的是方法论仓库自身 `scripts/run_tests.py`，
  第 2 步却在目标项目消费该报告；且 `run_tests.py` 只支持 unittest discover，
  混合测试栈的项目无法产出报告，能力永远停在 `declared`。
- 修复：第 1 步改为在目标项目侧运行 `governance/run_tests.py`（仓库自测
  回归 CI）；`work_panel.py` 新增 `import-report`，把 JUnit XML、jest JSON
  或任意符合 `ledger-test-report/1` 的 JSON 规范化成同一份报告，带
  `source_adapter` 与同源 `evidence_binding`（路径全部项目根相对）。
  默认 dry-run，写盘需 `--apply --approved-by <人>`；空用例报告判
  `overall=fail`，绝不伪造全绿。规范化后仍走既有 `sync-tests` →
  生成器 `--strict-evidence` 链路。

**新增 7 个回归用例**（合计 202），24 条不变量、`check.sh` 全绿。
资产 frontmatter 版本统一 1.3.0；`method_assets` 摘要变化，
已升级项目需重新批准升级（M4 + M5）重绑。

## [1.2.1] - 2026-11-18

把 v1.2.0 首次接入一个真实存量项目（多项目 monorepo）时暴露的集成缺陷修掉。

### 修复：资产检查器不把项目自有技能当成方法论资产

- 现象：目标项目 `.workbuddy/skills/` 本来就有 17 个自有技能，其中一个没有
  `description` frontmatter。`route_expert.py --check-assets` 全量枚举目录，
  把它的格式差异判成方法论资产 `incomplete`，`post_upgrade` 第 18 步因此失败——
  而 28 份只读副本其实逐字节正确。
- 根因：`asset_root()` 选了项目级 `.workbuddy/` 后，`load_assets()` 没有区分
  「清单内安装的副本」与「项目本来就有的技能」。
- 修复：新增 `installed_manifest_paths()`，从 `governance/ASSET_MANIFEST.json`
  读 28 条清单路径作为 scope；`load_assets()` / `check_assets()` / `build()`
  只消费清单内资产，输出带 `scoped` / `asset_count`。清单缺失或 root 非项目级
  资产目录时保持全量枚举，方法论仓库自身行为不变。
- 负向证明：2 个新用例——项目自有技能缺 description 时仍 `ok`；清单内副本被删
  仍 fail-closed（`tests/views/test_assets.py`）。

### 引入试用附带发现（不属于本仓库缺陷）

- 旧账本缺 `history` / `lessons` 两个新版字段；用生成器自身的 `evolve()` 建立
  genesis 基线即可，不需要重算能力等级（该存量项目 47 个能力点等级一字未动）。
- 旧账本一条决策证据含机器绝对路径，触发 `scenario_guard` 的 `path_hygiene`
  BLOCK；归一为 `~/...` 后 24/24 不变量全绿、预检 0 block 可写。
- 多项目 monorepo 与单项目 registry 契约不匹配（场景矩阵 E7 gap）仍然成立；
  本次试用不运行生成器重算，避免把 4 项目结构压成 1 个。

**195 个 unittest 用例**（+2）、24 条不变量、`check.sh` 全绿。
资产 frontmatter 版本统一为 1.2.1；`method_assets` / `installed_assets` 摘要变化，
已升级项目需重新批准升级（M5 + M7）重绑。

## [1.2.0] - 2026-11-18

三个深化要求：专家和 skill 要**升级到可用**、测试文件要**按开发模块重新组织**、
看板要**深化成能显示 TODO / issue / 测试结果的工作台**。核对后发现 v1.1.0 的三处
都停在「可证明」而非「可使用」：

- `route_expert.py` 用硬编码 `EXPERT_CARDS` 路由，不读 `EXPERT.md` / `SKILL.md`；
  升级链路不往目标项目装资产，`method_assets.py` 只算摘要，目标项目里没有一份可加载的技能。
- `tests/` 17 个 `test_*.py` 扁平排列、按脚本横切命名；`check.sh` 里甚至并存
  `unittest discover` 与 `run_tests.py` 两套发现口径，却没有模块归属映射。
- 看板 8 个 tab / 4 个 `render*` 函数，`next_queue` 不渲染、`test_report.json` 只有汇总徽章；
  一个项目负责人看完看板，仍要回到聊天记录、issue 列表与 CI 日志里找答案。

### 新增：资产可用层

- **`scripts/asset_bundle.py`**（`asset-bundle/1`）：把 8 份 `EXPERT.md`、20 份 `SKILL.md`
  装成目标项目 `.workbuddy/{experts,skills}/` 下的**只读部署副本**，写
  `governance/ASSET_MANIFEST.json` 并在 `governance_meta.installed_assets` 绑定逐文件摘要。
  权威源仍是方法论仓库 tag；副本逐字节一致、禁止项目内编辑，手改即 `drift`，
  唯一修复是重新人批准安装。安装默认 dry-run、幂等；被人改过的旧副本列 `stale_protected` 保留。
- **`route_expert.py` 的 `load_assets()` / `asset_root()` / `--check-assets`**：路由真正读取
  `EXPERT.md` / `SKILL.md` frontmatter（`name` / `description` / `Triggers:`），
  优先消费目标项目已安装副本，缺文件即报 `incomplete`；不再用旧硬编码卡片指挥新骨架。
- **技能 `asset-install`**：`.workbuddy/` 只读副本、清单与账本绑定、M7、verify、禁止事项与失败处理。

### 新增：测试架构层

- **`tests/MODULES.json`**：6 个开发模块（`core` / `adoption` / `routing` / `meta` /
  `traceability` / `views`）、21 个测试文件的唯一清单。
- 每个测试文件带 `MODULE_ID` 自证归属；`scripts/run_tests.py` 的 `rglob("test_*.py")`、
  `unittest discover -s tests` 与清单三方交叉验证，模块名避开 Python 标准库冲突。
- **`scripts/test_modules.py`**：`--check` 校验清单 / `MODULE_ID` / 发现口径 / 语法；
  `--target P` 汇总目标项目每个能力模块的 `doc_index.unit_tests`，输出 `modules_without_tests[]`；
  `--emit-md` 渲染 `docs/generated/TEST_MODULES.md`。
- **技能 `test-map`**：测试模块映射与目标项目单测缺口。

### 新增：节点工作台

- 账本内新增 `work_items`（`PROJECT` / 模块 / 四段式能力编码三种作用域，上级向下覆盖）
  与 `test_results`（`node-test-results/1`，用 `source_sha256` 绑定 `test_report.json` 原始字节）。
- **`scripts/work_panel.py`**：`check` / `nodes` / `sync-tests` / `add` / `close`；
  写动作默认 dry-run 且必须 `--approved-by`；派生聚合由 `nodes` 与看板 JS 按同一规则复算、
  **不落盘**，因此不产生第三份事实源。
- **`templates/index.html.template`**：tab 8 → **10**（新增 `workbench` / `work`），
  `nodeWork()` / `workStripHtml()` 在模块、组件、能力点节点上显示 TODO / issue /
  逐用例结果与健康度；空账本不崩；骨架摘要由 `17f3dfba…` 归一到 `735bcd09…`。
- **技能 `work-panel`**：工作项数据契约、健康度公式与写入纪律。

### 单一事实源同步

- `upgrade.py`：版本五轴 → **六轴**（新增 `installed_assets`）；迁移 M1–M6 → **M1–M8**
  （M7 资产安装、M8 工作台字段）；`post_upgrade` 11 → **18 步**；`verify` 9 → **11 项**；
  `upgrade_complete` 需八项关键检查全 pass；回滚按白名单移除升级前不存在的副本。
- 校验器 21 → **24 条不变量**：`work_items_valid` / `work_item_refs_valid` /
  `test_results_binding_valid`；示例副本逐字节同步。
- `scenario_matrix.py`：54 → **60 场景 / 10 轴**，新增 U4 / U5 / V1 / V2 / V3 / T6；
  有效覆盖率 82.4% → **84.2%**（47 covered / 7 partial / 5 by-design / 1 gap）。
- `file_layout.py`：27 → **31 路径条目 / 12 账本内字段**，新增资产层 `.workbuddy/`、
  `.workbuddy/skills/`、`.workbuddy/experts/`、`governance/ASSET_MANIFEST.json`。
- `scale_budget.py`：9 → **10 项预算**，新增 `work_items`（warn 500 / hard 2000）。
- `check.sh`：测试阶段改为 `unittest discover` + `run_tests.py` 双口径并断言绑定 21 个
  模块内测试文件；新增「测试架构」阶段；升级端到端与契约阶段纳入
  `asset_bundle verify` / `work_panel check` / `route_expert --check-assets`。
- 新增 `docs/19-专家与技能可用.md`、`docs/20-测试架构与模块映射.md`、
  `docs/21-节点工作台与看板视图.md`（共 21 篇编号文档）；全仓数量 / 版本口径同步到 1.2.0。

### 结果与边界

**193 个 unittest 用例**（新增 21 个）、24 条不变量、`check.sh` 全绿。
诚实保留：生成器全量重算无增量索引（S2 `partial`）；E7 monorepo 联合门禁仍是唯一 `gap`；
网关仍是策略执行点而非 OS 沙箱；只读副本依赖 `verify` 主动检查，不是文件系统级只读保护；
`ledger_version` 数据契约迁移仍需人工专用方案。**没有引入第二事实源**。

## [1.1.0] - 2026-11-18

三个反问：专家和 skill 是否一起升级、项目 HTML 是否已有统一样式避免差异化版面、
项目大且需生成的文件数量多时是否有对应考量。核对后发现这三者都是**一致性约束**，
v1.0.0 只有隐含约定、没有可校验契约：

- 专家 / 技能 / 路由卡 / 模板 / 文档随仓库 tag 发版，但目标账本没记录这批资产；
  用旧专家卡指挥新骨架，`verify` 仍全绿。
- 看板同步器与 21 条不变量只校验 `EMBED` 数据段；项目手改 CSS、删 tab 或留着旧模板，
  `board_embed_synced` 照样通过，呈现规则分裂。
- 治理层文件数本来就固定，但账本 / 看板体积、历史事件全量快照与浏览器 DOM
  没有任何预算、分页或可复现基准。

### 新增

- **`scripts/method_assets.py`**（`method-assets/1`）：只读扫描 6 组资产
  （experts / skills / scripts / templates / 编号文档 / STANDARD），按相对路径聚合 sha256。
  摘要写进账本内 `governance_meta.method_assets`；任一资产变化 → `plan` 列 M5、
  `verify` 的 `method_assets` 变 warn、`upgrade_complete=false`。**资产不复制进目标项目**。
- **`scripts/board_contract.py`**（`board-contract/1`）：把 EMBED 换成占位符后对剩余全部字节
  取骨架 sha256；`check` 只读、`normalize` 默认 dry-run 且需人批准。
  `upgrade.py` 新增 M6，用唯一模板重建 CSS/DOM/JS，数据段仍由账本同步。
- **`templates/index.html.template`**：新增 `const PAGE_SIZE=200` 与通用 `moreHtml` / `bindMore`，
  条目 / 时间线 / 架构 / 模块 / 能力 / 历史 / 经验七个视图统一分批渲染；CSS 不变。
- **`scripts/scale_budget.py`**（`scale-budget/1`）：9 条阈值只读预算，报
  `ok / warn / exceed`；渲染上限直接从模板解析，避免口径漂移；不落盘报告、不拆账本。
- **`scripts/scale_probe.py`**（`scale-probe/1`）：临时目录合成大项目并真实跑生成器，
  量化耗时与体积。实测 50 能力/100 文件 → 0.135s、账本 184 KiB；
  400 能力/500 文件/30 事件 → 0.723s、2.1 MiB；
  1000 能力/1500 文件/80 事件 → 4.406s、9.4 MiB；**治理文件数始终为 4**。
- **三个技能**：`method-assets` / `board-layout` / `scale-budget`（共 17 个技能）；
  `platform-steward` 与 `evidence-auditor` 挂上新技能，路由 `migrate` 意图与推荐命令同步。
- **`docs/18-规模化与版面契约.md`**：三问的完整答案、阈值表、实测基准、超预算流程与反模式；
  `docs/16` 升为版本五轴 / 六条迁移 / 11 步 `post_upgrade` / 9 项 `verify`。

### 单一事实源同步

- `scenario_matrix.py`：50 → **54 场景 / 8 轴**，新增 U3、F8、S1（covered）与 S2（partial）；
  有效覆盖率 82.0% → **82.4%**（41 covered / 7 partial / 5 by-design / 1 gap）。
- `file_layout.py`：仍 27 条路径，账本内字段 9 → **10**（`method_assets` / `board_skeleton`）；
  `NOT_IN_TARGET` 对齐 `docs/01-18`，示例看板按新模板归一。
- `upgrade.py`：版本三轴 → **五轴**，M1–M6 迁移，`post_upgrade` 8 → **11 步**，
  `verify` 7 → **9 项**，`upgrade_complete` 需六项全 pass。
- `check.sh` 新增「资产与版面契约」阶段（`method_assets --check` / `board_contract check` /
  `scale_budget --check` / `scale_probe` 小档），`stage_sync` 增加示例骨架一致性检查。

### 结果与边界

**172 个 unittest 用例**（新增 16 个契约专项）、21 条不变量、`check.sh` 全绿。
诚实保留：生成器全量重算无增量索引（S2 `partial`）；E7 monorepo 联合门禁仍是唯一 `gap`；
F7 只检测 registry 漂移不自动合并；网关仍是策略执行点而非 OS 沙箱；
`ledger_version` 数据契约迁移仍需人工专用方案。

## [1.0.0] - 2026-11-17

从第一性原理回答四个问题：还应该补什么、怎么升级、升级后有没有流程、不同 Agent 如何接入控制开发。
结论是 v0.9.0 缺的不是功能，而是**两个层级**：

- **元层**：判定规则本身会变。已交付项目的 3 个工具副本会悄悄落后于模板，账本却仍自称可信；
  升级没有计划/备份/回滚/批准人；工具源码一变，`evidence_binding` 失配会让 `verified` 静默回落 `declared`。
- **接入控制层**：权限写在七份 `EXPERT.md` 的散文里，路由输出的是建议，guard 只读；
  Agent 只要有 shell 就能直接跑 `ledger_decide.py` / `lifecycle.py` 绕过全部纪律。
  **声明的权限不是权限，在写入口强制执行的最小权限才是权限。**

### 新增

- **`scripts/ledger_io.py`**：账本 + 看板 EMBED 的唯一落盘原语、sha256 内容摘要、registry 摘要、指纹取值。
  此前每个写入脚本各写一份，新写入口漏掉同步就会破 `board_embed_synced`。
- **`scripts/upgrade.py`**（`upgrade-plan/1` / `upgrade-apply/1` / `upgrade-verify/1`）：
  版本三轴（`method_version` / `ledger_version` / 3 个工具 sha256）写进账本内 `governance_meta`；
  `plan` 只读且确定性、`apply` 需人批准并先写带清单的备份、`verify` 7 项只读复验、
  `rollback` 按清单恢复并写回执。4 条迁移全部**只加字段**，因此不追加 `history.events`。
  `post_upgrade` 固定 8 步，把「重新绑定证据」变成升级流程的一部分。
- **`scripts/agent_gateway.py`**（`agent-gate/1`）：默认拒绝的九道门（身份 / 角色 / scopes / CAS /
  registry 摘要 / 人批准 / 生命周期 / 租约 / 场景预检），`status` / `register` / `request` / `check`；
  `ledger-write` 动作由网关亲自调用既有纯函数，`permit-only` 只签带指纹的许可。
  账本内 `access` 存名册、租约、`revision` 与 append-only `audit`，不新建第二事实源。
  并发三锁：`fcntl.flock` + 指纹 CAS + 编码租约；权限授予者 ≠ 被授权者。
- **硬耦合**：升级的 M2 建立默认拒绝的 `access` 登记；没有它，网关拒绝一切 Agent 请求。
  想让多个 Agent 接手开发，必然先经过一次有人批准的升级。
- **第八个专家 `platform-steward`** 与两个技能 `ledger-upgrade` / `agent-gate`；
  `route_expert.py` 新增 `access` 意图、`migrate`/`access` 元层分支（优先于项目状态）与升级/接入推荐命令。
- **`docs/16-升级与迁移.md`、`docs/17-多Agent接入控制.md`**：六阶段升级流程、升级后状态机、
  平台注入约定、角色权限矩阵，以及「策略执行点 ≠ OS 沙箱」的诚实边界。

### 单一事实源同步

- `scenario_matrix.py`：44 → **50 场景 / 7 轴**（新增 U 升级、G 接入两组）；
  T2 `partial→covered`、F7 `gap→partial`（检测漂移但不自动合并）、新增 G4 `by-design`；
  有效覆盖率 79.5% → **82.0%**，每项的探针都落在真实测试里。
- `file_layout.py`：24 → **27 条目**，新增运行时层 `.ledger-upgrade/` / `.ledger-write.lock`；
  账本内字段 7 → **9**（`governance_meta` / `access`），`NOT_IN_TARGET` 对齐 `docs/01-17`。
- `check.sh` 新增「升级与接入」端到端阶段：在临时副本上跑 plan→apply→verify→register→
  dry-run→apply→未注册拒绝，最后验证 21 条不变量仍全绿。
- `README` / `STANDARD` / `10-AI集成` / `12-专家路由` / `14-场景矩阵` / `15-文件架构` /
  `RELEASE_CHECKLIST` 与 `layout-inspect` 技能全面对齐。

### 验证

- 测试 127 → **156**（新增 12 个升级专项、15 个网关专项，另补 2 个元层路由用例）。
- `check.sh` 全绿：156 测试 / 证据分层 / 21 不变量 / 50 场景 / 27 条目布局 /
  升级与接入端到端 / 幂等 / 同步 / 脱敏 / 文档链接。

### 仍诚实保留的边界

E7 monorepo 多项目与跨仓联合门禁（唯一 `gap`）；F7 只检测 `registry.json` 漂移不自动合并；
G4 有 shell 的 Agent 仍可绕过网关，强隔离需容器 / 只读挂载 / CI 白名单；
`fcntl` 在 Windows 降级为告警；`ledger_version` 数据契约迁移仍需人工写专用方案。

## [0.9.0] - 2026-11-17

补齐「引入这套方案后，项目文件架构到底发生什么变化」。此前答案散落在 README 目录树、
初始化脚本 docstring 与各脚本的默认输出参数里，无法回答「哪些能改、哪些是生成物、
账本内字段是不是文件」，也无法发现示例骨架与实际初始化产物的漂移。

### 新增

- **`scripts/file_layout.py`**：`file-layout/1`，被治理项目文件布局的单一事实源 ——
  24 个目录 / 文件条目、7 个账本内字段、6 类「不会进入目标项目」的内容；
  每条标注分层、来源、出现时机、写入者、写入方式、能否手改、git 策略、保护机制与含义。
- **`--check`**：除定义自检外，逐条核对产出脚本源码里是否仍写着该文件名；
  清单与代码漂移直接失败（并有负向测试证明该检查不是摆设）。
- **`--diff --target P`**：全程只读，输出 `bootstrap / skeleton / governed` 阶段、
  已在位条目、缺失必需骨架、按需未跑产物，以及 `governance/` 下的越界文件
  （可能是第二事实源）；`--strict` 可直接进 CI。
- **`--emit-md`**：渲染 `docs/generated/FILE_LAYOUT.md` 目录全量表，与定义逐字节同源。
- **`docs/15-文件架构.md`**：引入前后目录树（greenfield / adopt 两种）、目录含义、
  五层所有权矩阵、生命周期时序、编码贯通链路、git 策略与反模式。
- **第十二个技能 `layout-inspect`**；`route_expert.py` 五张专家卡接入布局技能，其中四张附 `--diff` 推荐命令。
- `check.sh` 新增「文件布局」阶段：清单自检、渲染同步、示例骨架 `--diff --strict`、
  第 3 个工具副本 `cmp` 同步。

### 一致性修复

- 示例补齐 `governance/run_tests.py` 工具副本（v0.5 时代骨架缺它），纳入逐字节同步门禁。
- `init_project.py` docstring 从「生成器副本」对齐为实际 6 个文件 / 3 个工具副本；
  `lifecycle.py` 澄清 `lifecycle.log` 是**账本内 append-only 数组字段**，不是独立文件。
- `RELEASE_CHECKLIST.md` 历史记录「4 个文件正确生成」修正为 6 个。

### 验证

- 测试 113 → **127**（新增 14 个布局专项：自检、漂移拦截、渲染幂等、只读哈希、
  三态判定、越界报告、草稿层、缓存忽略、缺目录 fail-closed）。
- `check.sh` 全绿：127 测试 / 证据分层 / 21 条不变量 / 场景矩阵 / 文件布局 /
  幂等 / 同步 / 脱敏 / 文档链接。

## [0.8.1] - 2026-11-17

### 修复

- `scenario_guard.py` 的路径脱敏正则会把 `file://` 的 `e:/`、`https://` 的 `s:/`
  误判为 Windows 盘符绝对路径，导致项目被**假冻结**。收紧为「前面不邻 URI scheme 字符、
  后面不再跟斜杠」；真实 `/Users/...` 与 `C:/...` 仍被拦截。
- 新增负向用例证明 URL 不误报、真实绝对路径仍命中；测试 112 → **113**。

## [0.8.0] - 2026-11-17

从第一性原理反查「各种场景的流程应用」，发现 v0.7.0 的两类公理级盲区：证据只做了空间维度（文件存在）没做时间维度（证据是否过期），以及只有项目入口没有项目出口（冻结/归档/退役）。本期把场景覆盖变成可复算的矩阵，并补齐高危缺口。

### 新增

- **`scripts/scenario_matrix.py`**：44 个场景的单一事实源，覆盖 6 条公理 / 6 个轴；`--check` 自检定义、`--emit-md` 渲染 `docs/generated/SCENARIO_MATRIX.md`。covered 必须有探针、gap 必须写代价，覆盖状态由测试复算。
- **`scripts/scenario_guard.py`**：`scenario-preflight/1`，14 项只读预检（版本契约、冻结/归档、证据绑定与新鲜度、并发 CAS、退役冲突、任务锁、看板同步、git、脱敏、模板、扫描截断），输出 `allowed_actions` / `blocked_actions` / `route_hint`。
- **`scripts/lifecycle.py`**：冻结 / 解冻 / 归档 / 能力退役 / 任务领用的唯一写入口。状态写进账本内 `lifecycle` / `retired_caps` / `execution` 与 append-only `lifecycle.log`，**不新建第二事实源、不碰 history.events**，并自动同步看板 EMBED。
- **证据时间维度**：`run_tests.py` 报告新增 `evidence_binding`（逐测试文件 sha256）；生成器 `check_freshness()` 重算，源码变化即回落 `declared`；`--strict-evidence` 拒绝未绑定报告。
- **并发 CAS**：生成器 `--expect-fingerprint`，读取时指纹与当前不符则退出码 2、不写盘。
- **生命周期 fail-closed**：`frozen` / `archived` 下生成器拒绝写入；`unfreeze` / `archive` 强制 `--approved-by`。
- **第七个专家 `release-steward`** 与技能 `scenario-guard`；路由新增 `archive` / `migrate` / `retire` / `resume` 意图与 frozen/archived 状态。
- **`docs/14-场景矩阵.md`**：六公理推导、场景收敛判据、真缺漏清单、诚实保留的 2 个 gap 与 6 个 partial、四条端到端 playbook。

### 验证

- 测试 79 → **112**（场景矩阵 23 + 生命周期 10）；`check.sh` 新增场景矩阵阶段，幂等阶段启用 `--strict-evidence`。
- 21 条账本内部不变量保持不变；新检查独立成层，避免旧账本因上下文变化被误判腐化。

## [0.7.0] - 2026-11-17

用五个反问检验方法本身，并把每个"能"落成可复现脚本：文档重建、目标架构、git 追踪、规划/实际图比对、编码全链路对应。全部产物默认非破坏性，沿用同一套编码与专家路由。

### 新增

- **`scripts/rebuild_docs.py`**：从 registry + 账本渲染 `docs/generated/{PROJECT_BRIEF,MODULE_MAP,CAPABILITY_INDEX}.md`；剥离账本仓库根前缀、路径相对化、逐字节可复现，默认跳过既有文件。
- **`scripts/architect_from_docs.py`**：文档 → `TARGET_ARCHITECTURE.json`（`target-arch/1`），抽取目标、模块/入口、编码、`依赖: CODE`、`目标: L3`；置信度与警告明确降级，不与文件系统草稿混淆。
- **`scripts/trace_git.py`**：只读 `git log --name-only`，把真实变更路径映射到模块、能力编码、账本 `entry_ids` 与历史 `event_seqs`，产出 `GIT_TRACE.json`；不信任 commit message 自述。
- **`scripts/compare_graphs.py`**：规划图（目标架构，缺失时退回 registry）vs 实际图（账本）逐能力比对，五态 `aligned/in_progress/not_started/planned_only/actual_only`；输出 `GRAPH_DIFF.json` + `GRAPH_DIFF.md`，按 `next_queue` 给开发顺序、执行专家与前置条件。
- **`scripts/code_index.py`** + **`scripts/trace_common.py`**：共享路径归一与能力展开；`CODE_INDEX.json` 把 `PROJ.MODULE.DOMAIN.NN` 映射到文档/测试/代码/账本事件/决策/git 提交。
- **两个技能** `doc-rebuild` / `graph-compare`；专家路由技能表与建议命令同步更新。
- **`docs/13-可追溯性.md`**：逐条回答五个反问，给出完整闭环命令、状态语义、边界与反模式。

### 验证

- 新增 19 个 unittest 用例（文档重建/编码索引 7、文档架构/git 追踪 6、规划实际比对 6），总计 **79 个**，全在临时目录运行。
- `bash scripts/check.sh` 全绿：79 测试 / 证据分层 / 21 不变量 / 幂等 / 同步 / 脱敏 / 文档链接。
- 负向覆盖：无 git 仓库退出码 2、空文档降级为 `low`、既有产物不被覆盖、planned_only/actual_only 分派到正确专家。

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
