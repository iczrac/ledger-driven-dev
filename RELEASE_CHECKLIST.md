# 发布前自检清单

发布到 GitHub 前逐项勾选。已在本地验证通过的标注 ✓。

## 功能完整性

- [x] 生成器可从 registry 读取项目定义，路径参数化（--root/--registry/--ledger/--board）
- [x] 完成度由证据逐级判定 L0-L5，禁止手填，可回落
- [x] 嵌套组件树从真实目录生成，深度/规模可控
- [x] 文档索引分 8 类 + 关联决策，路径存在性校验
- [x] 看板 11 个标签视图（含工作台 / 工作项 / 术语与实现）可渲染，节点工作条显示 TODO / issue / 测试；内嵌数据由生成器同步；CSS/DOM/JS 骨架与模板一致，按 PAGE_SIZE 分批
- [x] 循环协议写入 capability_model
- [x] 可信性校验器：31 条不变量（含证据分层），支持 --json / --strict
- [x] 证据分层：declared/verified，run_tests.py 产出实测报告，生成器 --test-report 判定升级
- [x] 看板显示 tier 徽章与 verified 覆盖率；任务卡携带 tier 与 needs_runtime_verification
- [x] SELECT 任务队列：生成器产出 next_queue，dry-run 可见，任务卡携带已确认经验
- [x] 历史层：状态指纹驱动 append-only 事件，重跑幂等，支持状态快照回放
- [x] 经验层：自动识别候选 + 人工确认 + 任务卡消费，看板两视图可见可点
- [x] 一键初始化脚本可用（含校验器），支持 greenfield / adopt 双模式与 provenance 记录
- [x] 八种专家角色（路由 / 新建 / 考古 / 账本治理 / 审计 / 执行 / 生命周期 / 平台治理），各含权限矩阵与停止条件
- [x] 二十二个技能（intent-restate/expert-run/route/discover/bootstrap/scan/verify/decide/lesson/guard/doc-rebuild/graph-compare/scenario-guard/layout-inspect/ledger-upgrade/agent-gate/method-assets/board-layout/scale-budget/asset-install/test-map/work-panel），标准 SKILL.md frontmatter
- [x] 复述门：结构化意图声明 + 8 道机器校验（防幻觉能力码/只读越权/意图竞争/元指令披露），可复算、只读、三态退出码；接入 route_expert 前置，不传 --intent-file 时向后兼容
- [x] 专家团自动编排：expert_run 沿交接链展开逐跳契约 + 命令分类（readonly/approval/manual）+ 人工批准包；零新判定权、默认 dry-run 零执行、fail-closed、可复算；批准点仍由人 --approved-by
- [x] 来源投影：provenance_view 把既有 issue/decision 字段按 [AI推断]/[人确认] 分组、从任务卡派生 definition_of_done；只读投影不写账本、不改 27 不变量；黄金范例 examples/golden-walkthrough 六步全链路可运行可复算零写盘
- [x] 技能脚本：重复立项、缺行动经验、无理由驳回均由代码拒绝
- [x] 377 个 unittest 用例（含 v1.3.0 的 7 个三态/幂等/适配器回归、v1.4.0 的 9 个反向回流专项、v1.5.0 的 12 个本体投影专项、v1.6.0 的 16 个验收契约专项 + 4 个 append-only 回归、v2.4 的 11 个复述门、v2.5 的 16 个编排器、v2.6 的 10 个来源投影、v2.7 的 6 个自举守门），零第三方依赖，临时目录隔离
- [x] 自举闭环：方法仓账本走过 M1-M8 补齐 governance_meta 五轴、补录 v2.4/2.5/2.6 三条发版决策、三个新元工具登记为能力点（7→10），账本=f(registry,仓库,报告) 可复算；守门测试 test_dogfood 先红后绿
- [x] 看板术语接本体：第二数据段 ONTO_TERMS 由 board_contract 从 ONTOLOGY.json 注入 11 条 ubiquitous_language，骨架摘要归一化该段；术语视图新增「本体投影词表」区与人读概念解说并列；方法与示例看板骨架统一（digest ba37cd40）
- [x] CI（Python 3.10-3.13 矩阵）/ CD（tag 触发，先门禁后打包）
- [x] 示例项目已跑通，产出真实账本与看板

## 验证记录（2026-11-17 / 18）

- [x] 示例：verify_ledger 24/24 通过，--strict 退出码 0
- [x] 证据分层：无报告全 declared；带通过报告 3 个 verified（覆盖 75%）；失败报告不升级
- [x] 负向测试：verified 无依据/非法取值/越级 → 3 类 FAIL 均被校验器抓到
- [x] 负向测试：注入重复编码/手改完成度/失效路径 → 3 FAIL；篡改历史指纹/清空经验行动 → 2 FAIL
- [x] 幂等测试：连续重跑三次，事件数/指纹/候选 id/任务卡完全一致
- [x] 示例：3 条历史（genesis + 等级跃迁 + 决策演进），2 个经验候选，1 条已确认经验
- [x] 示例：next_queue 产出 1 条任务并携带已确认经验 L-001
- [x] 示例：4 能力点编码唯一；分布 L5×3 / L2×1；完成度 0.80
- [x] 示例：3 条决策，含 superseded → done 取代链，双向校验通过
- [x] 示例：文档索引 0 缺失；3 模块全部有嵌套组件树
- [x] 示例：看板 EMBED 与账本完全一致；骨架 sha256 与模板一致；JS 通过 node --check
- [x] 初始化脚本在临时目录跑通，6 个文件正确生成（含 3 个工具副本）
- [x] 生成器 dry-run 与正式模式均正常
- [x] `bash scripts/check.sh` 全绿：223 测试（双发现口径）/ 测试架构 / 24 条三态不变量 / 60 场景 / 31 条目 + 12 字段布局 / 升级与接入端到端 / 资产与工作台契约 / 幂等 / 同步 / 反向回流 / 脱敏 / 文档链接
- [x] 看板 JS 通过 `node --check`；CI 用同一份门禁脚本，口径一致
- [x] 负向纪律测试：重复立项、缺 action、无理由驳回均被拒绝

## 多专家接入（0.6.0）

- [x] 路由脚本只读、确定性，账本损坏/意图冲突时 fail-closed
- [x] 存量项目盘点只写草稿与报告，不覆盖既有治理文件与源码
- [x] 新建/接入均写入 provenance，外部路径不泄露绝对路径
- [x] 接入模式生成后可通过 31 条不变量校验
- [x] docs/12-专家路由.md 与 README / AI 集成 / 落地指南互相引用一致

## 可追溯性五项反问（0.7.0）

- [x] registry + 账本可重建规范化文档三件套，默认不覆盖人工内容
- [x] 文档可抽目标/模块/编码/依赖，置信度不足时明确警告
- [x] git 真实路径可回连模块、能力编码、账本决策与历史事件
- [x] 规划图 vs 实际图五态比对，附带开发顺序、专家与前置条件
- [x] 四段式编码索引贯通文档 / 测试 / 代码 / 决策 / 事件 / 提交

## 场景矩阵与生命周期（0.8.0）

- [x] 当时 44 个场景定义自检通过（v1.2.0 已扩为 60），covered 均有探针、gap 均写明代价
- [x] 覆盖矩阵为生成物，check.sh 校验与定义无漂移
- [x] 证据绑定源码摘要：改动测试源码后 verified 自动回落 declared
- [x] 并发 CAS：指纹漂移时生成器退出码 2 且不写盘
- [x] 冻结态阻止生成器、归档态阻止全部写动作、解冻需人工批准
- [x] 能力退役与任务领用状态不污染 history.events，看板 EMBED 保持同步
- [x] 生命周期状态只写账本内字段，无第二事实源

## 文件架构清单（0.9.0）

- [x] `file_layout.py` 自检通过：31 条目 / 12 账本内字段，产出脚本源码字面量交叉验证
- [x] 引入前后目录树、greenfield / adopt 差异、七层所有权（含资产层）与 git 策略写入 docs/15
- [x] 渲染生成物 `docs/generated/FILE_LAYOUT.md` 与定义同步，check.sh 校验无漂移
- [x] `--diff` 只读：跑前后项目文件树哈希一致；三态与越界报告均有负向测试
- [x] 第 3 个工具副本补齐并纳入逐字节同步门禁
- [x] `lifecycle.log` / `capability_model` / `governance_meta` 明确为账本内字段，不产生同名文件

## 升级与多 Agent 接入（1.0.0）

- [x] `upgrade.py` 定义自检：3 个工具来源、8 条迁移、1 步 pre_upgrade / 19 步 post_upgrade 均存在
- [x] `plan` 只读且确定性；不兼容版本 / 冻结归档 / 未来版本 / 账本损坏均 fail-closed
- [x] `apply` 缺 `--approved-by` 被拒绝；有备份清单、相对路径、sha256；重复 apply 为 noop
- [x] 升级只加字段（M6 归一派生层文件）：`current_fingerprint` 与 `history.events` 不变；24 条不变量仍全绿
- [x] `verify` 11 项；测试源码改动后 `evidence_rebaseline` warn 且 `upgrade_complete=false`
- [x] `rollback` 逐文件恢复并写回执；缺批准 / 非法备份 id 被拒绝
- [x] `agent_gateway.py` 定义自检：8 角色 / 18 动作 / 10 个网关写入动作，写入型动作全在白名单
- [x] 默认拒绝：无 `access` 登记、未注册、越权、越 scope、无 CAS、registry 漂移、自我批准均 deny
- [x] 网关写入后 `access.audit` append-only、`revision` 递增、看板同步、24 条不变量全绿
- [x] `check.sh` 端到端阶段在临时副本跑 plan→apply→verify→register→dry-run→apply→拒绝→verify

## 资产 / 版面 / 规模契约（1.1.0）

- [x] `method_assets.py --check` 通过：6 组资产齐备、连续两次摘要一致、路径全相对
- [x] 资产漂移负向证明：手改账本摘要 → `verify.method_assets` warn、`plan` 重新列出 M5
- [x] `board_contract.py` 骨架摘要对 EMBED 数据不敏感、对 CSS 敏感；缺结构锚点会报出
- [x] `normalize` 默认 dry-run、缺批准被拒绝；归一后骨架一致且 EMBED 仍与账本等价
- [x] 版面漂移进入 `plan` 的 M6 且 risk=medium；`apply` 后 `plan` 为 noop、11 项 verify 全 pass
- [x] 模板 `PAGE_SIZE=200` 由 `scale_budget.py` 解析；超阈值项目报 warn/exceed，`--check --strict` 退出 2
- [x] `scale_probe.py` 三档基准可复现：50/400/1000 能力 → 0.135s / 0.723s / 4.406s，治理文件数固定
- [x] 示例看板按新模板归一；`check.sh` 的同步阶段增加骨架一致性检查
- [x] 场景矩阵 54 / 8 轴、覆盖率 82.4%；U3 / F8 / S1 covered、S2 partial、E7 唯一 gap

## 资产可用 / 测试架构 / 节点工作台（1.2.0）

- [x] `asset_bundle.py --check` 通过：可安装资产 28 份（8 专家 + 20 技能）、摘要确定性、路径全相对
- [x] `install` 默认 dry-run、缺 `--approved-by` 被拒绝、重复安装幂等；旧副本被人改过时保留并列 `stale_protected`
- [x] 负向证明：项目内手改 `SKILL.md` / 删副本 / 手改账本 `installed_assets` 摘要 → `verify` 报 drift
- [x] `route_expert.py --check-assets` 通过；路由优先读项目内已安装副本，缺文件报 `incomplete`
- [x] M7 纳入 `upgrade.py` 的 plan / 备份 / apply / verify / rollback；回滚只移除升级前不存在的副本
- [x] `tests/MODULES.json`：6 个开发模块 / 23 个测试文件；`MODULE_ID` 自证、`rglob` 与 `unittest discover` 双口径一致
- [x] `test_modules.py --check` 与 `docs/generated/TEST_MODULES.md` 渲染同步；`--target examples/demo-shop` 输出模块单测缺口
- [x] `work_items` / `test_results` 两个账本内字段；`work_panel.py` 写动作全部需人批准；`sync-tests` 绑定报告字节
- [x] 31 条不变量中的 `work_items_valid` / `work_item_refs_valid` / `test_results_binding_valid` 均有负向证明
- [x] 看板 10 个 tab：工作台 / 工作项视图与节点工作条；Node DOM stub 证明空账本不崩；骨架归一到 `735bcd09…`
- [x] `work_panel.py nodes` 与看板 JS 按同一规则复算派生聚合，不落盘、无第三份事实源
- [x] 规模预算新增 `work_items`（10 项阈值）；场景矩阵 60 / 10 轴、覆盖率 84.2%（47 / 7 / 5 / 1）
- [x] 版本七轴、8 条迁移、1 步 `pre_upgrade` / 19 步 `post_upgrade`、12 项 `verify`、九项 `upgrade_complete` 判据均由定义自检与测试复算
- [x] 新增 docs/19 / 20 / 21 与技能 `asset-install` / `test-map` / `work-panel`；全仓数量口径同步到 1.2.0

## 资产检查作用域补丁（1.2.1）

- [x] `installed_manifest_paths()` 从 `ASSET_MANIFEST.json` 读 28 条清单路径；项目自有技能不参与摘要与 frontmatter 检查
- [x] 负向证明：自有技能缺 description 仍 `ok`；清单内副本被删仍 `incomplete`
- [x] 真实存量项目接入验证：目标项目 `--check-assets` 从 `skill_count=37 / ok=false` 变为 `28 / ok=true`，且摘要与权威源一致
- [x] 资产 frontmatter 统一 1.2.1；`METHOD_VERSION` 同步；已升级项目经 M5 + M7 重绑摘要

## 脱敏

- [x] 看板模板 EMBED 已替换为空账本骨架
- [x] 全项目搜索无来源项目的内部代号、数据源名与专有名词残留
- [x] 示例为虚构电商项目，无真实业务数据
- [x] 示例决策、文档、代码均为演示内容

## 文档

- [x] README（价值主张、快速开始、目录结构、视图说明）
- [x] 二十四篇编号方法论文档 + STANDARD.md + CONTRIBUTING.md
- [x] LICENSE（MIT）
- [x] CHANGELOG
- [x] registry.example.json 含字段说明注释
- [x] 生成器 docstring 含用法说明

## 发布动作（v1.2.1 待执行）

- [x] 确认仓库名（`ledger-driven-dev`）
- [x] `git init` / 添加 remote
- [x] 检查 `.gitignore`（排除 `__pycache__/`、`*.pyc`、`.venv/`）
- [x] 提交并打 tag `v1.2.1`
- [x] GitHub 仓库描述、topics 标签（README 顶图仍可选）

## 建议的 topics

`developer-tools` `knowledge-management` `ai-agent` `documentation` `methodology` `single-source-of-truth` `python`

## v1.3.0 发布检查（反向回流第一批）

- [x] R1：校验器三态输出；无投影记 `na`；`--require-active` 可判失败
- [x] R2：无报告项目第二次 `plan` 收敛 `noop=True`；`verify.summary.na` 可观测
- [x] R3：`POST_UPGRADE[0]` 在目标项目侧生成报告；`import-report` 三种适配器 + 干跑纪律
- [x] 7 个新回归（na 不计 pass / require-active / 幂等收敛 / 三适配器 / 干跑批准 / 空报告不绿）
- [x] 工具副本同步：`templates/verify_ledger.py` → `examples/demo-shop/governance/`
- [x] 资产 frontmatter 统一 1.3.0；`METHOD_VERSION` 同步
- [x] `bash scripts/check.sh` 全绿
- [x] 已引入项目重新批准升级（`M4 + M5`）重绑摘要：已由 S4（`M5 + M7`）与 v1.6.0 发版（`M4 + M5 + M7`）完成，见 `feedback/S4-REBIND-1.5.0.md` / `feedback/RELEASE-1.6.0.md`

## v1.4.0 发布检查（反向回流闭环 / L0）

> 从本版起，**每个 tag 必须写明 `feedback_closed`**，否则不算完整发布。

- [x] **本版 `feedback_closed = 3`**：`feedback/observations.jsonl` 共 12 条来自真实存量项目的匿名观察，3 条收敛到真实产物，9 条保持 `open` 作为后续版本处方
- [x] `ledger_feedback.py export` 只读目标项目、重复导出幂等、脱敏数据驱动；写观察包需 `--apply --approved-by`
- [x] `triage` 四产物协议；`check` 校验内容指纹、**产物引用必须指向真实文件**、关闭理由非空
- [x] 升级流程变为「升级前 1 步基线 + 升级后 19 步」；`plan()` 输出 `pre_upgrade`；定义自检校验首末步
- [x] `check.sh` 新增「反向回流」阶段：闭环校验 / `feedback_closed ≥ 1` / 导出幂等
- [x] 9 个新回归（含「先失败后通过」的闭环证明），测试架构清单纳管 22 个文件
- [x] `docs/22-反向回流.md`；28 份资产 frontmatter 与 `METHOD_VERSION` 统一 1.4.0
- [x] `bash scripts/check.sh` 全绿：211 测试 / 24 条三态不变量 / 12 个阶段（含反向回流）
- [x] 已引入项目升级到 1.4.0：未单独执行 1.4.0，由 U（`1.2.1 → 1.5.0`，备份 `20261118T072013Z-ad0f73f7`）跨版本覆盖；证据见 `feedback/UPGRADE-DIFF-1.5.0.md`

## v1.5.0 发布检查（本体投影 / 派生只读元契约）

> 本体必须先于 `registry/2`：先定义什么合法，再改数据长什么样。

- [x] **本版 `feedback_closed = 4`**：观察包 13 条，新增 1 条 `ontology` 轴观察（基数违例），triage 成 `tests/meta/test_ontology.py` 负向回归
- [x] `scripts/ontology.py`：`build`（AST 抽取 18 个分型取值域 / 6 个 BC / 7 条关系 / 31 条公理，来源带 sha256）、`check`（同步 / 幂等 / 三类漂移 / 第七轴）、`diff`（复用 `make_obs` 输出 `affected_axis=ontology` 观察）、`emit-md`、`digest`
- [x] 派生只读文件 `docs/generated/ONTOLOGY.json` + `ONTOLOGY.md`；`docs/STANDARD.md` 第四章改为分型词表，禁止裸 `status`
- [x] 第七轴 `governance_meta.ontology_digest` 由 `upgrade.py apply` 在 M5 分支写入；`verify` 新增 `ontology_binding`（pass / na / warn）；**8 条迁移与 19 步 post_upgrade 不变**
- [x] `check.sh` 新增「本体层」阶段（共 13 阶段）并在「升级与接入」阶段校验升级后绑定；注入非法状态词 / 伪造单项目 registry 必须被抓
- [x] 12 个新回归（含「先失败后通过」与写盘无批准人被拒），测试架构清单纳管 23 个文件
- [x] `docs/23-本体投影.md`；28 份资产 frontmatter 与 `METHOD_VERSION` 统一 1.5.0
- [x] `bash scripts/check.sh` 全绿：223 测试 / 24 条三态不变量 / 13 个阶段（含本体层）
- [x] 已引入项目升级到 1.5.0：由 U 完成（`1.2.1 → 1.5.0`），`verify 11 pass / 1 na / 0 warn`、10/10 看板视图；基线 → 升级 → 复导 → diff → triage 全链证据见 `feedback/UPGRADE-DIFF-1.5.0.md`

## v1.6.0 发布检查（验收契约 / 写入语义 / 版本统一）

> 顺序不可交换：S1 固化证据 → S2 先写红灯 → S3 转绿 → S4 重绑 → 发版。

- [x] **S1**：本地固化升级前后观察证据（`feedback/UPGRADE-DIFF-1.5.0.md`），三包 sha 与闭环计数留档；未 push / 未打 tag
- [x] **S2**：`scripts/acceptance.py` + 16 个绿灯自测 + 第 14 个门禁阶段；刻意红灯 `13 PASS / 1 FAIL`，27 处漂移 / 15 文件、append-only 违例（13→10 行）如实记录
- [x] **S3**：三层验收转绿 —— `drift=0`（85 文件）/ 3 份派生可复算 / 观察包 13→23 行且 4 条已收敛证据逐字段不变；10 处历史复核留痕；`check.sh` 14/14 全绿、243 测试、24/24 三态不变量
- [x] `ledger_feedback.py` 的 `export` 改为 append-only 合并；`triage` 语义不变；`docs/22` 补写入契约
- [x] `stage_scenarios` 改用「临时重算 + cmp」，门禁不再把合法重算判成手改派生文件
- [x] `test_acceptance.py` 的版本断言改为从 `upgrade.py` 动态读取，发版不再需要手改测试
- [x] `METHOD_VERSION` 与 28 份资产 frontmatter 统一 1.6.0；`docs/16` 当前示例值同步；历史性「v1.5.0 起」保留
- [x] `ontology.py check` 通过：升版本不改 `ontology_digest`（版本脚本不在 `SOURCE_FILES`），仍为 `e258dec1…`
- [x] **S4**：已引入项目人批准重绑 `M5 + M7`（备份 `20261118T100016Z-ccd42d92`），复验 `pass=11 / na=1 / warn=0`、`upgrade_complete=true`；业务数据六段 digest 与三包观察 sha 不变
- [x] 本次发版重绑 `M4 + M5 + M7`：`method_assets` `9493bc9e… → 264026fd…`；备份 `20261118T102418Z-5cd2106a`，复验与回滚命令见 `feedback/RELEASE-1.6.0.md`
- [x] **本版 `feedback_closed = 4`**（发布时点：`feedback/observations.jsonl` 13 条，4 条收敛为四产物、9 条 `open`）；2026-11-18 规划收口再 triage 3 条后为 **5**，见文末「路线图对账」
- [x] `CHANGELOG` / 本清单 / `README` 口径一致；`bash scripts/check.sh` 14 阶段全绿
- [x] 条件化第 1/2/15 步 SOP（目标项目无 `tests/` 时的降级路径）→ **v1.7.0 已交付**，由 `acceptance.py` 的 G2 机器判据校验，证据见 `feedback/S2-1.7.0-RED.md` / `feedback/RELEASE-1.7.0.md`
- [x] M8 `activation` 占位与 `all_active` 语义 → **v1.7.0 已交付**，G3 机器判据 + `P` 侧 24 条三态不变量复验
- [x] `registry/2` 多项目数据契约：由 **v2.0.0** 交付（`code_namespace` 4 段码 + 双写兼容），
      经用户「a」显式授权 + 备份 + 人批准 S4 重绑完成；见证 `feedback/RELEASE-2.0.0.md`

### 设计内告警（不掩盖、不在本版修）

- E7 `cardinality_contradiction`：单项目 registry vs 4 项目能力模型，`ontology.py check --target` 仍 `ok=false`，但第七轴 `binding=pass`。
- `evidence_rebaseline=na` / `all_active=false`：目标项目无测试报告，47 个能力仍
  `declared`；v1.7.0 起由 `governance_meta.activation.state=unbound` 明示未激活。
- `scale_budget` 的 `project_files=49078` 超阈值告警。

## 路线图对账（v1.6.0 后，2026-11-18）

> 本节是**规划对账**，不是第二份状态清单。观察状态权威源仍是
> `feedback/observations.jsonl`，发布状态权威源仍是 `DECISION_LEDGER.json`。
> 完整取证见 `feedback/ROADMAP-AUDIT-1.6.0.md`。

### 失配与顺延

`docs/23-本体投影.md` 第七节与 ODLA 提案第 7 节把 **v1.6.0** 定义为
「Semantic Graph：Statement 再化 + K3 推理机 + 最小割集根因分析」；
而实际发布的 v1.6.0 是「验收契约 + append-only 写入语义 + 版本统一」
（S1–S4 反向优化序列占用了该版本）。**语义图未实现**，规划陈述必须顺延：

| 原定版本 | 内容 | 调整后 |
|---|---|---|
| v1.6.0 | Semantic Graph | 已由 S1–S4 占用；语义图顺延 **v1.7.0** |
| v1.7.0 | Risk & Evidence（polarity / confidence / contradicting evidence） | 顺延 **v1.8.0** |
| v1.8.0 | Agent Autonomy Ladder | 顺延 **v1.9.0** |
| v2.0.0 | `registry/2`（破坏性） | **不变**，仍需人批准数据迁移 + 备份 + 双写兼容期 |

注：`docs/23` 正文仍保留旧规划表述。修正它会改变 `method_assets.digest`（整包
摘要含编号文档），因此必须与 v1.7.0 实现合并为**一次发版 + 一次主仓重绑**，
不单独为改一句话再发一版。这是整包摘要绑定的固有成本，不是缺陷。

### 观察包收敛（本轮）

`feedback/observations.jsonl` 13 条：人批准 triage 3 条
（版本落差 → `migration: scripts/upgrade.py`；两条历史迁移日志 → `wontfix`
append-only 事实），`open 9 → 6`、`feedback_closed 4 → 5`。既有 4 条已收敛
证据逐字段不变；`baseline.jsonl` / `post-v150.jsonl` 两包 sha 不变。

剩余 6 条 `open` 的处方：`test_results` 绑定与 `verified` 升级、
`registry/2`（v2.0.0）、`access` 名册激活（`agent_gateway.py register` 需人批准）、
`lifecycle` 登记（`lifecycle.py status`）、经验候选确认（`ledger_lesson.py --confirm`）、
`test_results` 投影未绑定。前两类需方法论仓迭代，后四类主要是目标项目侧动作。

### 启动成本（必须一次性合并）

任何权威源改动（`docs/23`、`upgrade.py`、`templates/*`、新增脚本）都会改变
`method_assets.digest`，需再次人批准 `M5 + M7` 重绑主仓并复验。因此 v1.7.0 应把
「语义图 + 条件化 SOP + M8 `activation` 占位 + `docs/23` 规划修正」合并为一次
迭代，按 S1 固化证据 → S2 先写红灯 → S3 转绿 → S4 重绑 → 发版推进。
`registry/2` 独立立项，需人批准数据迁移，不得由 Agent 自动执行。

### 依赖顺序修正（2026-11-18 第二轮决策，**取代上方启动建议**）

> 完整取证与判据见 `feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md`。
> 上方「v1.7.0 应把语义图 + … 合并」的顺序被本段修正：**语义图不再无条件纳入 v1.7.0**。

从「规则可复放 + 事实可验证 + 不可伪造」推出三条约束，全部指向
「本轮不发版、不写 `P`」：

- **C1 诚实 > 绿灯**：`P` 无 `tests/`、无 `test_report.json`、
  `activation=null`、`test_results=null`；`docs/11` 的两条不变量会抓伪造
  `verified`。`na` 与 47 个 `declared` 是正确状态，不得用方法论仓自身测试顶替。
- **C2 依赖顺序**：`ontology.py` A2 要求 L3+ 有新鲜 `verified` 证据、G3 要求
  含 Unknown 不得派生 `pass`。47 能力全 `declared` → K3 推理恒 Unknown →
  **语义图在零 `verified` 事实上是空集推理**，必须先有证据再做推理。
- **C3 版本经济**：实证 `docs/23`、`scripts/upgrade.py`、`templates/*`、
  frontmatter 均在 `ASSET_GROUPS`；改任一处即触发一次发版 +
  `P` 的 `M4 + M5 + M7` 全量重绑。刚发 v1.6.0 就为 3 个小修再发版 = 零散发版，禁止。

**语义图启动前置条件 P1–P3**（缺一则 v1.7.0 降级为「一致性与可适配性」收敛版，
语义图再次顺延）：P1 `P` 至少一条能力由其真实 CI 报告升为 `verified`；
P2 `ontology.py check --target P` 中 A2 可判定；P3 规划一致性已由机器门禁校验。

**本轮实际推进（零摘要成本）**：修订仓外 ODLA 提案第 7 节（消除一处
「v1.6.0 = Semantic Graph」错误陈述 + 补依赖顺序判据）、新增
`feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md`（S2 红灯定义书：6 条转绿判据
G1–G6、启动序列、固定成本）、更新本节。`feedback/*` 与根级 md 均为 `ZERO`
作用域，`method_assets 264026fd…` 与 `ontology_digest e258dec1…` 不变。

**已知且刻意保留的失配**：`docs/23` 第七节仍写着旧规划。修它属 `ASSET` 改动，
须与下一次功能实现攒成一次发版；G1 要求届时把它升级为 `acceptance.py` 的
机器断言（不是人眼复核），确保失配不会永久挂着。

**边界**：`METHOD_VERSION` 仍 1.6.0、`tag v1.6.0` 仍指 `a22f3eb`、未发版、
未写 `P`（97 个在途改动与账本 mtime 未变）、未把 6 条 `open` 伪装成收敛。
下一轮若实现 v1.7.0，须一并授权完整「S1→S4→发版 + `P` 重绑」。

**执行结果（2026-11-18，v1.7.0）**：用户授权落实 A，上述授权已给出；因
P1–P3 仍全部未满足，本版按 R4 / G6 降级为「一致性与可适配性」收敛版，
只交付 R1–R3，语义图再次顺延。上方「`docs/23` 第七节仍写着旧规划」的失配
已由 G1 机器断言修复；顺延表以 `CHANGELOG` 的 1.7.0 段落与下节为准。

## v1.7.0 发布检查（一致性与可适配性收敛版）

> 顺序不可交换：S1 固化证据 → S2 先写红灯 → S3 转绿 → S4 重绑 → 发版。
> P1–P3 未满足（取证见 `feedback/S1-1.7.0-BASELINE.md`），语义图顺延；
> 范围裁剪按 G6 记入 `feedback/RELEASE-1.7.0.md`。

- [x] **S1**：本地固化基线（三包 sha / 两项摘要 / 门禁基线 / `P` 边界），未 push / 未打 tag → `feedback/S1-1.7.0-BASELINE.md`
- [x] **S2**：G1–G3 落成 `acceptance.py` 第四层 + 第 15 门禁阶段，刻意红灯（13 绿 / 2 红）→ `feedback/S2-1.7.0-RED.md`
- [x] **S3**：R1 规划一致性 / R2 条件化 SOP / R3 M8 `activation` 占位；L4 三项转绿
- [x] **G1**：`docs/23` 第七节与 `CHANGELOG` 顺延锚点由机器断言校验，不是人眼复核
- [x] **G2**：空 `tests/` fixture 上三条命令 SKIP、不生成 `test_report.json`；`POST_UPGRADE` 仍 19 步
- [x] **G3**：无报告项目写入 `governance_meta.activation.state=unbound`；24 条三态不变量仍 `23 pass + 1 na`
- [x] **G4**：三包观察 sha 与 7 条 `closed` 证据不变；append-only 探针幂等
- [x] **G5**：`bash scripts/check.sh` 15/15 全绿、`acceptance/1 overall=pass`、drift 0、3 份派生可复算
- [x] **G6**：P1–P3 在 `feedback/RELEASE-1.7.0.md` 显式记录「未满足 / 范围裁剪为 R1–R3」
- [x] `METHOD_VERSION` 与 28 份 frontmatter 统一 1.7.0；`docs/16` 当前示例值同步
- [x] `ontology.py check` 通过；`ontology_digest` 不变（`SOURCE_FILES` 未改）
- [x] **S4**：人批准 `M4 + M5 + M7 + M8` 重绑 `P`（备份 `20261118T135753Z-ed92ea36`），复验 `pass=11 / na=1 / warn=0`、`upgrade_complete=true`、24 条 `23 pass + 1 na`；六段业务 digest 与三包观察 sha 不变，`activation.state=unbound` 已写入 → `feedback/RELEASE-1.7.0.md`
- [x] **发版**：附注 `tag v1.7.0` + push `origin/main`（本清单提交后立即执行），发版报告与回滚命令见 `feedback/RELEASE-1.7.0.md`

### 顺延表（v1.7.0 发布点，取代上方 v1.6.0 后对账节的启动建议）

| 版本 | 内容 | 状态 |
|---|---|---|
| v1.6.0 | 验收契约 / append-only / 版本统一 | 已发布（S1–S4 序列占用，语义图未实现） |
| v1.7.0 | 一致性与可适配性收敛版（R1–R3） | **本版发布** |
| v1.8.0 | 证据适配与不降级（L5 四缺口） | **本版发布（S3 转绿；S4 待发版）** |
| v1.9.0 | Risk & Evidence（polarity / confidence / contradicting evidence） | 顺延 |
| v2.0.0 | `registry/2` 多项目数据契约 / Agent Autonomy Ladder | 不变，需人批准数据迁移 |
| 待定 | Semantic Graph（Statement 再化 / K3 推理机 / 最小割集 RCA） | 再次顺延，须先满足 P1–P3 |

### 设计内告警（本版仍如实保留）

E7 `cardinality_contradiction`（`ontology.py check --target P` 仍 `ok=false`、
第七轴 `binding=pass`）、`evidence_rebaseline=na` / `all_active=false`、
`scale_budget` 项目文件阈值告警 —— 三者均未被收敛版掩盖。

## v1.8.0 发布检查（证据适配与不降级版）

- [x] **S1**：`feedback/S1-1.8.0-BASELINE.md` 固化四缺口、两仓映射、不降级配方与三方摘要
- [x] **S2**：`feedback/S2-1.8.0-RED.md` 记录 L5 四断言红灯（L1–L4 全 PASS、L5 四项 FAIL）
- [x] **S3**：L5 十项 checks 全 PASS、16 阶段门禁、264/264 单测
- [ ] **S4**：人批准 apply 重绑 `P`（`M3+M4+M5+M7` + 第七轴 ontology 摘要刷新）
- [ ] **发版**：附注 `tag v1.8.0` + push；发版报告见 `feedback/RELEASE-1.8.0.md`
- [x] **G1 规划一致性**：`docs/23` 第七节 / `CHANGELOG` / 本清单顺延表含 v1.7.0–v2.0.0 锚点
- [x] **不降级**：真实报告在新模板 `build()` 上 level 保持 `L5:20/L3:22/L2:5`、降级数 0、`verified=9`
- [x] **诚实纠正**：早期「降级 0」为 code 前缀失配的假阴性，剥离前缀后重新对齐并修正

### 本版边界（不掩盖）

- 主仓 `governance/registry.json` 与 `capability_model` **本版未写盘**；P1 最终满足需独立人批准数据迁移
- 语义图仍顺延（须 P1–P3 全满足）；`registry/2` 仍 v2.0.0
- E7 `cardinality_contradiction`、`evidence_rebaseline=na`、`scale_budget` 告警、6 条 `open` 观察均保留

## v2.0.0 发布检查（registry/2 多项目编码契约）

> 顺序不可交换：S1 固化证据 → S2 先写红灯 → S3 转绿 → S4 重绑 → 发版。
> 授权：用户「a」= 正式立项 v2.0.0 破坏性迁移。

- [x] **S1**：`feedback/S1-2.0.0-BASELINE.md` 固化三方摘要 / 观察包三 sha / P1 真实报告（182 passed）/ 5 段码写盘失败复现
- [x] **S2**：`feedback/S2-2.0.0-RED.md` 记录 L6 三项红灯（code_namespace / registry2_contract / no_prefix_leak）
- [x] **S3**：`feedback/S3-2.0.0-GREEN.md`；生成器 `code_namespace()` + build 两处 code 改经命名空间；L6 四项转绿、14 项验收全 PASS、273/273 单测
- [x] **双写兼容**：单项目模板 `DEMO.DATA.READY.01` 与 monorepo `APEX.DATA.READY.01` 均 4 段合法（专项测试覆盖）
- [x] **根因修复**：真实 P dry-run 产出 0 个 5 段码、0 个 `RACOS.` 泄漏、level 保持 `L5:20/L3:22/L2:5`、`no_regress=[]`
- [x] **S4**：人批准 apply 重绑 `P`（M3+M4+M5+M7 + P1 三步数据迁移），24 不变量无 fail、P1 verified 落盘
- [x] **发版**：附注 `tag v2.0.0` + push；发版报告见 `feedback/RELEASE-2.0.0.md`

### 本版边界（不掩盖）

- 语义图（Statement 再化 / K3 / 最小割集 RCA）仍顺延（P2/P3 尚未复验）
- E7 `cardinality_contradiction`、`scale_budget` 告警、6 条 `open` 观察按既有状态保留/复验

## v2.0.1 发布检查（registry schema/2 容器）

> 顺序不可交换：S1 基线 → S2 红灯 → S3 转绿 → S4 人批准重绑 → 发版 → 独立复放核实。
> 授权：用户在“下一步路径”中选择 registry schema v2。

- [x] **S1**：`feedback/S1-REGISTRY-SCHEMA-V2-BASELINE.md` 固化 v2.0.0 全绿基线、消费者地图、容器双读与第二套 codec 风险
- [x] **S2**：`feedback/S2-2.0.1-RED.md` 记录 L7 两项 fail、专项 7 项全未通过
- [x] **S3**：`feedback/S3-2.0.1-GREEN.md`；唯一 codec、双读、4 工具副本、18 项 acceptance、282/282 单测
- [x] **S4**：`feedback/S4-2.0.1-REBIND.md`；备份后迁移为 4 个 `projects[]`，47 code 逐项全等，M4/M5/M7 重绑，24 不变量全 pass
- [x] **语义契约**：registry 与 capability_model 同为 4 项目，本体 A4 真正一致（不再靠单项目掩盖）
- [x] **发版**：`tag v2.0.1` + push；发版报告见 `feedback/RELEASE-2.0.1.md`
- [x] **独立复放**：`feedback/DELIVERY-VERIFY-2.0.1.md`

### 本版边界（不掩盖）

- 语义图 R4 仍顺延；本版只做 registry 容器与 codec 契约；
- `scale_budget` 告警与 6 条 open 观察保留；
- 目标项目根仓库不整体提交，只留下治理文件与备份链。

## v2.1.0 发布检查（声明驱动证据）

> 由来：v2.0.3 让账本只描述仓库里有的东西；再追一层才发现账本描述的是它自己。
> 把 47 个能力的 evidence 抹空重算，20 个 L5 全部塌成 L2、verified 归零——
> 说明那份账本从仓库里重建不出来，只是记录，不是证明。

- [x] **切断回路**：删除 `evidence_hints()`；生成器证据只来自 `caps[].tests` / `test_records` / `hints`
- [x] **声明优先**：`resolve_declared()` 逐条校验「存在且已入库」，缺失即告警并按缺失处理
- [x] **项目内扫描**：测试/记录扫描限制在 `impl` 前缀推导出的项目子树，消除跨项目串味
- [x] **漂移门禁**：`--check` 重算与账本不一致即 exit 1，逐条打印差异
- [x] **负向证明**：`tests/core/test_declared_evidence.py` 5 条（账本不影响派生、缺失降级、不跨项目、差异可检出）
- [x] **可复算实测**：抹空全部 evidence 后重算，47 个能力逐字段差异 0，verified 仍 43
- [x] **纠错审计**：移除 5 条跨项目证据、3 条同形异义（security=证券池）、若干宽词噪声；补 24 个真实测试文件
- [x] **证据重建**：在干净 clone 里按声明跑 133 个测试文件（1290 用例进入报告，6 个文件不绿如实排除）
- [x] **方法仓门禁**：`scripts/check.sh` EXIT=0；acceptance 目标版本 2.1.0 全 PASS
- [x] **重绑**：目标项目 `upgrade verify` 12 pass / 0 warn，`method_assets.digest` 与目标账本一致
- [x] **发版**：`tag v2.1.0` + push；远端 `Governance invariants` 全绿且 `--check` 无漂移

### 本版边界（不掩盖）

- 声明只校验**存在与归属**，不校验语义相关性——「这个测试是否真在测这个能力」仍需人审；
- 6 个声明文件在干净检出里跑不绿（集成测试需外部服务、RSS/浏览器需网络与凭据），相关能力保持原状；
- 4 个能力本来没有测试（RSCOV.04 / ARES.DECIDE.02 / HELM×2）；
- `manual` 型关闭条件仍需人主动关闭；多副本同步税未处理。

## v2.1.1 发布检查（术语与实现视图）

> 由来：看板十个视图全部回答「账本里有什么」，没有一个回答「这套方法论怎么读」。
> 新手面对 D-NNN / verified / 漂移 / M1–M8 只能翻文档，而文档与页面分离、注定漂移。
> 解法不是再写一份入门文档，而是把解说放进页面本身——与实现同源，改实现必须改它。

- [x] **新视图**：第 11 个标签「术语与实现」，三个分区（专有词汇表 20 条 / 编码思路 6 条 / 关键实现解说 7 条）
- [x] **同源纪律**：解说的是当前实现而非愿景；内容为模板静态内容（方法论事实对所有项目一致），随 M6 归一化推送，禁止项目内手改
- [x] **契约跟进**：视图分批走 `PAGE_SIZE`、样式只复用既有类、搜索框支持过滤术语；`test_board_views` 新增 4 个锚点断言
- [x] **脱敏**：视图内容不含来源项目内部名词（示例编码用 `DEMO.CORE.ORDER.01`）
- [x] **文档同步**：版面契约「十个视图」改十一个；本体投影版本表补 v2.1.1 行
- [x] **方法仓门禁**：`scripts/check.sh` EXIT=0
- [x] **示例重排**：`examples/demo-shop` 看板经 `normalize` 从新模板重建，骨架摘要一致
- [x] **重绑**：目标项目干净检出 `upgrade apply` → `upgrade verify` 全过、24 不变量全绿、`--check` 无漂移
- [x] **发版**：`tag v2.1.1` + push；远端 `Governance invariants` 全绿

### 本版边界（不掩盖）

- 术语数量有意的克制（20 条）：页面是索引不是教材，完整论述仍在 docs/；
- 「符号级证据绑定」（测试必须 import 能力实现）已沙箱验证但**未经批准不在本版**，
  资产摘要双算法问题同此——两项都等独立批准后另发补丁；
- 多副本同步税依旧：模板一改，主仓与示例要各重绑一次。

## v2.0.3 发布检查（路径全集补丁）

> 由来：v2.0.2 把强制点搬上机器后，第一条真话就是「本机 24 绿、干净检出 2 红」。
> 根因是生成器把本机文件系统当仓库事实，账本里混进了 gitignore 的运行产物与未入库测试。

- [x] **实现**：`RepoScope`（git index 取路径全集）+ 五处扫描收窄 + `norm_existing_path` 收紧
- [x] **负向证明**：`tests/core/test_path_scope.py` 7 条（先造噪声，再断言不可见；含报告绑定未入库文件）
- [x] **删除许可**：主仓 `ci_governance_gate.py` 去掉 `doc_paths_exist` / `component_paths_exist` 放行名单
- [x] **干净检出**：仅导出 tracked 文件、无 `.git` 的沙箱里 24 pass / 0 fail / 0 na，且重跑生成器与提交账本逐字段一致
- [x] **方法仓门禁**：`scripts/check.sh` EXIT=0；acceptance 目标版本 2.0.3 全 PASS
- [x] **重绑**：目标项目 `upgrade verify` 12 pass / 0 warn，`method_assets.digest` 与目标账本一致
- [x] **发版**：`tag v2.0.3` + push；远端 `Governance invariants` 打印 `OK: 24 pass / 0 fail / 0 na（零放行）`，无 warning

### 本版边界（不掩盖）

- 只保证「不引用仓库外路径」，未扩大证据覆盖（verified 仍 20/47）；
- `manual` 型关闭条件仍需人主动关闭；
- 多副本同步税未处理：模板一改，主仓与示例仍需手工同步（由 `check.sh` 字节比对兜底）。

## v2.0.2 发布检查（业务诚信补丁）

> 由来：真实价值评估发现「24 条不变量全绿 + 3 条工作项全部完成却仍 open」并存，
> 结构自洽掩盖了业务说谎。本版只补这一件事与强制点。

- [x] **评估**：`feedback/DELIVERY-2.0.2.md` 记录结论、改动清单与负向证明
- [x] **实现**：`work_items.close_condition` + 不变量 #22 扩展；`work_panel close` 支持 `--resolution/--close-condition`
- [x] **方法仓门禁**：`scripts/check.sh` EXIT=0；acceptance 18 项 PASS；单测全绿
- [x] **目标项目**：3 条过期工作项关闭并写 resolution；24 不变量 24 pass/0 fail/0 na；upgrade verify 12 pass/0 warn，complete=true
- [x] **证据刷新**：重跑 24 个能力引用文件 182 passed，报告重绑，freshness=fresh，verified 仍 20/47
- [x] **强制点**：目标仓 `.github/workflows/governance.yml` + `git-hooks/pre-commit` 第 11 步
- [x] **发版**：`tag v2.0.2` + push（已完成）
- [x] **主仓提交**：技能树漂移按批准重算 manifest 后通过（未用 `--no-verify`），已推 origin/main

### 本版边界（不掩盖）

- `manual` 型关闭条件无法机器判定，仍需人主动关闭；
- 只补业务诚信与强制点，未做语义图 R4、未扩大证据覆盖（仍 20/47 verified）；
- 目标项目根仓库本次只提交治理文件、CI 与钩子，其余既有改动不动。


## v2.2.0 发布检查（绑定硬门禁 verified ⟺ bound）

- [x] **硬门禁**：`judge_tier(..., binding_status)` verified 改双条件（报告 pass +
      binding=bound）；via1/unbound/no_impl/no_tests 一律 declared；规则单一，
      verified 数必等于 bound 数
- [x] **同源绑定**：`binding_status_of_tests()` 在 `build()` 内基于实际证据
      (`ev["unit_test"]`/`ev["impl"]`) 计算并写入 cnode，与 `--check` 可复算同源
- [x] **防篡改**：第 7 条不变量校验 verified 必带 `binding_status=bound`；
      手改 tier / 抹字段 / 旧账本无字段必红（2 条负向用例）
- [x] **双向负向证明**：judge_tier unbound/no_impl/via1 拒绝 + bound 放行（4 条）；
      verifier 篡改绑定必抓（2 条）
- [x] **文档与派生**：METHOD_VERSION 2.2.0；EVIDENCE_TIER_SPEC、docs 03/08/11/23、
      CHANGELOG、ontology 派生重建
- [x] **主仓重绑**：干净 clone 重跑报告 → upgrade apply；verified 43→29；
      `--check` 无漂移；26 不变量零放行；远端 CI 绿


## v2.3.0 发布检查（派生 issue 闭环 + 方法仓自举）

- [x] **派生 issue**：`derived_issues.py` 第 6 个工具副本；非 bound 自动生成
      `source=derived` issue（固定 id、机器字段 + 人工字段保留）；转 bound
      自动关单；复用 `capability_verified` 不引入第二关单语义
- [x] **#27 不变量**：非 bound 缺 issue / bound 仍 open / 重复 / 孤儿均 fail；
      旧账本 na；负向用例 2 条先红后绿
- [x] **可复算**：生成器 `--check` 覆盖派生 issue，手删/篡改报漂移
- [x] **工具登记**：init_project / upgrade TOOLING(6) / scale_probe / check.sh /
      file_layout(6) / method_assets(templates 5) / test_modules / ontology 全同步
- [x] **方法仓自举**：`governance/` 6 能力；dogfood bound 6/6 + 第 7 能力
      unbound 自动生成 issue；330/330 测试；账本 25 pass / 0 fail / #27 ok；
      `--check` 含 issue 可复算
- [x] **文档**：METHOD_VERSION 2.3.0；CHANGELOG / docs 21 / docs 23 / DELIVERY
- [ ] **主仓推广**：干净 clone upgrade；14 个降级能力生成派生 issue；27 不变量
      零放行；`--check` 无漂移；远端 CI 绿（阶段2，待人批准）

## v2.1.2 发布检查（证据绑定与资产对账）

- [x] **符号级绑定 advisory**：`SymbolIndex`（再导出链 + 项目就近消歧）进生成器；
      `[BIND]`/`[UNBOUND]` 在 --check / dry-run / 写盘三路径都输出；
      `--binding-report` 机器可读；**不改 tier、不影响退出码**（shadow 门禁）
- [x] **advisory 测试**：直接绑定 / 相对导入再导出链 / via1 桥接 / 词面碰撞
      unbound 且 tier 不动 / no_impl·no_tests 分类，5 个用例（含
      `__init__.py` 相对导入多剥一层的回归钉）
- [x] **资产摘要统一**：`route_expert` 摘要规范化 = `asset_bundle` 的
      `sha256-files-v1`；`--check-assets` 逐文件 + 整包与清单对账，fail-closed；
      无清单 `manifest_checked=false`；篡改一字节必红（3 个用例）
- [x] **不变量 25**：`work_items_owned`——未完结工作必须有 owner 或 owner_note；
      done 不追溯；demo 夹具正反向覆盖
- [x] **不变量 26**：`installed_assets_binding`——副本↔清单↔账本三方对账，
      安装后绿、篡改后红；未安装 na；随 verify_ledger 部署，主仓 CI/pre-commit
      零新增步骤
- [x] **计数跟进**：24 → 26 不变量（docs/08/10/13/14/15/17/18/23、README、
      scripts 五处、acceptance 三态断言 `24 pass + 2 na`、ontology 断言、
      work_panel / tristate 用例）；MODULES.json 注册 `test_binding_advisory`
- [x] **派生文档重建**：ONTOLOGY.json/md（route_expert 摘要变化）、
      FILE_LAYOUT.md、SCENARIO_MATRIX.md、TEST_MODULES.md
- [x] **文档同步**：docs/03 声明的测试是否真测该能力（advisory 说明）；
      docs/08 不变量表 + 第 25/26 行；docs/23 版本表补 v2.1.2 行
- [x] **模块拆分**：advisory 独立为 `templates/binding_advisory.py`（生成器
      1665 → 1439 行，低于主仓 1500 模块大小硬限，不动 grandfathered 上限）；
      部署登记四处跟进（TOOLING / init_project / scale_probe / file_layout）
- [x] **全量门禁**：`bash scripts/check.sh` EXIT=0（acceptance 目标版本 2.1.2）

### 本版边界（不掩盖）

- advisory 判得对不对尚未被人审验证：主仓实测 unbound 10 个能力有待逐条
  人工核对后修映射（机械推荐报告另行生成供人审），修完才谈硬门禁；
- 绑定是必要条件不是充分条件：测试 import 了 impl 只说明有调用关系，
  不证明测的就是该能力的语义；
- via1 桥接只追一跳；`from x import *` 星号导入不解析（记 failure 不猜）；
- 不变量 26 只查清单登记的路径：清单外新增的 `.workbuddy` 文件（如旧版本
  残留）由方法仓侧 `asset_bundle verify` 才能发现；
- no_impl 能力（声明了测试但 impl 为空）只告警不阻断——映射修正属人批准
  迁移，本版不动 registry 数据。

## v2.20.0 发布检查（证据口径收口 / shadow 可解释 / 不变量派生）

> 由来：四项疑似缺陷先独立复现再判定，A/B/C 部分成立、D 已证实；共同根因是权威源与消费端断开，而非“写得不够多”。

- [x] **判定与分提交**：A `ad13c5d`、B `8c0bc62`、C `8abd095`、D `494f62d`，每笔提交写明判定与复现依据；未放宽既有判据，未改 `feedback/`，未加第三方依赖。
- [x] **发布前完善**：`shadow_pairs` 从 warning 文案升级为 JSON 全量对 + 人读报告独立小节；warnings 只显示前 5 组并指向 JSON。`acceptance.constants` 只从 `verify_ledger.py::verify()` 内 `add()` 派生不变量，排除模块层/辅助函数污染。新增 2 条专项测试。
- [x] **权威源重绑**：`METHOD_VERSION=2.20.0`；按官方 upgrade 流程执行 M3/M4/M5/M7 与同版 M5 增量重绑，`method_assets=5c1e275a20b4e337`、`installed_assets=145683f532bc89ab`、`ontology_digest=72b9e5bb96da3ad0`；自举账本与看板 EMBED 同步。
- [x] **全量门禁**：`bash scripts/check.sh` EXIT=0，16 阶段全绿；单测 473/473（绑定 38 个测试文件）；验收契约 full / preconditions 均 PASS；literal_drift 扫描 108 文件、0 漂移、10 处历史复核；31 条不变量 28 pass / 0 fail / 3 na。
- [x] **`feedback_closed = 7`**：`feedback/observations.jsonl` 13 行，7 closed / 6 open；本次未新增或改写观察包。
- [x] **发版**：附注 tag `v2.20.0` + push `origin/main` 与 tag；GitHub Release `v2.20.0` 以本版 CHANGELOG 为说明。

### 本版边界（不掩盖）

- shadow 只提示同义异码，不自动合并；是否合并/废弃仍由人工裁决。
- `run_tests.py --source-dir` 是显式 opt-in；缺省仍只绑定测试文件，源码变更不会让旧报告过期。
- `literal_drift` 对“不变量条数”保留「第 N 条」序号与小于 20 的子集计数排除，避免把历史序号误判成当前总数；真正权威仍是 `verify()` 派生值。
- 方法仓自举已重绑；主仓推广仍需单独批准，不在本版范围内。

## v2.20.1 发布检查（结构化暂停范围）

> 由来：主仓 `D-028` 已裁决“HELM 暂停，不补测试刷分”，但 `next_queue` 仍把 HELM 排在前两位。裁决是事实源，队列是唯一入口；两者不一致时执行者按队列干活就是在制造假绿灯。

- [x] **判定**：不是 HELM 能力需要补测试，而是暂停裁决缺机器可消费字段；不从散文猜“暂停”，猜错比不猜更危险。
- [x] **实现**：`entries[].paused_scopes` 为唯一结构化暂停字段；只认 `status=done` 且未被 `superseded_by` 取代的条目，按 project code 整段排除；字段缺失的历史账本保持原顺序。
- [x] **可复算**：`diff_queue_risk` 同时校验队列成员与风险注解；暂停导致成员缺失也算漂移，禁止手删账本绕过。
- [x] **测试**：新增 3 条 TDD 用例（结构化暂停排除、散文不猜、proposed/superseded 不生效）；476/476 单测通过。
- [x] **文档与副本**：`docs/05-循环协议.md` 写入 SELECT 暂停规则；`templates/build_capability_model.py` 与 `examples/demo-shop/governance/build_capability_model.py` 同步。
- [x] **权威源重绑**：`METHOD_VERSION=2.20.1`；官方 upgrade 执行 M3/M4/M5，`method_assets=8630eced4a8c9a4d`；本体投影重生成，自举账本与看板 EMBED 同步。
- [x] **全量门禁**：`bash scripts/check.sh` EXIT=0，16 阶段全绿；476/476 用例，验收契约 full / preconditions PASS，literal_drift 108 文件 0 漂移 10 历史复核，31 条不变量 28 pass / 0 fail / 3 na。
- [x] **`feedback_closed = 7`**：观察包 13 行，7 closed / 6 open；本次未改 `feedback/`。
- [x] **发版**：附注 tag `v2.20.1` + push `origin/main` 与 tag；GitHub Release `v2.20.1` 以本版 CHANGELOG 为说明。

### 边界

- 本版只提供机制，不为任何目标项目写入 `paused_scopes`；主仓 D-028 结构化与队列重排须单独批准执行。
- 暂停按 project 粒度，不支持模块/能力粒度； finer-grained pause 需另立契约。
- 字段缺失时不改变历史账本顺序，迁移是显式批准的动作，不是生成器猜测。

## v2.21.0 发布检查（目标架构对账链可信度收口）

> 由来：`TARGET_ARCHITECTURE.json` → `compare_graphs.py` 的规划图 vs 实际图链存在四项缺口。先独立复现、再判定、再分笔修复，不以「看起来像 bug」直接放宽判据。

- [x] **判定与分提交**：A 部分成立 `579ac0c`、B 已证实 `ec94fdc`、C 部分成立 `f702cad`、D 部分成立 `4338a7d`；技能执行语境 `5667bb1`、权威口径文档 `247c003`。每笔写明复现依据，未改 `feedback/`，未加第三方依赖。
- [x] **权威口径**：规划码唯一来源 `CAPABILITY_INDEX.md`（示例码污染 5/21=23.8% 归零）；`plan_status` 四态显式声明，规划图不可信时报告首行写明漂移结论不可采信；同层依赖稳定拓扑排序 + `dep_cycles` shadow；`alias_matches` → `shadow_pairs(kind=alias_suspect)` 只提示不裁决。
- [x] **测试**：新增 4 个专项 TDD 模块（`test_plan_status` / `test_plan_input_scope` / `test_dep_topology` / `test_alias_suspect`），单测 476 → 495（+19）；`tests/MODULES.json` 与 `docs/generated/TEST_MODULES.md` 同步。
- [x] **文档与技能**：`docs/13-可追溯性.md` 同步四项权威口径与实测代价；17 份 `SKILL.md` 补「执行语境（先读）」，目标项目内统一走单一入口，消除断链路径。
- [x] **权威源重绑**：`METHOD_VERSION=2.21.0`；官方 upgrade 执行 M4/M5/M7（工具副本已在同步状态，无 M3），`method_assets=476fb36e597eb6866`、`installed_assets=a344b3e9c84d3494`、`ontology_digest=137fb6cdab5b7b80f`；`upgrade verify` 全 pass、`plan` 为 noop，自举账本与看板 EMBED 同步。
- [x] **全量门禁**：`bash scripts/check.sh` EXIT=0，16 阶段全绿；单测 495/495，31 条不变量三态保持，literal_drift 无漂移。
- [x] **`feedback_closed = 7`**：本次未新增或改写观察包。
- [x] **发版**：附注 tag `v2.21.0` + push `origin/main` 与 tag；GitHub Release `v2.21.0` 以本版 CHANGELOG 为说明。

### 本版边界（不掩盖）

- shadow 只晒不裁决：同义异码是否合并/废弃、依赖环是否成真，仍由人工裁决；`status` / `level` 不受影响。
- 规划图缺失或为空时，diff 报告首行声明漂移结论不可采信，禁止拿空图反向证明「无缺口」。
- 规划码唯一来源是账本投影；手写文档只增强已有码，讲解示例不再污染规划集。
- 方法仓自举已重绑；主仓仍绑定 2.20.1，升级到 2.21.0 须单独批准，不在本版范围内。

## v2.22.0 发布检查（文档生命周期维度）

> 由来：路由/契约/技能三层对文档维度缺失。独立复现确认：doc 意图不识别（澄清 + low 兜底）、doc-rebuild 认文档但路由不认；未按任务书推测判为 plan/verify。

- [x] **判定**：路由缺 doc = 部分成立（实际 13 类非 14，兜底 ledger-steward 非 plan/verify）；技能/路由不一致 = 已证实；六契约缺文档维度 = 部分成立（读项提及、职责/写权/停止/交接全缺）；缺 doc-lifecycle = 已证实。
- [x] **工作流 A**：doc 类 + 冲突唯一负责人 + 文档交接链 + 复述门锚定；路由测试 8/8 绿，三条复现命令均命中 doc、负责人唯一、无澄清。
- [x] **工作流 B**：六份契约原地修订，权限矩阵互斥交叉检查 7/7 绿；未新增第 10 位专家。
- [x] **工作流 C**：doc-lifecycle 新增 + doc-rebuild/ledger-verify/ledger-guard/graph-compare 修订；技能纪律 6/6 绿，scaffold 产物被 lint 判 incomplete。
- [x] **工作流 D**：按官方升级 M4/M5/M7 重绑（approved-by user-approved-v2.22.0）；method_assets / asset_bundle / route --check-assets 三项一致（assets=33 / skills=24 / method_assets=5a7a02203d937fb8 / installed_assets=3ae603cad0acad77）。
- [x] **门禁**：`bash scripts/check.sh` 全绿；单测 495→517（只增不减，含 stale 过期红门负向）。
- [x] **边界**：五项文档不变量先 shadow 只告警；不为过门放宽既有判据；不改 feedback/；无第三方依赖；目标项目使用新副本需重新批准安装。

### 待人类拍板

- 五项文档不变量 shadow 期时长；升硬门前需确认 `docs.registry` 存量条目已覆盖。
- `declared_no_impact` 的批准人名单由人指定，AI 不得自批。

## v2.23.0 发布检查（docs 文件架构规范化）

> 由来：docs 内文件架构是否该规范化。独立核实：编号 01–36 连续、三层隔离已规范化，不动；四处口径漂移属实证，修权威源。

- [x] **判定**：编号/分层 = 已规范化（不动）；`docs/plan/` 路径冲突 = 已证实；generated 双作用域混列 = 已证实；`01-21` 残留 = 已证实；README 漏列 9 篇 = 已证实。
- [x] **修复**：doc_lifecycle 路径 → `docs/plans/`；STANDARD 第六节双作用域表；file_layout + 15 → `docs/NN-方法论文档`；README 补列并从代码派生计数（专家 9 / 技能 24 / 文档 36）。
- [x] **TDD**：新增 `tests/meta/test_doc_architecture.py` 6 用例，红灯 4 项 → 全绿；单测 517→523（只增不减）。
- [x] **权威链**：2.22.0→2.23.0，M4/M5，verify 全 pass、plan noop；ontology 重建绑定 1aa0f02348e0178b；method_assets 71dc5673ccd5b50e / installed_assets 3ae603cad0acad77。
- [x] **门禁**：`bash scripts/check.sh` 全绿；干净克隆复验通过。
- [x] **边界**：不改既有判据、不新增专家、不改 feedback/、不加依赖；目标项目需重新批准升级。

### 人类拍板

- 五项文档不变量仍为 shadow（v2.22.0 决定），本版未升硬门。
- `docs.registry` 存量登记仍需人决定是否首批入库。

## v2.24.0 发布检查（文档生命周期接进执行链）

> 第一性原理：信任必须由指纹与人工签名复算；规划只能来自人的声明，不能由账本现状自证。
> 澄清：v2.22.0 对 `PROJECT_STATE` / `--check` / ledger-guard 串接的宣称当时只改了文案，本版才落地。

- [x] **复现**：三条指控原始命令已贴；孤岛调用点、check.sh 无文档节、PROJECT_STATE 为 0、41 篇全 orphan 均实证。`verify_ledger` 有一条 `doc_paths_exist`（校验能力 `doc_index` 路径），评估者"无文档类不变量"的说法部分成立。
- [x] **工作流 A**：`check.sh` 新增 shadow 节并输出具体文件清单；默认退出码 0，`--strict` 阻断；收尾 16→17 节；五条不变量在 `skills/ledger-verify` 逐条对应实现位置。
- [x] **工作流 B**：`PROJECT_STATE.md` 从账本与 registry 渲染，连续两次逐字节相同；`--check` 抓手改并返回非 0；空账本给提示不崩；`file_layout` 与 README / STANDARD / 08 / 10 / 15 / 28 同步。
- [x] **工作流 C**：42 篇确定性播种进账本 `docs.registry`（唯一事实源），`status=draft`、`verified` 为空；`approve` 无签名拒绝；lint orphan=0、draft=42、verified=0；播种幂等。
- [x] **工作流 D**：计数从代码派生，历史条目未改写，`literal_drift` 0；单测 523→535。
- [x] **工作流 E**：E1 回测 16 `in_progress` → 16 `no_target`；E2 规划源改为 registry 声明，自身仓 `planned=17 / actual=16 / planned_only=1`。
- [x] **权威链**：M4/M5/M7 重绑，`verify` 全 pass、`plan` noop；`method_assets=9873b08f850e7c77` / `installed_assets=648c282a990b1a77` / `ontology=beb2146190093602`。
- [x] **门禁**：`bash scripts/check.sh` 全绿（535 tests / 漂移 0 / 17 节）；干净克隆复验通过。
- [x] **边界**：专家 9 / 技能 24 不变；未新增专家、未改看板版面、未改 `feedback/`、无第三方依赖、未放宽既有判据。

### 人类拍板（本版新增）

1. **shadow 升硬门条件**：连续 10 次 CI 运行 orphan=0 且 warn=0，且人工书面批准后才允许 `--strict` 进 CI 阻断；未满足前不得批量把 draft/suspect 置 current。
2. **docs.registry 批准人**：`seed` / `approve` 必须由 ledger-steward 角色签名；本版以 `user-approved-execution-chain` 作为批准标识由执行会话代录，需人类确认该批准人是否长期有效。

## v2.25.1 发布检查（四项拍板落盘）

> 第一性原理：拍板必须缩小解释空间，而不是增加一句更漂亮的文案。硬门条件、批准人、派生文档去留、会话授权边界都要能被脚本或目录清单复算。

- [x] **唯一升硬门条件**：连续 10 次 CI 运行中 `orphan=0`、`uncovered=0`、`obligation_missing=0`、`stale_unknown=0`、`suspect=0`、`stale=0`、`信任告警=0`、`派生漂移=0`，且任一指标不是 `n/a`，并经人工书面批准后才允许 `--strict` 进 CI；当前保持 shadow。
- [x] **owners 批准规则**：`owner` / `role` / `stale_after` 只能由人逐篇批准；禁止批量填充占位值或批量置 current。长期批准人为仓库维护者 `iczrac`，AI 不得自批。
- [x] **会话授权边界**：`user-approved-execution-chain` 仅作历史一次性会话授权，不作为长期 current 签名或 owner 指派身份；本版升级写入使用明确批准人。
- [x] **派生文档去留**：五份 `docs/generated/` 派生文档全部保持 `presence=on-demand`；`PROJECT_STATE.md` 不改为 required，删除后落入 `not_applicable`，手改落入 `hand-edited`；不为了让检查通过而提交其余四份。
- [x] **同步点**：`skills/ledger-verify`、`skills/doc-lifecycle`、`docs/08`、`docs/STANDARD`、`docs/10`、`docs/15`、`README` 与本节使用同一组硬门指标；新增三项回归测试锁定口径。

## Unreleased 发布硬项（防复发门禁）

第一性原理：文档里写下的命令是**可执行主张**，必须绑定到真实产物；一致性校验只能证明「副本 = 源」，不能证明「源是真的」。以下每项都是可复算命令，不是勾选承诺；任一失败即不得升版本、不得打 tag / 发版。

- [ ] **本仓全门禁**：`bash scripts/check.sh` 全绿（含规范自查阶段；命中和 `n/a` 分列，命中必须为 0）。
- [ ] **主张判据**：`python3 scripts/spec_check.py --target .` 的 `executable_claims` 适用且零命中；例外只允许写在 `spec_check.json` 的 `claims.exceptions`，带理由 / 批准人 / 到期日，禁通配。
- [ ] **资产边界**：`python3 scripts/asset_bundle.py --check` 通过；`install --apply` 遇到未解析命令必须拒绝写盘（负向证明见 `tests/views/test_assets.py`）。
- [ ] **升级器自检**：`python3 scripts/upgrade.py check` 通过——资产定义、模块映射与主张判据共用同一检查器，不复制第二份。
- [ ] **消费方门禁**：在 `julia-dev-squad` 仓根执行 `bash scripts/check.sh` 全绿；该脚本调用同一份 `spec_check.py`，组合锚声明的兄弟仓工具必须真实存在。
- [ ] **人工确认**：以上命令的实际输出贴入本次发版记录；AI 不得代签。未升 `METHOD_VERSION`、未打 tag、未生成 Release 包时，以上检查只做本地验证，不宣称「已发布」。
- [ ] **主账本自校验**：`bash scripts/check.sh` 新增第 18 个阶段 `stage_verify_main`（`python3 governance/verify_ledger.py --root . --strict`，走默认参数、不传 `--ledger/--registry/--board`）；旧 `stage_verify` 只验示例账本，不能替代主账本。`tests/meta/test_spec_gate.py` 同时锁函数定义 / run 接线 / 全绿枚举三处，并用临时副本写坏 `analytics.test_pass_rate.detail` 证明该阶段非零。

**证据报告与门禁口径（P1 已知差异）**：P1 新增一个测试方法后，committed `governance/test_report.json`（617 cases）与 `unittest discover` 口径（618 cases）存在已知静态差异；**committed 报告刻意不重生成**——`check.sh` 的 `stage_tests` 用 `mktemp` 现生成报告，只断言 `total>=170` 与绑定文件数，不读 committed 报告。示例项目 demo 的独立 3 cases 报告可豁免。下一次任何 re-baseline 必须把「报告重生成 → `work_panel.py sync-tests` → `build_capability_model.py` 重算 → 看板重建」当成一个原子单元；只重生成报告会令第 24 条 `test_results.source_sha256` 陈旧 FAIL（与 Task#20 F-1 同一根因）。

### 提交与发版原子口径（B 收口版）

第一性原理：原子化要绑在**可复算的状态边界**上，不是绑在不可机器判定的「决策」上。Git 不记录一个 commit 属于哪个决策，因此「一个 commit 一个决策」既无法机械校验，也必然退化为纸面承诺（与 `ledger_entry` 同一失败模式），明确拒绝。只保留两条可复算约束：

1. **派生一致性原子（提交边界）**：一个 commit 的状态边界 = `bash scripts/check.sh` 全绿。权威源与派生物（`docs/generated/`、`governance/index.html`）+ `spec_check.json` + 绑定测试必须落在**同一个 commit**。拆 commit 时不按主题拆，按派生一致性拆；机器可判定的边界是**发版／回滚边界**（版本锚 + tag 或当前全绿 HEAD），不要求每个中间 commit 各自全绿。中间 commit 的非绿状态必须如实记录，不得当作回滚点；若需要可逐个回滚的中间快照，就合为一个全绿 commit。
2. **发版逻辑原子（版本边界）**：版本锚 + tag 构成发版的逻辑原子；`python3 scripts/spec_check.py --target .` 的 `compat`（兄弟仓 `METHOD_VERSION` ≥ 声明的 `min_version`；**julia 侧适用，ledger 自身为 n/a**）与 `release_tag`（本仓版本有对应 tag）判据已 fail-closed 检查。

**诚实边界**：跨仓物理原子在 Git 中不存在，明确放弃；不引入 monorepo / submodule 等结构性改动。`compat` 读的是兄弟仓**工作树**的 `METHOD_VERSION`，不是兄弟仓的 tag；因此「tag 提交顺序」仍是人工纪律，机器只保证版本锚与「本仓版本已打 tag」，不得对外宣称「跨仓顺序已机器强制」。

**防复发判准**：本节任何「原子」承诺若不含可复算命令与判据，它本身就是下一条 `ledger_entry`——判准是「这句话有没有对应的判据与复算命令」。
