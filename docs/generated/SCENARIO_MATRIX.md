# 场景覆盖矩阵（生成物）

> 由 `scripts/scenario_matrix.py` 从场景定义渲染。**不要手改本文件**；
> 修改场景请改 `SCENARIOS`，再重跑 `--emit-md`。

共 60 个场景 · 有效覆盖率 84.2% （covered 计 1，partial 计 0.5，by-design 与 gap 计 0）。

| 状态 | 数量 | 语义 |
|---|---:|---|
| 已覆盖 | 47 | 已覆盖（有探针） |
| 部分 | 7 | 部分覆盖（有降级与告警，残差见文档） |
| 边界 | 5 | 边界内刻意不做（附理由） |
| 缺漏 | 1 | 已知缺漏（本期未实现） |

## 场景逐项

| ID | 轴 | 场景 | 公理 | 状态 | 期望行为 | 探针 |
|---|---|---|---|---|---|---|
| L1 | 生命周期 | 空目录新建项目 | A6 | 已覆盖 | greenfield-architect 建最小骨架，缺 registry 时不得声称完成度 | `test_routing.RoutingTest.test_greenfield_empty_dir` |
| L2 | 生命周期 | 历史项目无损接入 | A6 | 已覆盖 | 只读盘点产出草稿，人工确认前不覆盖任何既有文件 | `test_discovery + test_bootstrap` |
| L3 | 生命周期 | 稳态迭代 | A1 | 已覆盖 | SCAN→SELECT→PLAN→EXECUTE→VERIFY 可循环，重跑幂等 | `test_generation + test_history` |
| L4 | 生命周期 | 半成品（有账本缺 registry） | A5 | 已覆盖 | 路由到 ledger-steward 补齐唯一手写清单，不重建 history | `test_routing.RoutingTest.test_partial_state` |
| L5 | 生命周期 | 账本 JSON 损坏 | A5 | 已覆盖 | 冻结写入，先备份再人工修复，verify 通过前不得继续 | `test_scenarios.ScenarioProbeTest.test_corrupt_ledger_blocks_writes` |
| L6 | 生命周期 | 发布窗口冻结 | A6 | 已覆盖 | lifecycle freeze 后 guard 阻止所有写动作；生成器返回 2 | `test_lifecycle.LifecycleTest.test_freeze_blocks_generator` |
| L7 | 生命周期 | 归档与移交 | A6 | 已覆盖 | archive 需人工批准，转为不可写终态；只读取证仍可用 | `test_lifecycle.LifecycleTest.test_archive_is_terminal` |
| L8 | 生命周期 | 冻结期误写 / AI 自行解冻 | A1 | 已覆盖 | unfreeze 无 approved-by 被拒绝；批准人写入 lifecycle.approved_by | `test_lifecycle.LifecycleTest.test_unfreeze_requires_human_approval` |
| L9 | 生命周期 | 能力退役与编码不复用 | A6 | 已覆盖 | retire 登记四段式编码 + 取代关系；仍活跃则 guard block | `test_scenarios.ScenarioProbeTest.test_retired_cap_conflict_blocks` |
| L10 | 生命周期 | 模块拆分 / 重命名 | A4 | 部分 | 编码稳定不随名称变化，但无自动 rename 映射表 | `test_generation` |
| C1 | 变更 | 新增能力 | A1 | 已覆盖 | 等级从证据重算，未达 L5 自动生成 next_action | `test_generation` |
| C2 | 变更 | 等级上调 | A2 | 已覆盖 | 补齐契约/实现/单测/记录才升级；指纹链追加事件 | `test_history` |
| C3 | 变更 | 等级回落 / 证据消失 | A2 | 已覆盖 | 证据文件删除后等级回落，历史事件记录降级信号 | `test_generation + test_history` |
| C4 | 变更 | declared → verified | A2 | 已覆盖 | 只有报告 overall=pass 且匹配单测才升级 | `test_evidence_tier.EvidenceTierTest.test_generator_with_report_upgrades_matching_caps` |
| C5 | 变更 | 报告丢失 / 整体失败 | A5 | 已覆盖 | 全部回落 declared，不保留旧 verified 徽章 | `test_evidence_tier.EvidenceTierTest.test_failed_report_never_upgrades` |
| C6 | 变更 | 报告过期（源码改了但没重跑测试） | A2 | 已覆盖 | 源码摘要不匹配 → 报告不予采信，verified 回落 declared | `test_scenarios.ScenarioProbeTest.test_stale_report_downgrades_evidence` |
| C7 | 变更 | 决策取代 / 撤回 | A4 | 已覆盖 | supersedes 双向一致，取代链连续 | `test_verify` |
| C8 | 变更 | 目标架构变更 | A1 | 部分 | compare_graphs 显示 planned_only/actual_only 差异 | `test_compare_graphs` |
| C9 | 变更 | 外部数据源 / 依赖版本变化 | A2 | 边界 | 不绑定具体数据源；由项目自己的测试报告表达 | `test_evidence_tier` |
| P1 | 并发 | 单人连续重跑（幂等） | A4 | 已覆盖 | 状态未变不追加历史事件，看板 EMBED 保持同步 | `test_generation + check.sh stage_idempotence` |
| P2 | 并发 | 两 Agent 同时写账本 | A3 | 已覆盖 | 读取时指纹与当前不符 → CAS 拒绝写入，退出码 2 | `test_scenarios.ScenarioProbeTest.test_cas_rejects_stale_write` |
| P3 | 并发 | 读后写漂移（人工手改账本） | A4 | 已覆盖 | guard 报 concurrent_write block；history 指纹链可发现篡改 | `test_scenarios.ScenarioProbeTest.test_fingerprint_drift_detected` |
| P4 | 并发 | 长任务中断后恢复 | A4 | 已覆盖 | claim/release 记录领用者；超时锁在 guard 中告警 | `test_lifecycle.LifecycleTest.test_claim_release` |
| P5 | 并发 | 同一任务被两个 Agent 领用 | A3 | 已覆盖 | 第二次不同 actor 的 claim 被拒绝 | `test_lifecycle.LifecycleTest.test_duplicate_claim_rejected` |
| P6 | 并发 | CI 与本地结论不一致 | A5 | 部分 | 同一份 check.sh 消除口径差异；环境差异仍需显式声明 | `check.sh` |
| T1 | 时间 | 首次运行（无账本） | A6 | 已覆盖 | 生成器创建空账本骨架并写入首个历史事件 | `test_generation` |
| T2 | 时间 | 跨版本升级 / 迁移 | A5 | 已覆盖 | 兼容版本走 plan→备份→人批准 apply→verify→重新取证；不兼容账本仍 fail-closed，不猜结构 | `test_upgrade.UpgradeTest.test_apply_is_approved_backed_up_and_verifiable + test_scenarios.ScenarioProbeTest.test_unsupported_version_blocks` |
| T3 | 时间 | 历史回溯 / 外部取证 | A4 | 已覆盖 | 事件指纹自证、末事件指纹 == 当前能力模型指纹 | `test_verify + test_history` |
| T4 | 时间 | git 历史被 rebase / force push 重写 | A4 | 部分 | 浅克隆被 guard 告警；trace_git 不信任 commit message | `test_trace_arch_git` |
| T5 | 时间 | 报告时间戳跨时区 | A2 | 已覆盖 | 新鲜度用内容摘要判定，不依赖时间戳比较 | `test_scenarios.ScenarioProbeTest.test_freshness_uses_content_not_clock` |
| E1 | 环境 | 非 git 目录 | A5 | 已覆盖 | guard 告警；trace_git 退出码 2，不伪造提交关联 | `test_trace_arch_git` |
| E2 | 环境 | 没有测试 / 没有单测 | A2 | 已覆盖 | 全部能力保持 declared，verified 覆盖率为 0 | `test_evidence_tier` |
| E3 | 环境 | 没有文档 / 文档是自由散文 | A5 | 已覆盖 | architect_from_docs 置信度降级为 low 并给 warnings | `test_trace_arch_git` |
| E4 | 环境 | 只读文件系统 | A6 | 边界 | guard / verify / trace / route 可只读运行；生成器需要写权限 | `test_scenarios.ScenarioProbeTest.test_guard_is_read_only` |
| E5 | 环境 | 超大仓库扫描截断 | A5 | 已覆盖 | 扫描达上限标记 truncated，guard 告警，不声称全量覆盖 | `test_discovery + test_scenarios.ScenarioProbeTest.test_truncated_scan_warns` |
| E6 | 环境 | 非 UTF-8 / Windows 路径 | A5 | 部分 | JSON/HTML 统一 UTF-8，路径相对化；未做跨平台 CI 矩阵 | `test_trace_docs` |
| E7 | 环境 | monorepo 多项目 / 跨仓依赖 | A1 | 缺漏 | 当前 registry.project.root 只描述单个项目根 | `—` |
| F1 | 失败 | 未批准就执行 / 越权写账本 | A1 | 已覆盖 | ledger_decide 只写 proposed；解冻/归档必须人工批准 | `test_skills + test_lifecycle` |
| F2 | 失败 | 人驳回提议 / 优先级争议 | A3 | 边界 | 条目留 deferred/proposed，AI 不替人决定业务优先级 | `test_skills` |
| F3 | 失败 | 测试偶发失败（flaky） | A2 | 边界 | 报告如实记录 fail，不自动重试 | `test_evidence_tier` |
| F4 | 失败 | 绝对路径 / 来源项目名词泄露 | A5 | 已覆盖 | guard block；check.sh 卫生阶段扫描全仓 | `test_scenarios.ScenarioProbeTest.test_absolute_path_blocks` |
| F5 | 失败 | 模板与示例副本漂移 | A5 | 已覆盖 | check.sh 同步阶段逐字节比较；guard 告警 | `check.sh stage_sync` |
| F6 | 失败 | 看板 EMBED 与账本不一致 | A3 | 已覆盖 | verify 的 board_embed_synced 失败；guard 告警 | `test_verify` |
| F7 | 失败 | 多人同时改 registry.json | A3 | 部分 | 网关对依赖手写清单的动作要求 --expect-registry-sha，内容摘要漂移即拒绝（检测，不合并） | `test_agent_gateway.GatewayTest.test_registry_cas_detects_concurrent_edit` |
| U1 | 时间 | 工具副本落后于权威模板 | A5 | 已覆盖 | plan 报 drifted/missing 并要求 M3 同步；verify 的 tool_hashes 不通过 | `test_upgrade.UpgradeTest.test_plan_detects_tool_drift` |
| U2 | 时间 | 升级后证据未重新绑定 | A2 | 已覆盖 | verify 报 evidence_rebaseline warn，upgrade_complete=false；post_upgrade 要求先重跑报告再 --strict-evidence 生成 | `test_upgrade.UpgradeTest.test_verify_flags_stale_evidence` |
| G1 | 接入 | 未注册 / 越权 Agent 写账本 | A3 | 已覆盖 | 默认拒绝：access 缺失、agent 未登记、角色无权、scopes 越界均 deny 且不写盘 | `test_agent_gateway.GatewayTest.test_unregistered_and_unauthorized_denied` |
| G2 | 接入 | 两个 Agent 并发写同一能力 | A4 | 已覆盖 | flock 锁内重读、指纹 CAS、编码租约与 revision 共同阻止静默覆盖 | `test_agent_gateway.GatewayTest.test_lease_blocks_concurrent_agent` |
| G3 | 接入 | Agent 自我批准 / 自行提权 | A1 | 已覆盖 | register 的 approved_by 不得等于 agent；unfreeze/archive 必须人批准 | `test_agent_gateway.GatewayTest.test_self_approval_and_self_register_denied` |
| G4 | 接入 | Agent 直接调用底层脚本绕过网关 | A5 | 边界 | 网关是策略执行点，不是 OS 沙箱；有 shell 仍可绕过 | `test_agent_gateway.GatewayTest.test_policy_point_boundary_is_declared` |
| U3 | 时间 | 专家 / 技能 / 模板 / 文档资产漂移 | A2 | 已覆盖 | 整包资产摘要写进账本；任一资产变化即 plan 要求 M5 重新批准，verify 不再宣布完成 | `test_platform_contract.AssetsTest.test_upgrade_binds_assets_and_detects_drift` |
| F8 | 失败 | 项目手改看板 CSS / DOM 形成差异化版面 | A3 | 已覆盖 | 去 EMBED 后的骨架 sha256 漂移；plan 列入 M6，归一化后数据段仍与账本等价 | `test_platform_contract.BoardTest.test_drift_is_part_of_the_upgrade_plan` |
| S1 | 规模 | 大项目账本体积 / 历史事件 / DOM 超预算 | A6 | 已覆盖 | scale_budget.py 按单一阈值表报 ok/warn/exceed，模板按 PAGE_SIZE 分批渲染，治理层文件数保持固定 | `test_platform_contract.BudgetTest.test_thresholds_flag_oversized_project` |
| S2 | 规模 | 生成器全量重算的成本 | A2 | 部分 | 可复现基准 + 阈值告警；超阈值由人决定拆项目或归档，不做静默降级 | `test_meta.test_platform_contract.BudgetTest.test_probe_shows_file_count_stays_fixed` |
| U4 | 时间 | 项目内手改已安装的 SKILL.md / EXPERT.md | A3 | 已覆盖 | asset_bundle.py verify 报 drift，upgrade.py verify 的 installed_assets 项 warn，upgrade_complete=false；必须重新批准 M7 安装 | `tests.views.test_assets.AssetsTest.test_installed_copy_drift_is_detected` |
| U5 | 时间 | 专家/技能升级后 Agent 仍用旧卡片 | A2 | 已覆盖 | route_expert.py 读取真实 EXPERT.md / SKILL.md frontmatter 并把资产摘要写进路由结果；缺文件即 --check-assets fail-closed | `tests.views.test_assets.AssetsTest.test_router_consumes_installed_assets` |
| V1 | 视图 | 模块 / 组件上看不到 TODO 与 issue | A1 | 已覆盖 | work_items 按 scope 覆盖项目/模块/能力编码；nodeWork 与 work_panel.py nodes 用同一规则复算，节点卡片显示条数、健康度并可下钻 | `tests.views.test_work_panel.WorkPanelTest.test_node_summary_scopes_work_items` |
| V2 | 视图 | 手填测试结果投影伪造全绿 | A2 | 已覆盖 | test_results.source_sha256 必须等于当前 test_report.json 的 sha256；24 条不变量里 test_results_binding_valid 会拦下 | `tests.views.test_work_panel.WorkPanelTest.test_tampered_projection_fails_verifier` |
| V3 | 视图 | 新项目尚无工作态数据 | A5 | 已覆盖 | 工作台/工作项视图与节点条在无 work_items / test_results 时显示空态而非报错；全部能力按 declared 显示，不伪装成 verified | `tests.views.test_board_views.BoardViewsTest.test_work_views_degrade_without_data` |
| T6 | 结构 | 测试文件未按开发模块归属 / 清单漂移 | A1 | 已覆盖 | tests/MODULES.json + 文件内 MODULE_ID + rglob 三方一致才算通过；模块名与标准库冲突也会被拦 | `tests.views.test_test_modules.TestModulesTest.test_map_module_id_and_discovery_agree` |

## 最短流程（playbook）

### 变更

- **C1 新增能力**（已覆盖）：`编辑 registry.json` → `重跑生成器`
- **C2 等级上调**（已覆盖）：`补证据` → `重跑生成器` → `verify_ledger.py`
- **C3 等级回落 / 证据消失**（已覆盖）：`重跑生成器` → `查看 GRAPH_DIFF`
- **C4 declared → verified**（已覆盖）：`run_tests.py --dir tests --out governance/test_report.json` → `build_capability_model.py --root P --test-report ...`
- **C5 报告丢失 / 整体失败**（已覆盖）：`重跑生成器（不带报告）`
- **C6 报告过期（源码改了但没重跑测试）**（已覆盖）：`run_tests.py → 生成账本` → `修改测试文件` → `重跑生成器（同一报告）`
  - v0.8.0 前是假绿灯：judge_tier 只按文件名匹配
- **C7 决策取代 / 撤回**（已覆盖）：`ledger_decide.py` → `verify_ledger.py`
- **C8 目标架构变更**（部分）：`architect_from_docs.py` → `compare_graphs.py`
  - 残差：差异只报告，不自动回写 registry；避免文档误读直接改动事实源
- **C9 外部数据源 / 依赖版本变化**（边界）：`在被测项目内跑 run_tests.py`
  - 理由：方法论项目不应持有外部系统凭据或版本知识

### 失败

- **F1 未批准就执行 / 越权写账本**（已覆盖）：`ledger_decide.py` → `verify_ledger.py`
- **F2 人驳回提议 / 优先级争议**（边界）：`账本条目置 deferred 并写明理由`
  - 理由：优先级是业务判断，不应用脚本推断
- **F3 测试偶发失败（flaky）**（边界）：`run_tests.py --out report.json`
  - 理由：自动重试会把不稳定测试伪装成通过；稳定性应在被测项目内解决
- **F4 绝对路径 / 来源项目名词泄露**（已覆盖）：`bash scripts/check.sh`
- **F5 模板与示例副本漂移**（已覆盖）：`bash scripts/check.sh`
- **F6 看板 EMBED 与账本不一致**（已覆盖）：`重跑生成器`
- **F7 多人同时改 registry.json**（部分）：`agent_gateway.py status 取 registry_sha256` → `request ... --expect-registry-sha <sha>` → `git 人工合并冲突`
  - 残差：只检测漂移，不自动合并；无 workspace 层时跨项目联合门禁仍缺（E7）
- **F8 项目手改看板 CSS / DOM 形成差异化版面**（已覆盖）：`board_contract.py --target P check --json` → `upgrade.py --target P apply --approved-by <人>` → `board_contract.py --target P check`
  - 要换样式只能改方法论模板并发版，再由升级推到所有项目

### 并发

- **P1 单人连续重跑（幂等）**（已覆盖）：`build_capability_model.py --root P（两次）`
- **P2 两 Agent 同时写账本**（已覆盖）：`读 current_fingerprint` → `build_capability_model.py --expect-fingerprint FP`
- **P3 读后写漂移（人工手改账本）**（已覆盖）：`scenario_guard.py --target P --expect-fingerprint FP --strict`
- **P4 长任务中断后恢复**（已覆盖）：`lifecycle.py claim --code ... --actor ai-1` → `（中断）scenario_guard.py --json` → `lifecycle.py release`
- **P5 同一任务被两个 Agent 领用**（已覆盖）：`lifecycle.py claim --code ... --actor ai-2（应失败）`
- **P6 CI 与本地结论不一致**（部分）：`本地 bash scripts/check.sh` → `CI 同一命令`
  - 残差：Python 版本 / 时区 / 文件系统大小写敏感未做矩阵测试

### 接入

- **G1 未注册 / 越权 Agent 写账本**（已覆盖）：`upgrade.py apply 建立 access` → `register --approved-by <人>` → `agent_gateway.py request --json（默认 dry-run）`
  - 权限从 EXPERT.md 的散文移到写入口的九道门
- **G2 两个 Agent 并发写同一能力**（已覆盖）：`status 取 fingerprint / registry_sha` → `request --expect-fingerprint <fp> --apply`
  - 同一能力编码在租约 TTL 内只属于先登记的 Agent；超时由人清理
- **G3 Agent 自我批准 / 自行提权**（已覆盖）：`register --approved-by <人>` → `request --action unfreeze --approved-by <人>`
  - 权限授予者 ≠ 被授权者，批准人写入 access.audit 与 lifecycle.approved_by
- **G4 Agent 直接调用底层脚本绕过网关**（边界）：`平台只把 agent_gateway.py 注册为写工具` → `CI 只接受带 audit 的产物`
  - 理由：强隔离需要容器 / 只读挂载 / 文件系统权限，超出纯文本方法范围；刻意不在脚本里伪装成安全边界

### 时间

- **T1 首次运行（无账本）**（已覆盖）：`build_capability_model.py --root P`
- **T2 跨版本升级 / 迁移**（已覆盖）：`upgrade.py --target P plan --json` → `upgrade.py --target P apply --approved-by <人>` → `upgrade.py --target P verify --json` → `执行 post_upgrade 18 步`
  - 迁移只加字段，不改 history.events，因此不追加历史事件；真正的 ledger_version 数据迁移仍需人工写专用方案
- **T3 历史回溯 / 外部取证**（已覆盖）：`verify_ledger.py --strict --json`
- **T4 git 历史被 rebase / force push 重写**（部分）：`scenario_guard.py --json` → `trace_git.py`
  - 残差：无法从本地证明远端未强制推送；需外部签名/服务端保护
- **T5 报告时间戳跨时区**（已覆盖）：`run_tests.py` → `build_capability_model.py --test-report ...`
- **U1 工具副本落后于权威模板**（已覆盖）：`upgrade.py --target P plan --json` → `upgrade.py --target P apply --approved-by <人>`
  - check.sh 只同步本仓库模板/示例，管不到已交付项目的工具副本，这一层由 upgrade 补
- **U2 升级后证据未重新绑定**（已覆盖）：`run_tests.py --out governance/test_report.json` → `build_capability_model.py --test-report ... --strict-evidence`
  - 工具源码变化会让 evidence_binding 失配，verified 回落 declared 是正确行为，危险的是没人重跑
- **U3 专家 / 技能 / 模板 / 文档资产漂移**（已覆盖）：`method_assets.py --check` → `upgrade.py --target P plan --json` → `upgrade.py --target P apply --approved-by <人>`
  - 资产随方法论仓库 tag 升级、不复制进目标项目；绑定的是摘要，不是第二份文件
- **U4 项目内手改已安装的 SKILL.md / EXPERT.md**（已覆盖）：`asset_bundle.py verify --target P --json` → `upgrade.py --target P plan --json` → `asset_bundle.py install --target P --apply --approved-by <人>`
  - 副本是只读部署产物，不是可编辑的第二份规则；清单外的 .workbuddy 文件不动
- **U5 专家/技能升级后 Agent 仍用旧卡片**（已覆盖）：`route_expert.py --target P --check-assets --json` → `route_expert.py --target P --intent 升级治理骨架 --json`
  - 资产不再只是摘要：安装的副本优先于方法论仓库源被路由消费

### 环境

- **E1 非 git 目录**（已覆盖）：`trace_git.py --target P`
- **E2 没有测试 / 没有单测**（已覆盖）：`build_capability_model.py --root P`
- **E3 没有文档 / 文档是自由散文**（已覆盖）：`architect_from_docs.py --target P`
- **E4 只读文件系统**（边界）：`scenario_guard.py --target P --json`
  - 理由：生成与校验分离，审计者无需写权限
- **E5 超大仓库扫描截断**（已覆盖）：`scenario_guard.py --max-files N --json`
- **E6 非 UTF-8 / Windows 路径**（部分）：`保持源码 UTF-8` → `避免绝对路径写入账本`
  - 残差：Windows 换行与大小写敏感差异未在 CI 覆盖
- **E7 monorepo 多项目 / 跨仓依赖**（缺漏）：`每个项目各自 governance/，用外层脚本聚合`
  - 缺漏：无跨项目依赖图与联合门禁；需要独立的 workspace 层，本期未做

### 生命周期

- **L1 空目录新建项目**（已覆盖）：`route_expert.py --target P` → `init_project.py --target P --mode greenfield`
- **L2 历史项目无损接入**（已覆盖）：`discover_project.py --target P --dry-run` → `discover_project.py --target P` → `init_project.py --target P --mode adopt --from-draft ...`
- **L3 稳态迭代**（已覆盖）：`build_capability_model.py --root P`
- **L4 半成品（有账本缺 registry）**（已覆盖）：`route_expert.py --target P` → `补齐 governance/registry.json`
- **L5 账本 JSON 损坏**（已覆盖）：`scenario_guard.py --target P --strict` → `备份并修复账本` → `verify_ledger.py --strict`
- **L6 发布窗口冻结**（已覆盖）：`lifecycle.py --target P freeze --reason ...` → `lifecycle.py --target P unfreeze --approved-by <人>`
- **L7 归档与移交**（已覆盖）：`lifecycle.py --target P archive --approved-by <人>` → `verify_ledger.py --root P --strict` → `打包 governance/ 交付`
- **L8 冻结期误写 / AI 自行解冻**（已覆盖）：`lifecycle.py --target P unfreeze --approved-by <人>`
- **L9 能力退役与编码不复用**（已覆盖）：`lifecycle.py --target P retire --code ... --reason ...` → `从 registry.json 移除该能力` → `build_capability_model.py --root P`
- **L10 模块拆分 / 重命名**（部分）：`保留编码，仅改 registry.name` → `重跑生成器`
  - 残差：跨仓/跨项目引用无法自动重写，需人工 new → old 映射并写入决策

### 结构

- **T6 测试文件未按开发模块归属 / 清单漂移**（已覆盖）：`test_modules.py --check` → `run_tests.py --dir tests --top . --out report.json` → `test_modules.py --target P --json`
  - 两套发现口径（unittest discover 与 run_tests.py rglob）用例数必须相同

### 规模

- **S1 大项目账本体积 / 历史事件 / DOM 超预算**（已覆盖）：`scale_budget.py --target P --json --check` → `scale_probe.py --mods 50 --caps 20 --files 1500 --json` → `file_layout.py --diff --target P --strict`
  - 基准：1000 能力 / 1500 文件 / 80 事件 → 生成器 4.4s，账本 9.6 MiB，治理文件仍为 4
- **S2 生成器全量重算的成本**（部分）：`scale_probe.py --json` → `scale_budget.py --target P --check`
  - 残差：生成器按能力逐个扫 docs / tests，接近 O(能力 × 文件)，没有增量索引；触发升级条件：超过 1 万能力或 2 万文件且门禁耗时不可接受时，再引入缓存/分片，同时必须保持同一份账本可复算

### 视图

- **V1 模块 / 组件上看不到 TODO 与 issue**（已覆盖）：`work_panel.py --target P add --kind todo --scope DEMO.CORE.ORDER.01 ...` → `work_panel.py --target P nodes --json` → `看板 → 能力地图 / 工作项`
  - 派生聚合不落盘，避免产生第三份需要同步的事实
- **V2 手填测试结果投影伪造全绿**（已覆盖）：`work_panel.py --target P sync-tests --apply --approved-by <人>` → `verify_ledger.py --root P --strict --json`
  - 投影不含 generated_at / raw_tail，保证确定性；原始报告仍是唯一测试事实
- **V3 新项目尚无工作态数据**（已覆盖）：`init_project.py --target P --mode greenfield` → `看板 → 工作台` → `verify_ledger.py --root P --strict`
  - 空数组与缺失字段都按零处理；M8 只新增字段，不改 entries / history

## 公理索引

- **A1** 状态完备：在哪 / 去哪 / 谁在改 / 凭什么 / 谁批准（9 个场景）
- **A2** 证据有效：结论来自可复算证据，且对当前源码有效（13 个场景）
- **A3** 单点写入：同一事实只有一个写入点（8 个场景）
- **A4** 时间可逆：历史不可篡改，能检测并发覆盖与中断（8 个场景）
- **A5** 未知即停止：版本 / 路径 / 完整性存疑时 fail-closed（14 个场景）
- **A6** 边界闭合：进入 / 冻结 / 归档 / 退役 / 失效都有出口（8 个场景）
