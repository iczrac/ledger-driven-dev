# 发布前自检清单

发布到 GitHub 前逐项勾选。已在本地验证通过的标注 ✓。

## 功能完整性

- [x] 生成器可从 registry 读取项目定义，路径参数化（--root/--registry/--ledger/--board）
- [x] 完成度由证据逐级判定 L0-L5，禁止手填，可回落
- [x] 嵌套组件树从真实目录生成，深度/规模可控
- [x] 文档索引分 8 类 + 关联决策，路径存在性校验
- [x] 看板 10 个标签视图（含工作台 / 工作项）可渲染，节点工作条显示 TODO / issue / 测试；内嵌数据由生成器同步；CSS/DOM/JS 骨架与模板一致，按 PAGE_SIZE 分批
- [x] 循环协议写入 capability_model
- [x] 可信性校验器：24 条不变量（含证据分层），支持 --json / --strict
- [x] 证据分层：declared/verified，run_tests.py 产出实测报告，生成器 --test-report 判定升级
- [x] 看板显示 tier 徽章与 verified 覆盖率；任务卡携带 tier 与 needs_runtime_verification
- [x] SELECT 任务队列：生成器产出 next_queue，dry-run 可见，任务卡携带已确认经验
- [x] 历史层：状态指纹驱动 append-only 事件，重跑幂等，支持状态快照回放
- [x] 经验层：自动识别候选 + 人工确认 + 任务卡消费，看板两视图可见可点
- [x] 一键初始化脚本可用（含校验器），支持 greenfield / adopt 双模式与 provenance 记录
- [x] 八种专家角色（路由 / 新建 / 考古 / 账本治理 / 审计 / 执行 / 生命周期 / 平台治理），各含权限矩阵与停止条件
- [x] 二十个技能（route/discover/bootstrap/scan/verify/decide/lesson/guard/doc-rebuild/graph-compare/scenario-guard/layout-inspect/ledger-upgrade/agent-gate/method-assets/board-layout/scale-budget/asset-install/test-map/work-panel），标准 SKILL.md frontmatter
- [x] 技能脚本：重复立项、缺行动经验、无理由驳回均由代码拒绝
- [x] 195 个 unittest 用例（含 12 个升级、15 个网关、2 个元层路由、16 个资产/骨架/规模专项、21 个 v1.2.0 资产/测试架构/工作台专项），零第三方依赖，临时目录隔离
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
- [x] `bash scripts/check.sh` 全绿：195 测试（双发现口径）/ 测试架构 / 24 不变量 / 60 场景 / 31 条目 + 12 字段布局 / 升级与接入端到端 / 资产与工作台契约 / 幂等 / 同步 / 脱敏 / 文档链接
- [x] 看板 JS 通过 `node --check`；CI 用同一份门禁脚本，口径一致
- [x] 负向纪律测试：重复立项、缺 action、无理由驳回均被拒绝

## 多专家接入（0.6.0）

- [x] 路由脚本只读、确定性，账本损坏/意图冲突时 fail-closed
- [x] 存量项目盘点只写草稿与报告，不覆盖既有治理文件与源码
- [x] 新建/接入均写入 provenance，外部路径不泄露绝对路径
- [x] 接入模式生成后可通过 24 条不变量校验
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

- [x] `upgrade.py` 定义自检：3 个工具来源、8 条迁移、18 步 post_upgrade 均存在
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
- [x] `tests/MODULES.json`：6 个开发模块 / 21 个测试文件；`MODULE_ID` 自证、`rglob` 与 `unittest discover` 双口径一致
- [x] `test_modules.py --check` 与 `docs/generated/TEST_MODULES.md` 渲染同步；`--target examples/demo-shop` 输出模块单测缺口
- [x] `work_items` / `test_results` 两个账本内字段；`work_panel.py` 写动作全部需人批准；`sync-tests` 绑定报告字节
- [x] 24 条不变量中的 `work_items_valid` / `work_item_refs_valid` / `test_results_binding_valid` 均有负向证明
- [x] 看板 10 个 tab：工作台 / 工作项视图与节点工作条；Node DOM stub 证明空账本不崩；骨架归一到 `735bcd09…`
- [x] `work_panel.py nodes` 与看板 JS 按同一规则复算派生聚合，不落盘、无第三份事实源
- [x] 规模预算新增 `work_items`（10 项阈值）；场景矩阵 60 / 10 轴、覆盖率 84.2%（47 / 7 / 5 / 1）
- [x] 版本六轴、8 条迁移、18 步 `post_upgrade`、11 项 `verify`、八项 `upgrade_complete` 判据均由定义自检与测试复算
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
- [x] 二十一篇编号方法论文档 + STANDARD.md + CONTRIBUTING.md
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
- [ ] 已引入项目重新批准升级（M4 + M5）重绑摘要（由项目负责人决定，不自动执行）
