# FILE_LAYOUT · 引入方案后的文件布局

> 本文件由 `scripts/file_layout.py` 从布局定义渲染；请勿手改。
> schema `file-layout/1` · 条目 36 · 引入后新增 31 项 · 账本内字段 12 项。

## 分层含义

| 层 | 含义 |
|---|---|
| 业务层 | 引入前就存在的代码 / 测试 / 文档，方法只规定命名约定，不搬迁、不改写 |
| 事实源层 | 唯一需要人维护或裁决的输入；所有结论都从这里复算 |
| 派生层 | 由脚本从事实源重算，禁止手改；改事实源后重跑即可 |
| 工具层 | 模板复制进目标项目的可执行副本，只读运行，升级靠同步模板 |
| 资产层 | 专家/技能的只读部署副本，唯一权威源仍是方法论仓库 tag |
| 草稿层 | 存量接入时的临时候选，人工确认前不得成为事实源 |
| 运行时层 | 升级备份与写入互斥锁；不属于事实源、不参与结论复算、不进 governance/ |

## 目录与文件清单

「写入」列：manual 人写 / bootstrap 初始化写一次 / rewrite 全量重算 / write-if-absent 默认跳过 / append-only 只追加 / read-only 只读。

| 路径 | 层 | 来源 | 出现时机 | 谁写 | 写入 | 手改 | git | 含义 / 保护 |
|---|---|---|---|---|---|---|---|---|
| `src/` | 业务层 | 引入前可能已有 | 原有资产，不强制 | 开发者 | `manual` | 可 | 建议提交 git | 实现代码。registry 的 impls 必须指向这里真实存在的文件。　保护：registry.impls 路径校验。 |
| `tests/` | 业务层 | 引入前可能已有 | 原有资产，不强制 | 开发者 | `manual` | 可 | 建议提交 git | 单元测试。文件名与 unit_test 声明匹配，测试报告绑定其内容摘要。　保护：evidence_binding 源码摘要。　注：测试源码改动后 verified 会自动回落 declared，需重跑测试报告。 |
| `docs/` | 业务层 | 引入前可能已有 | 原有资产，不强制 | 开发者 | `manual` | 可 | 建议提交 git | 人工文档根目录；其下再分 plans / test_records / generated。　保护：doc_index 路径校验。 |
| `docs/plans/` | 业务层 | 引入前可能已有 | 原有资产，不强制 | 开发者 | `manual` | 可 | 建议提交 git | 规划文档 <HINT>_PLAN.md / *_ROADMAP.md，是 L1 契约证据之一。　保护：HINT 文件名匹配。　注：HINT 必须与 registry 的能力 hints 一致，否则生成器识别不到。 |
| `docs/test_records/` | 业务层 | 引入前可能已有 | 原有资产，不强制 | 开发者 | `manual` | 可 | 建议提交 git | 测试记录 <HINT>_TEST_RECORD.md，是 L4 运行验证证据之一。　保护：HINT 文件名匹配。　注：与 docs/generated/ 区分：这里是人写的实测记录，那里是机器渲染。 |
| `governance/` | 事实源层 | 引入方案后新增 | 治理骨架必需 | init_project.py | `bootstrap` | 禁 | 建议提交 git | 治理目录：事实源、派生报告与工具副本都收敛在此，不另建管理项目。　保护：scenario_guard 越界文件检查。　注：此目录出现清单外的自制报告 / 第二份账本会被 --diff 报为越界。 |
| `governance/registry.json` | 事实源层 | 引入方案后新增 | 治理骨架必需 | 人（唯一手写清单） | `manual` | 可 | 建议提交 git | 能力注册表：项目信息、模块清单、impls / hints / unit_test 声明。全项目唯一需手填的清单。　保护：registry_impls_exist / component_paths_exist。　注：新建为空清单；存量接入来自人工确认后的 registry.draft.json。多人同改仍需 git 合并。 |
| `governance/DECISION_LEDGER.json` | 事实源层 | 引入方案后新增 | 治理骨架必需 | 生成器 / 决策脚本 / 生命周期脚本 | `rewrite` | 禁 | 建议提交 git | 单一事实源：entries 决策、capability_model 派生结果、history、lessons、lifecycle 全在这里。　保护：31 条不变量 / --expect-fingerprint CAS / frozen 冻结 / 看板 EMBED 同步。　注：可以写 entries（经 ledger_decide.py），但 level / completion / history / EMBED 一律自动派生，禁止手改。 |
| `governance/index.html` | 派生层 | 引入方案后新增 | 治理骨架必需 | build_capability_model.py / lifecycle.py / upgrade.py / board_contract.py | `rewrite` | 禁 | 建议提交 git | 可视化看板；EMBED 与账本逐字节等价，CSS/DOM/JS 骨架与权威模板一致、按 PAGE_SIZE 分批渲染。　保护：board_embed_synced 不变量 + 去 EMBED 后的骨架 sha256（board_contract.py）。　注：lifecycle.py 改状态时同步 EMBED；禁止在项目里改样式，换版面要改模板并发版再由 upgrade 归一。 |
| `governance/vendor/` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | upgrade.py | `rewrite` | 禁 | 建议提交 git | 治理目录下的本地前端依赖目录；当前只放 D3，避免 CDN 与后端依赖。　保护：relative file:// path。　注：由 upgrade.py 创建；目录内文件必须逐项登记，禁止手工塞入第二套事实源。 |
| `governance/vendor/d3.v7.min.js` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | upgrade.py | `rewrite` | 禁 | 建议提交 git | 本地 D3 v7 运行时：供追溯树、趋势与热力图做离线交互，不访问 CDN、不引后端。　保护：upgrade.py TOOLING 摘要一致 / file:// 相对路径加载 / hasD3() 降级。　注：由方法仓下发；删除后看板自动回退原生 SVG / details 树，禁止在项目内改版本。 |
| `governance/test_report.json` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | run_tests.py | `rewrite` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 机器可读测试报告，schema ledger-test-report/1；是 verified 证据的唯一来源。　保护：evidence_binding 逐文件 sha256 / --strict-evidence。　注：报告绑定测试源码内容摘要；源码一改就判 stale，verified 回落 declared。 |
| `governance/TARGET_ARCHITECTURE.json` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | architect_from_docs.py | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 从规范文档抽取的目标架构：目标 / 模块 / 能力编码 / 依赖 / target_level。　保护：置信度 warnings。　注：结构化抽取而非自然语言理解；差异只报告，不自动回写 registry。 |
| `governance/GIT_TRACE.json` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | trace_git.py | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 提交 → 变更路径 → 模块 / 能力编码 / 决策 id / 历史事件序号的映射。　保护：只读 git log --name-only。　注：不信任 commit message，只认真实变更路径；force-push 重写历史无法本地证明。 |
| `governance/GRAPH_DIFF.json` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | compare_graphs.py | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 规划图 vs 实际图的机器可读差异，附开发顺序、执行专家与前置条件。　保护：五态比对 + next_queue。 |
| `governance/CODE_INDEX.json` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | code_index.py | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 能力编码 ↔ 文档 / 测试 / 实现代码 / 决策 / 历史事件 / git 提交的全链路索引。　保护：四段式编码一致性。　注：编码是跨 artifact 的唯一身份证，不要另起一套编号。 |
| `docs/generated/` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | rebuild_docs.py / compare_graphs.py | `write-if-absent` | 禁 | 建议提交 git | 机器渲染的规范化文档目录，与人工 docs/ 物理隔离，避免误改生成物。　保护：可逐字节复现 / 无绝对路径。　注：需要长期人工补充时请换文件名，不要手改这里的生成物。 |
| `docs/generated/PROJECT_BRIEF.md` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | rebuild_docs.py | `write-if-absent` | 禁 | 建议提交 git | 规范化项目简报：目标、范围、现状、状态词、边界。　保护：默认不覆盖。 |
| `docs/generated/MODULE_MAP.md` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | rebuild_docs.py | `write-if-absent` | 禁 | 建议提交 git | 模块地图：模块 → 目录 → 能力编码，回答「东西在哪」。　保护：默认不覆盖。 |
| `docs/generated/CAPABILITY_INDEX.md` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | rebuild_docs.py | `write-if-absent` | 禁 | 建议提交 git | 能力索引：编码 → 文档 / 测试 / 代码 / 决策 / 等级。　保护：默认不覆盖。 |
| `docs/generated/GRAPH_DIFF.md` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | compare_graphs.py | `write-if-absent` | 禁 | 建议提交 git | 规划图与实际图差异的人类可读报告与开发顺序。　保护：默认不覆盖。 |
| `governance/registry.draft.json` | 草稿层 | 引入方案后新增 | 仅存量接入路径出现 | discover_project.py / 人 | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 存量项目盘点草稿，schema registry-draft/1。人工确认后才被 adopt 消费。　保护：只读发现 / 默认不覆盖 / 需人工精简。　注：草稿不是事实源；重复跑 discover 不会覆盖它。 |
| `governance/ADOPTION_REPORT.md` | 草稿层 | 引入方案后新增 | 仅存量接入路径出现 | discover_project.py | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 人类可读的接入盘点报告：候选模块、能力点、置信度、风险与下一步。　保护：只读发现 / 截断与无测试告警。 |
| `governance/build_capability_model.py` | 工具层 | 引入方案后新增 | 治理骨架必需 | init_project.py（复制模板） | `bootstrap` | 禁 | 建议提交 git | 生成器副本：从 registry + 证据重算账本与看板。　保护：check.sh 模板/示例逐字节同步 / --no-generator 可跳过。　注：不要在目标项目里改这份副本；升级方法论后同步 templates/ 版本。 |
| `governance/verify_ledger.py` | 工具层 | 引入方案后新增 | 治理骨架必需 | init_project.py（复制模板） | `bootstrap` | 禁 | 建议提交 git | 校验器副本：回答「账本内部坏没坏」。　保护：31 条不变量 / 模板同步。　注：与 scenario_guard.py 分工：后者回答「现在能不能动它」，未复制进目标项目。 |
| `governance/registry_codec.py` | 工具层 | 引入方案后新增 | 治理骨架必需 | init_project.py（复制模板） | `bootstrap` | 禁 | 建议提交 git | registry schema/2 唯一编码与容器归一化契约，供生成器和校验器共同消费。　保护：唯一 code_namespace / cap_code / normalize_projects / iter_caps。　注：禁止在目标项目里改写；code 规则只在本方法的权威模板维护。 |
| `governance/run_tests.py` | 工具层 | 引入方案后新增 | 治理骨架必需 | init_project.py（复制 scripts/） | `bootstrap` | 禁 | 建议提交 git | 测试报告生成器副本，产出 governance/test_report.json。　保护：报告含源码绑定摘要。　注：工具副本之一：让项目脱离本仓库也能独立复算证据（v2.1.2 起共 5 个，v2.3.0 增至 6 个）。 |
| `governance/binding_advisory.py` | 工具层 | 引入方案后新增 | 治理骨架必需 | init_project.py（复制模板） | `bootstrap` | 禁 | 建议提交 git | 证据绑定 advisory 副本：查「声明的测试」与「声明的实现」之间有无调用关系。　保护：符号级绑定 advisory / 模板同步。　注：shadow 门禁：只晒 [UNBOUND] 不否决；由生成器在重算时调用，独立成模块是让生成器主体保持在模块大小硬限之下。 |
| `governance/derived_issues.py` | 工具层 | 引入方案后新增 | 治理骨架必需 | init_project.py（复制模板） | `bootstrap` | 禁 | 建议提交 git | 把非 bound 能力投影成可认领 issue（issue_set = h(binding_status)）。　保护：派生 issue / 生成器调用。　注：v2.3.0 起共 6 个工具副本；issue 是账本视图而非手工第二事实源，独立成模块让生成器主体保持在模块大小硬限之下。 |
| `.workbuddy/` | 资产层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | asset_bundle.py | `write-if-absent` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 平台项目级 Agent 资产目录；升级 M7 后才有内容，权威源仍是方法论仓库。　保护：asset_bundle.py verify 逐文件 sha256 / manifest 整包摘要。　注：这里只放由治理升级安装的副本；用户自己放的技能不属于治理清单，不会被删除。 |
| `.workbuddy/skills/` | 资产层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | asset_bundle.py | `rewrite` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 可被 Agent 平台直接加载的技能副本，每个技能一个 <name>/SKILL.md。　保护：frontmatter name 与目录名一致 / 逐字节副本校验。　注：禁止在项目内编辑；改技能要改方法论仓库并发版，再由 M7 重新安装。 |
| `.workbuddy/experts/` | 资产层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | asset_bundle.py | `rewrite` | 禁 | 可提交（便于离线审计）或 CI 重跑 | 专家包副本，每个专家一个 <name>/EXPERT.md；路由优先消费这份已安装资产。　保护：frontmatter name 与目录名一致 / 逐字节副本校验。　注：路由卡若引用的专家缺文件，--check-assets 会 fail-closed 报 incomplete。 |
| `governance/ASSET_MANIFEST.json` | 派生层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | asset_bundle.py | `rewrite` | 禁 | 建议提交 git | 已安装资产的只读清单；证明副本与权威源逐字节一致、没有多余旧版本。　保护：逐文件 sha256 + 整包 digest + 账本 installed_assets 绑定。　注：不是第二事实源：它只记录 sha256，不含规则正文；权威源是方法论仓库 tag。 |
| `.ledger-upgrade/` | 运行时层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | upgrade.py | `write-if-absent` | 禁 | 不建议提交（本地临时产物） | 升级备份根目录；跑过 upgrade.py apply 后才出现。　保护：manifest 只存相对路径 / 路径不含 ..。　注：备份是时间戳快照，不是活跃状态；放在项目根而不在 governance/，避免分裂事实源。 |
| `.ledger-upgrade/backups/` | 运行时层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | upgrade.py | `write-if-absent` | 禁 | 不建议提交（本地临时产物） | 每次升级一个目录：<UTC>-<账本摘要前 8 位>/manifest.json + 被改文件的副本。　保护：rollback 需 --approved-by。　注：manifest.json 列相对路径与 sha256；rollback 按清单逐文件恢复并记录到 upgrade_log。 |
| `.ledger-write.lock` | 运行时层 | 引入方案后新增 | 跑对应命令后才出现（不出现属正常） | agent_gateway.py | `write-if-absent` | 禁 | 不建议提交（本地临时产物） | 多 Agent 写入网关的 OS 级互斥锁文件，保证读-判-写原子。　保护：fcntl.flock 锁内重读账本并重新判定。　注：瞬态协调文件，不是事实源；无 fcntl 的平台降级为告警（见 E6 边界）。 |

## 账本内字段（不是 governance/ 下的独立文件）

| 字段 | 写入者 | 方式 | 含义 |
|---|---|---|---|
| `capability_model` | build_capability_model.py | rewrite | 能力等级、完成度、组件树、文档索引、next_queue 的派生结果；禁止手改。 |
| `history.events` | build_capability_model.py | append-only | 状态指纹链；末事件指纹必须等于当前能力模型指纹。 |
| `entries` | ledger_decide.py / ledger_lesson.py | manual | 决策 D-NNN；人裁决，AI 只能新增 proposed。 |
| `lessons.items / lessons.candidates` | ledger_lesson.py / 生成器 | manual / 派生 | 已确认经验与自动识别的候选，任务卡只引用 confirmed。 |
| `lifecycle / lifecycle.log` | lifecycle.py | state-field / append-only | 冻结、归档、批准人、状态变更日志。**不是 governance/lifecycle.log 文件**。 |
| `retired_caps / execution.claims` | lifecycle.py | state-field | 退役编码登记与任务领用锁，保证编码不复用、同码不被两个执行者同时领用。 |
| `provenance` | init_project.py | bootstrap | 接入来源（template / 草稿相对路径）、模式与意图，外部绝对路径自动脱敏。 |
| `governance_meta / upgrade_log` | upgrade.py | state-field / append-only | 版本七轴、已应用迁移、工具 sha256 与升级/回滚日志。**不是 UPGRADE_LOG.md 文件**。 |
| `governance_meta.method_assets / board_skeleton / installed_assets` | upgrade.py | state-field | 整包资产摘要、看板骨架摘要，以及项目级已安装副本的逐文件绑定；三者任一漂移都要重新批准升级。 |
| `work_items` | work_panel.py | state-field | 节点级 TODO / issue 的唯一写入点；scope 可指向项目、模块或四段式能力编码。 |
| `test_results` | work_panel.py sync-tests | state-field | 测试报告的可验证投影（source_sha256 绑定原报告）；供工作台显示模块/组件级逐用例结果。 |
| `access / access.audit` | agent_gateway.py | state-field / append-only | Agent 名册、编码租约、revision 与写入审计。**不是 AGENTS.yaml 或独立审计日志**。 |

## 不会进入被治理项目的内容

| 方法论仓库路径 | 原因 |
|---|---|
| `experts/、skills/（权威源）` | 方法论仓库里的专家与技能**原文**不进项目源码；v1.2.0 起由 asset_bundle.py 把逐字节只读副本装到 .workbuddy/，整包摘要写进 governance_meta.method_assets、副本清单写进 installed_assets。 |
| `scripts/、templates/、tests/` | 方法论自身的工具、模板与测试；只有 3 个脚本副本落到 governance/。 |
| `docs/NN-方法论文档、docs/STANDARD.md` | 方法论文档，属于本仓库而非被治理项目。 |
| `docs/generated/SCENARIO_MATRIX.md、FILE_LAYOUT.md、TEST_MODULES.md` | 本仓库的机器渲染矩阵；目标项目只会得到 docs/generated/ 下那 4 份项目级文档。 |
| `examples/、.github/workflows/、CHANGELOG.md、RELEASE_CHECKLIST.md` | 示例、CI 与发布资产，属于方法论仓库。 |
| `全仓 .git/` | git 元数据；trace_git.py 只读取证，不写入、不重写历史。 |

## 复算方式

```bash
python3 scripts/file_layout.py --check
python3 scripts/file_layout.py --diff --target /path/to/project --strict
```

`--check` 会逐条核对产出脚本源码中是否仍写着该文件名，
清单与代码漂移时直接失败；`--diff` 全程只读。
