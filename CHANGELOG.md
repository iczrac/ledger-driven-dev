# Changelog

本项目版本遵循语义化版本（SemVer）。

## [2.24.0] - 2026-11-24

**第一性原理**：文档的信任只能由可复算的指纹、登记与人工签名派生；事实源只有账本与 registry，任何"看起来绿了"的批量标记都是伪造信任。派生文档只允许由事实源重算，不允许手改；规划图只允许来自人的声明，不允许拿账本现状投影自证。

**对外宣称澄清（不改写历史条目）**：v2.22.0 的 CHANGELOG 写了"修订 doc-rebuild（PROJECT_STATE + `--check`）"与"ledger-guard 串起 doc lint 与义务门禁"，实测当时只改了技能文案，代码没有落地——`rebuild_docs.py` 中 `PROJECT_STATE` 出现 0 次，`check.sh` 无文档节，`scripts/` 与 `.github/` 中除 `doc_lifecycle.py` 自身外无调用点。本版把两处承诺真正实装，并补上可复现的负向测试。

- 复现判定：孤岛调用点 = 已证实；`check.sh` 无文档节 = 已证实；`PROJECT_STATE` 缺失与 41 篇全 orphan = 已证实；"verify_ledger 无文档类判据" = 部分成立（有一条 `doc_paths_exist`，校验能力 `doc_index` 路径，非文档生命周期信任判据）。
- 工作流 A：`scripts/check.sh` 新增「文档生命周期（shadow）」节，输出 orphan / suspect / stale / 信任告警 / 派生漂移的数量与具体文件清单；默认退出码 0，仅 `--strict` 阻断；收尾汇总由 16 节增至 17 节。`doc_lifecycle.py` 新增 `gate` 子命令；`skills/ledger-verify` 的五条文档不变量逐条标注实现来源；升硬门条件写为"连续 10 次 CI orphan=0 且 warn=0 + 人工批准"。
- 工作流 B：`scripts/rebuild_docs.py` 真正生成 `docs/generated/PROJECT_STATE.md`（能力等级/证据分层、待复核与过期文档、`next_queue` 前 5 条、最近变更），全部取自账本与 `docs.registry`；新增 `--check` 只读比对，手改即点名文件并返回非 0；生成物无时间戳，连续两次逐字节相同；账本为空时给 fail-closed 提示而不崩。`scripts/file_layout.py` 纳入单一事实源并重新渲染 `FILE_LAYOUT.md`，README / STANDARD / 08 / 10 / 15 / 28 同步。
- 工作流 C：`doc_lifecycle.py` 新增 `seed`（确定性初判：generated→derived、plans/计划→plan、编号文档/STANDARD→rationale；`covers` 从正文能力码与决策 id 抽取；全部 `status=draft`、`verified` 为空）与 `approve`（无签名或无可复算 `source_hash` 一律拒绝升 current）；登记写入 `governance/DECISION_LEDGER.json#docs.registry`，并追加 ledger-steward 历史事件，未新建第二登记表。自身仓 42 篇（原 41 + PROJECT_STATE）全部登记，lint orphan 归零、draft=42、verified=0。
- 工作流 D：README / STANDARD / 08 / 10 的专家、技能、路径与字段计数改为从代码派生；`literal_drift` 0 漂移；单测 523 → 535（只增不减，新增 12 条覆盖门禁 warn/strict、幂等、手改、播种、无签名拒绝、E1/E2）。
- 工作流 E1：`compare_graphs.py` 取消"未声明目标默认 L5"，新增 `no_target`，不参与对齐与完成度；回测：自身仓 16 条 `in_progress` → 16 条 `no_target`，`in_progress=0`。E2：规划码唯一来源改为 registry 人工声明（`committed` / `target_level` / `depends_on`），CAPABILITY_INDEX 仅作现状投影；自身仓声明一条未实现能力后 `planned=17 / actual=16 / planned_only=1`，不再恒等。
- 实测代价：`check.sh` 增加一节（16→17），单测多 12 条；`PROJECT_STATE.md` 的"最近变更"排除文档登记记账事件，避免与 registry 自指漂移；`method_assets=9873b08f850e7c77…`、`installed_assets=648c282a990b1a77…`、`ontology=beb2146190093602…`，按 M4/M5/M7 重绑，目标项目需重新批准升级。

## [2.23.0] - 2026-11-24

**docs 文件架构规范化**：三类分层不动，修四处口径漂移，索引与权威源对齐。

- 独立复现：编号文档 01–36 连续无缺口；三层物理隔离（人工编号文档 / STANDARD / generated 派生）已规范化，不动。发现四处真实漂移：`scaffold` 示例用单数 `docs/plan/`（与 `file_layout` 的 `docs/plans/` 冲突）、STANDARD 第六节混列双作用域 generated、file_layout 与 `15-文件架构` 残留 `docs/01-21`、README 人工索引漏列 9 篇且计数过时。
- 修复：`doc_lifecycle.py` 路径统一 `docs/plans/`；STANDARD 第六节改为双作用域表（目标项目 4 份 / 方法仓自身 5 份 + 指向 FILE_LAYOUT 权威清单）；file_layout 与 15 改为 `docs/NN-方法论文档`；README 补列 24–29/34–36 并从代码派生修正技能 24/专家 9 计数。
- 权威链：`METHOD_VERSION=2.23.0`，`upgrade plan`（M4/M5，无 blocks）→ `apply --approved-by user-approved-v2.23.0` → `verify` 全 pass → `plan` noop；ontology 投影按 `ontology.py build --apply` 重建并绑 1aa0f02348e0178b。
- 资产：`method_assets=71dc5673ccd5b50e`、`installed_assets=3ae603cad0acad77`；method_docs 36 篇不变；新增 `tests/meta/test_doc_architecture.py`（6 用例：编号连续/三层隔离/双作用域/路径口径/01-21 残留/README 覆盖）；单测 517→523。
- 边界：不新增第 10 专家、不改 feedback/、不加依赖、不放宽判据；不重构已规范化的编号与分层。

## [2.22.0] - 2026-11-24

**文档生命周期维度**：路由、六份专家契约与技能三层同步补齐，文档从"人肉同步"升为可复算的裁决对象。

- 独立复现：三条文档意图（整理过期文档 / 规范化补过期标记 / 文档与代码对不上）实测全部 `intents=[]` 并触发澄清，兜底落到 `ledger-steward`（low），并非任务书推测的 plan/verify。意图表实为 13 类（非 14），`doc-rebuild` 技能 triggers 认文档但路由表不认——不一致已证实。
- 工作流 A：`INTENT_PATTERNS` 新增 `doc` 类（中英文触发词 22 条）；冲突唯一负责人规则——doc+code 判 `ledger-steward`（唯一写入方 + 交接链），doc+verify 判 `evidence-auditor`（只读审计优先，不得写文档），三者并存触发澄清 fail-closed；`FOLLOW_UP["doc"]`、`HANDOFF_CHAIN["doc"]`、`intent_restate.VALID_INTENTS/SCOPES` 同步。
- 工作流 B：六份专家契约原地修订（不新增第 10 位专家），每份写清职责边界/允许/禁止/停止/交接；文档写权互斥——`docs.registry` / `docs.obligations` 仅 `ledger-steward`，`docs/**` 正文仅 `loop-executor`，草稿仅 `project-archaeologist`，`evidence-auditor` / `release-steward` / `goal-orchestrator` 只读。
- 工作流 C：新增 `doc-lifecycle` 技能（scaffold / lint / mark-stale / clear-suspect / check），骨架含 `<!-- 待人工填写 -->` 必判 incomplete，不自动写"为什么"正文，不绕过账本改 ledger；修订 `doc-rebuild`（PROJECT_STATE + `--check` + 派生文档禁止手改）、`ledger-verify`（五项文档不变量先 shadow）、`ledger-guard`（串起 doc lint 与义务门禁）、`graph-compare`（可执行规则断言 + suspect + 旧集合差保留 shadow 一版）。
- 五项文档不变量（覆盖完整 / 派生可复算 / 信任一致 / 义务已声明 / 无孤儿）先 shadow：只告警不改状态，升硬门须人批准。
- `doc-lifecycle check` 的 stale 判据为 shadow 只读投影：读 `docs.registry` 的 `stale_after`，过期且未复核即报 issue（含具体文件与原因），不写账本状态；独立复现确认此前仅有文档承诺、代码未实现，已 TDD 补齐。
- 资产：专家契约 6 改 / 技能 23→24（+1 改 4）/ 已安装资产 32→33；`method_assets=5a7a02203d937fb8`、`installed_assets=3ae603cad0acad77`；已按官方升级执行 M4/M5/M7 重绑，目标项目需重新批准安装才能使用新副本。
- 实测：单测 495 → 517（+22：doc 路由 8 / 契约互斥 7 / 技能纪律 7，含骨架不可信与 stale 过期两项负向）；`feedback/` 未改，未加第三方依赖。

## [2.21.0] - 2026-11-24

**目标架构对账链可信度收口**：四项缺口先独立复现再分笔修复；规划图不再拿讲解示例当目标，规划图缺失不再反向假警，同层顺序与同义异码只晒不裁决。

- 第一性原理：`compare_graphs.py` 的结论要能回答「图纸是否可信」。若规划码混入文档示例、规划图为空却给出确定 diff、开发顺序靠字典序、同义异码被当成两个能力，那么报告越漂亮越是在制造假绿灯。修法是「权威源唯一、缺证据就声明不可采信、不确定只给 shadow、不改 status/level」。
- C（部分成立，commit `f702cad`）：`build()` 输出 `plan_status=absent|empty|partial|present`；规划图缺失/为空/部分时给 warning，报告首行明确「漂移结论不可采信」；`execution_order` 的权威指向 `architect_from_docs.py`，不再让读者误以为是比对器现场算出的顺序。
- B（已证实，commit `ec94fdc`）：规划码唯一来源改为 `CAPABILITY_INDEX.md`（账本确定性投影）；其他手写文档里的四段码只增强 `target_level` / `depends_on`，`MODULE_MAP` 保持 codec fail-closed。实测此前 21 个规划码混入 5 个示例码（23.8%：`DEMO.*` / `MYPROJ.*` / `X1`），改为唯一来源后规划码 16 个全为 `METHOD.*`，污染归零。
- A（部分成立，commit `579ac0c`）：`depends_on` 同层稳定拓扑排序，环检测写入 `dep_cycles` 作 shadow warning；稀疏/全空依赖退化为原 `next_queue` 顺序，不改能力等级与证据。
- D（部分成立，commit `4338a7d`）：`impl_hint` 与实际 `artifact_paths()` 按路径末 3 段归一化；同模块且实现相同或交集写双向 `alias_matches`，进入 `shadow_pairs(kind=alias_suspect)`；不改 `status` / `level`，不自动合并同义码。
- 技能权威源：17 份 `SKILL.md` 补「执行语境（先读）」，目标项目内不要照抄 `scripts/xxx.py`，统一走单一入口；消除文档里的断链路径。
- 文档：`docs/13-可追溯性.md` 同步四项权威口径与实测代价；`tests/MODULES.json` 与 `docs/generated/TEST_MODULES.md` 随新增 4 个测试模块同步。
- 实测代价：单测 476 → 495（+19）；`method_assets=476fb36e597eb6866`、`installed_assets=a344b3e9c84d3494`、`ontology_digest=137fb6cdab5b7b80f`；`feedback/` 未改。
- 边界：本版只改判定与报告口径，不改账本事实、不改能力等级；主仓推广与账本重绑须单独批准，不随本版自动生效。

## [2.20.1] - 2026-11-23

**结构化暂停范围**：让人工裁决的“暂停”真正约束 `next_queue`。

- 第一性原理：`next_queue` 是唯一入口；若裁决已写“HELM 暂停，不补测试刷分”，队列仍把 HELM 排在前两位，那么执行者按队列干活就是在制造假绿灯。问题不在人不守纪律，而在裁决与投影之间没有机器可消费的契约。
- 实现：`entries[].paused_scopes` 成为唯一结构化暂停字段；只认 `status=done` 且未被 `superseded_by` 取代的条目，按 project code 整段排除。生成器不解析散文里的“暂停”，字段缺失的历史账本保持原顺序，避免从文字猜测造成误排除。
- 影响：`diff_queue_risk` 现在同时校验队列成员与风险注解；暂停导致成员缺失也算可复算漂移，不能靠手删账本条目绕过。
- 文档：`docs/05-循环协议.md` 补充 SELECT 的暂停规则；模板与示例工具副本同步。
- 边界：本版只提供机制，不替任何项目写入 `paused_scopes`；把既有裁决结构化和重绑账本仍需在目标项目单独批准执行。
- 实测代价：单测 473 → 476（+3）；权威模板、示例副本与方法仓自举账本同步。

## [2.20.0] - 2026-11-23

**四项疑似缺陷独立核实后的证据口径收口**：先复现再判定，按判定分四处落地，不把“看起来像 bug”直接当 bug 修。

- 第一性原理：本项目的承诺是“完成度不是写出来的，是从证据里算出来的”。四组现象的共同根因都是**权威源与消费端断开**：草稿码绕开 codec、测试报告不绑定源码、文档抽码另起规则、人写数字不回读校验器。因此修法是“权威处严格、比对处可解释、计数只从代码派生”，不放宽既有判据。
- A（部分成立，commit `ad13c5d`）：`discover_project.sanitize_code` 收敛段内非字母数字字符，`init_project.py` 在 adopt 落盘前用唯一 codec 校验草稿；非法码返回 2 并报出草稿文件、原码、建议码与“四段式”口径。声称的“必须人工精简草稿”属既定设计，未采纳。
- B（部分成立，commit `8c0bc62`）：`run_tests.py --source-dir` 把被测源码纳入 `evidence_binding.inputs`；README 改为按绑定内容陈述承诺，缺省仍只绑测试文件，避免改变既有 38 文件口径。实测仅改源码即触发 `changed:ledger_feedback.py`，verified 回落 declared。
- C（部分成立，commit `8abd095`）：反向双报复现；畸形码并非“静默接受后落盘失败”，而是被宽松抽码静默丢弃或触发空列 unpack 崩溃。`trace_common` 统一候选扫描与四段式归一，`architect_from_docs.py` 对非法码 fail-closed 并给出文件/行号/合法写法，空能力列回退到已抽编码；`compare_graphs.py` 新增 `shadow_pairs` / `shadow_match`，同义异码仍保留 planned_only / actual_only 与专家口径，只加“疑似同一能力”提示，不自动合并。发布前完善：`shadow_pairs` 全量对进 JSON、人读报告单列小节，warnings 仅显示前 5 组并指向 JSON，避免大批量同义异码淹没摘要。
- D（已证实，commit `494f62d`）：README 7 处写 30 条，而 `verify_ledger.py` 的 `add()` 去重后是 31 条；`literal_drift` 因词表不认“条”且 expect 无该键而漏检。现在 `expect.invariants` 由该文件的 AST 派生，词表纳入“条”但排除“第 N 条”序号与小于 20 的子集计数。新旧门禁对齐后共修正 52 处字面量（含 README 7 处与首次暴露的 24/26/27/30 条历史口径），派生文档由既有生成器重算；最终扫描 108 文件、0 漂移、10 处历史复核。`feedback/` 未改。
- 实测代价：单测 461 → 473（+12），发布前门禁内单测 473/473 passed、耗时约 220 秒；版本重绑按官方升级流程执行 M3/M4/M5/M7 与一次同版 M5 增量重绑，`method_assets` / `installed_assets` / `ontology_digest` 最终为 `5c1e275a20b4e337` / `145683f532bc89ab` / `72b9e5bb96da3ad0`，自举账本与看板 EMBED 同步。全量门禁 16 阶段全绿；`feedback/` 未改，`feedback_closed = 7`。

## [2.19.0] - 2026-11-22

**风险下降判据与关闭回路**：把「信号变旧」「风险下降」「人工裁决关闭」三件事分开。

- 新增 `docs/36-风险下降判据.md`：severity 与 freshness 正交；风险下降须同主体、同口径、
  方向改善且持续，并最终由 operator 写入显式关闭决策。衰减、跨母体、单点、猜指标一律 fail-closed。
- `runtime_signals.py` 新增 `extract_metric_trend` / `risk_outcome` / `signal_disposition`：
  只读对照客观指标方向与衰减方向（`divergent/aligned/n/a`），并从账本决策判定关闭状态。
- 关闭判据复用既有决策 schema（evidence 锚点 + 有效 status + 显式关闭意图），
  「引用但不关警报」正确判 `open`；观察器永不自动关闭。
- 测试 446→461；真实事件实证异口径链与单点值均拒绝；方法仓与目标仓的纯函数逐字节一致。

## [2.18.0] - 2026-11-22

**投影新鲜度可见化**：陈旧信号不能再伪装成风险下降。

- 新增 `signal_age_days` / `decay_factor`：显式 `as_of` 才启用线性衰减，7 天过期出队；
  无时间 / 不可解析 / 过期一律 fail-closed。
- `project_signals(..., as_of=...)` 输出 `observed_at / age_days / decay_factor` 使投影可复算；
  不传 `as_of` 保持既有形状。
- 目标仓投影工具 `--apply` 缺 `--as-of` 直接 BLOCK；新增只读反馈报告说明「衰减只表示信号变旧」。

## [2.17.0] - 2026-11-21

**运行时映射 fail-closed**：operator 警报不得变成补证据任务。

- `project_signals` 过滤 `alert-operator` 类信号；COVERAGE 别名移除裸 `coverage/frontier` 字面词，
  防止按文件名把运行时缺陷误挂到无关能力点。
- 补两条回归测试；重建投影后两条 operator 信号从 `next_queue` 撤回，记为显式 open 警报。

## [2.16.0] - 2026-11-21

**投影新鲜度不变量**：健康度明细不能再落后于测试证据。

- 新增第 31 条不变量 `analytics_test_results_detail_valid`：从 `test_results.cases` 实算 pass/total，核对 `summary` 与 `test_pass_rate.detail`，不一致即 fail-closed。
- 修正 v2.15.0 遗留的明细陈旧：437/437 报告下健康明细仍写 418/418；本版按权威口径重算。
- 第 31 条归入已有分析层能力 `METHOD.GOV.ANALYTICS.14`；新增 `docs/35-投影新鲜度不变量.md`，验证器三份副本同步。

## [2.15.0] - 2026-11-21

**运行时风险入口**：让 `next_queue` 既能回答“缺什么证据”，也能回答“现场正发生什么”。

- 新增 `scripts/runtime_signals.py`：从 `STATE/events/*.md` 解析 `## E<n>` 事件块，产出带 `source_file / id / confidence` 的可追溯信号；unknown 与无域命中 fail-closed。
- Slice 1 域级重排：在内存副本按 `(-risk, completion, code)` 抬高风险域，不写盘、不改等级/证据。
- Slice 2 精确映射 + 生成器接入：`capability_hits / project_signals / apply_risk_signals_exact` 按显式 code → 完整 code → 语义词表映射能力点，歧义即丢弃；`build_capability_model.py --runtime-signals` 只在命中时注入 `risk_score / risk_signal / risk_evidence`，`--check` 同步检查风险漂移。
- 真实只读取证：17 个事件块 → 3 条精确投影；队列头号任务由“补证据”转为带原文可追溯的运行时风险点，原 rank1 降 rank3。收紧泛词「覆蓋」后，非审计事件不再误伤。
- 新增能力点 `METHOD.GOV.RUNTIME.16`、`docs/34-运行时风险入口.md`、两份脱敏取证报告；测试 418→437，方法版本升至 2.15.0。

## [2.14.0] - 2026-11-21

**推广探路驱动的目标编排加固**：让循环能表达治理目标、能识别空转、能在验证门 fail-closed。

- `goal_ledger` 新增 `method_version`（语义版本比较）与 `level_progress`（能力等级相对基线提升）两个判据指标，含参数校验与未知 op 一律 false 的 fail-closed 语义。
- `goal_loop` 新增进展指纹（任务 + 相关能力等级 + 方法版本）与 `stall_limit`（默认 2）：连续无进展即 `stagnated` 暂停并给四要素结构化提议，不再烧满 `max_loops` 后才失活；新增 `--stall-limit` CLI。
- 第 30 条不变量扩展：账本侧拒绝非法新判据（未知 metric / 非法版本 / 缺 baseline）；单测新增 9 例。
- 取证报告 `feedback/GOAL-PROMOTE-DRYRUN.md`：在干净 clone 上以 v2.13 验证器复跑推广目标，发现旧账本 43 处 `unbound_verified` 脏数据在验证门被正确拦下（报告初写 5 处系验证器只打印前 5 个）——推广的第一道门是账本合规，不是目标循环。人批准后按可复算路径在 clone 修复全部 43 处（bound 29 保 verified / 其余 14 降 declared + 派生 issue），验证门升至 30/30 全绿，复跑正确触发 `stagnated`。

## [2.13.0] - 2026-11-20

**目标编排监督者**：在授权预算内对单一目标做受控自动循环，方向锁定、人批准调整。

- 账本新增 `goals/1`：目标对象、方向锁 `sha256(description+success_criteria)`、机读成功判据、`max_loops/current_loop` 预算、状态机与逐动作审计。
- 新增 `goal-orchestrator` 专家与 `goal-orchestrate` 技能：只读监督者，不直接写事实源。
- `agent_gateway` 新增 `goal-create/propose/approve/reject/advance/achieve/deactivate/pause/resume`；create/approve/reject 必须人 `--approved-by`，其余由预算授权但仍走统一审计。
- 新增 `scripts/goal_loop.py`：默认 dry-run，每轮重路由 → 队列 → expert-run 计划 → verify_ledger → 方向检查 → 推进 → 判据评估；超预算 `deactivated`，达标 `achieved`，输出结构化轨迹与待批准命令。
- 路由新增 `goal` 意图高置信指向 goal-orchestrator；第 30 条不变量 `goal_loop_valid` 守护方向锁与终态纪律；升级 M9 初始化 goals 字段。

## [2.12.0] - 2026-11-20

**本地 D3 离线交互**：在不联网、不引后端、不改事实源的前提下，让看板能追、能试。

- 引入本地 `templates/vendor/d3.v7.min.js`（v7.9.0），模板以相对路径加载；缺失时三个视图自动回退原生 SVG / DOM。
- Python 新增 `analytics.timeline` 与 `analytics.lineage`（`trace-lineage/1`）：趋势横轴摘要与“能力→决策→证据→状态”树，全部只读派生。
- D3 强化能力热力图与成熟度趋势，并新增可展开/收合的“追溯链”视图；点击节点钻取证据。
- What-if 同步更新趋势末点、追溯状态节点和变更高亮，仍只改 `VIEW_DATA` 内存副本。
- 新增第 29 条不变量 `analytics_d3_projection_valid`、能力点 `METHOD.GOV.D3.15`、决策 `D-009` 与 `docs/32-本地D3可视化.md`。

## [2.11.0] - 2026-11-20

**可视化分析层**：把账本数字翻译成可判断的热力图、趋势、证据链与 What-if。

- Python 生成层新增 `analytics`：能力点 L0–L5 时间序列、与前一快照的差异摘要、健康度五维、推荐行动与健康增益；`next_queue` 卡片带 `health_impact`。
- 看板新增「能力热力图 / 成熟度趋势 / 任务卡片墙」三个视图，原有 `data-v` 全部保留；工作台补五维健康度进度条。
- 热力图、趋势图、卡片墙共用证据链钻取面板；`localStorage` 标记自上次查看以来变化的能力点与工作项。
- What-if 只在内存副本中试算，不写账本、不改不变量；Python 与前端共用同一组健康度权重。
- 新增第 28 条不变量 `analytics_maturity_valid` 与能力点 `METHOD.GOV.ANALYTICS.14`；新增 `docs/31-可视化分析层.md`。

## [2.10.0] - 2026-11-20

**工作台视角**：突破「账本列表 + 一堆标签」的原框架，默认落点改为工作台。

- 打开先看「今日焦点」：阻塞 / 失败用例 / 证据待补三张结论卡，各自带处理入口。
- 新增可信度条：证据新鲜度、verified 覆盖、完成度、报告绑定、数据来源徽标第一眼可见。
- 新增入口矩阵：把工作项 / 架构图 / 数据流 / 能力地图 / 术语 / 设计理念收成可下钻卡片。
- 下一轮队列从 SELECT 缺口派生，焦点工作项按阻塞优先；搜索现在能过滤工作台与图形节点（命中高亮）。
- 图形区支持窄屏横向滚动；上下文与页脚标明数据来自内嵌快照还是实时 JSON。
- 新能力点 `METHOD.GOV.WORKBENCH.13`，能力模型 12→13；单测 381；修复升级器把 2.10.0 当旧版本比较的语义版本缺陷；主项目推广仍待确认。

## [2.9.0] - 2026-11-20

**架构图与数据流**：把「为什么这样设计」和「数据怎么流」做成可下钻的看板投影。

- 新增「设计理念」视图：七条原则，每条含为什么 / 界面落点 / 反例；上下文条可一键进入。
- 新增「架构图」视图：权威源 → 生成器 → 投影 → 视图四层 SVG，节点带实时计数并可点击/键盘下钻。
- 新增「数据流」视图：声明链、写入链、本体链三条链路；每条边标注当前账本规模，数字来自 `DATA` / `ONTO_TERMS`。
- 导航降噪：首屏 7 个高频入口，其余收进「更多视图」；跳进隐藏视图时自动展开。
- 新能力点 `METHOD.GOV.VISUAL.12`，能力模型 11→12；单测 379；守门测试先红后绿。
- 图形与理念都是投影，不新增账本字段、不复制第二事实源；主项目推广仍待确认。

## [2.8.0] - 2026-11-20

**看板体验**：只改呈现层，不新增账本字段、不改判定规则、不复制第二事实源。

- 权威模板新增语义结构（skip link / nav / main / footer）、粘性导航、当前视图上下文条；
  搜索词与钻取作用域以可移除 chip 显示，统计卡可直接跳转到对应视图。
- 搜索框加清除按钮，`/` 聚焦、`Esc` 清除；展开/收起带状态与 `aria-expanded`；
  小屏两列、减少动态效果、打印样式。视图元信息由 `VIEW_META` 描述，不存账本事实。
- 新契约测试 `tests/views/test_board_views.py::test_board_ux_contract` 先红后绿；
  能力模型 10→11（10 verified + 1 declared，BINDING.07 负向探针保留）；
  单测 378。看板骨架由 `board_contract.normalize` 带批准人归一化到方法仓与示例。
- 方法仓账本补录 D-005 发版决策，`METHOD_VERSION` 2.7.0→2.8.0；主项目推广仍待确认。

## [2.7.0] - 2026-11-20

**真实自举 + 看板接本体**：修复「方法论仓库不用自己的账本开发自己」的断链，
让账本重新等于真实开发历史；看板术语视图从纯硬编码改为消费本体投影。

**A · 自举闭环**：
- 方法仓账本此前停在 v2.3.0、无 `governance_meta`（从未走过 M1-M8）。
  本版补齐版本轴绑定字段：`method_version=2.7.0` / `method_assets` / `board_skeleton` /
  `installed_assets` / `ontology_digest`，全部由 upgrade apply 生成（带批准人）。
- 补录 v2.4.0 / v2.5.0 / v2.6.0 三条实际已发生的发版决策（status=done，
  证据指向真实 CHANGELOG / 交付卡 / 实现脚本），走 `ledger_io.write_ledger`
  唯一写入口，看板 EMBED 同步。
- 三个新元工具登记为方法仓能力点（`METHOD.GOV.RESTATE.08` / `ORCH.09` /
  `ANNOT.10`），测试静态 import 实现可 bound；能力模型 7→10，
  9 verified + 1 declared（BINDING.07 负向探针诚实保留），
  `账本=f(registry,仓库,报告)` 逐字段可复算。
- 新增 `tests/meta/test_dogfood.py` 守门测试（6 条），先红后绿锁定自举状态。

**B · 看板术语接本体**：
- 权威模板新增第二个数据段 `ONTO_TERMS`（与 EMBED 同范式）：由
  `board_contract.normalize` 从 `docs/generated/ONTOLOGY.json` 注入 11 条
  `ubiquitous_language`，骨架摘要归一化该段以保持稳定。
- 「术语与实现」视图新增「本体投影词表」区（标注机器派生来源），
  与原 21 条概念解说、6 条思路、7 条实现并列——两类术语语义层次不同，
  不相互替代。`ledger_io.sync_board` 只管 EMBED，不触碰本体段，无写入冲突。
- 方法仓 + 示例看板骨架统一归一（digest `ba37cd40…`），M6 迁移推送。

无新治理不变量、无新账本字段；本体投影与来源投影范式不变。
全量门禁 EXIT=0、377 单测、27 不变量绿。

## [2.6.0] - 2026-11-20

**来源投影与完成定义**：借鉴外部方法论「让 AI 产出与人确认可区分」的思路，
但**不往账本加字段**——issue 早有 `source=derived`/`derived_from`（机器控制）与
`owner`/`owner_note`/`detail`（人补、重算保留），decision 早有 `status: proposed→done`。
再加 `origin` 字段就是同一事实两处表达，违背单一事实源。

- `provenance_view.py`（新增只读投影脚本，进 scripts 摘要但不进治理工具副本）：
  `projection = f(账本)`，把 issue/decision 既有字段按 `[AI推断]`（勿手改）/
  `[人确认]`（人补）白名单分组；从任务卡 `target_level`+`missing_evidence`
  派生 `definition_of_done`（含 `verified⟺bound` 达标条件与可运行复验命令）。
  不写回账本、不改 27 不变量、不参与写入链——P2「不改治理规则」由此保证。
- 黄金范例 `examples/golden-walkthrough/`（可运行、可复算、零写盘）：六步串起
  复述门→路由→编排→批准包→来源投影→完成定义；演示 fail-closed 对照。
  放在 examples 不进资产摘要，不触发额外整包安装。
- 新文档 `docs/26-来源投影与完成定义`；10 条单测（先红后绿）；版本 2.5.0→2.6.0。
- 七模型 YAML / 8 段硬暂停 / code-paas 一律不引入。

## [2.5.0] - 2026-11-20

**专家团自动编排：把路由链变成可执行分工 + 人工批准包**。P0 先修路由，
P1 再让「链 → 行动」落地——目标是尽量全 AI 驱动，但保留人必须保留的批准点。

**P0 · 路由修复**（不新增资产）
- 未识别的非空指令 → `needs_clarification`，点名 `intent.json` 复述路径，
  `confidence` 诚实降为 `low`；空意图仍按现状默认路由，向后兼容。
- `route` 意图恢复为合法强候选，由 `expert-router` 承接（只读、不写入），
  并补齐其专属只读命令集（原落到默认 `--help`）。
- `route.handoff.chain` 新增多跳交接链（3 跳，确定性），为编排器铺路。

**P1 · expert-run 编排器**（新元工具 + 新技能，触发整包升级）
- `expert_run.py`（新增，不进治理工具副本）：沿交接链展开逐跳专家契约
  （skills/writes/EXPERT.md）+ 命令分类（readonly/approval/manual）+ 人工批准包。
  **零新判定权**：负责人/链/命令全部来自 `route_expert` 与 `EXPERT_CARDS`；
  **默认 dry-run 零执行**：不跑命令、不写文件、不碰账本；
  **fail-closed**：路由未通过时 chain 与批准包为空，只给 halt_reason。
  结论 `run = f(intent, target, route_expert, EXPERT_CARDS, commands_for)` 可复算。
- 新技能 `expert-run`（21→22）+ `docs/25-专家团自动编排` + 11 条单测（先红后绿）。
- 命令分类保守：写授权标志压过只读标志，内联 `python3 -c` 归 manual，
  宁可归 approval 不误判 readonly；批准包命令透传真实 target，复制即可执行。

## [2.4.0] - 2026-11-20

**复述门：让意图被听懂之后再路由**。v2.3.0 建立专家团闭环后暴露一个真实的洞：
`route_expert.py` 面对「让专家团接管全流程」这类编排元指令返回 `intents=[]`，
照常路由——意图没被听懂，机器却往下走了。本版在路由之前补一道只读门禁。

- `intent_restate.py`（新增元工具，不进治理工具副本）：把人话变成结构化
  `intent.json`（意图/能力 code/写入范围/开放问题），再用真实 registry 与
  账本机器校验。8 道校验延续 v2.2.0「声明权 ≠ 伪造权」：防幻觉能力码、
  只读意图越权写入、多意图竞争、元指令未披露都会被拦。结论三态
  `allow / need_clarification / reject`（退出码 0/1/2），`结论 = f(声明, registry, 账本)`
  可复算、只读、零第三方依赖。
- `route_expert.py` 接入前置：新增 `--intent-file`，提供时先跑复述门，非 allow
  即 `route.blocked=true` 并把 `fix` 并入 `needs_clarification`；不提供时行为
  与旧版完全一致（向后兼容）。
- 新增技能 `intent-restate` 与 [24-复述门](docs/24-复述门.md)；更新 README /
  10-AI集成 / 12-专家路由 / 19-专家与技能可用的技能数与引用。
- 11 条单元测试（routing 模块）全绿；原型阶段经 10 个边界样本压测，先红后绿
  修掉「只读越权写入」与「多意图竞争」两个真实漏洞。
- **评估并否决图形化检查方案**：外部图形建模 prompt 规范零代码、不可机读，
  违背可复算，不纳入资产，只作给人看的展示投影参考。

## [2.3.0] - 2026-11-20

**派生 issue 闭环 + 方法仓自举**。v2.2.0 让 `verified⟺bound`，14 个能力诚实
降级——但只报警不闭环的红灯会退化成红灯疲劳。本版把「非 bound 能力」自动
投影成可认领的 issue，并让方法仓先用这套门禁治理自己（dogfood），验证可靠
后再推广到真实项目。

- `derived_issues.py`（新增工具副本，工具数 5→6）：`issue_set = h(binding_status)`。
  每个非 bound 能力恰好一条 `source=derived` 的 issue，固定 id、机器控制
  status/severity/close_condition，人工 owner/owner_note/detail 一律保留；
  能力转 bound 自动关单并写依据。`close_condition.kind` 复用 `capability_verified`
  （v2.2.0 起等价 bound），不新增关单语义。
- 不变量 #27 `binding_issues_derived`（26→27）：非 bound 缺 issue、或已 bound
  仍 open，均 fail；旧账本无 binding_status 时 na。
- 生成器 `--check` 覆盖派生 issue：手删/篡改 issue 报漂移，可复算判据扩展为
  「账本 = f(registry, 仓库, 报告)」含 issue 投影。
- **方法仓自举**：`governance/` 落地方法仓自身（6 个主链脚本为能力点），
  同一套绑定门禁、派生 issue、27 不变量先作用于方法仓自己。
- 配套：init_project / upgrade TOOLING / scale_probe / check.sh / file_layout /
  method_assets / 测试清单同步登记第 6 个工具副本；ontology 重建。

## [2.2.0] - 2026-11-19

**绑定硬门禁：verified ⟺ bound**。v2.1.2 把「声明的测试是否真测到实现」以
shadow advisory 晒了半个月，证明判据判得对（10 个 unbound 能力全库零测试
触达实现）；本版把它升为硬门禁，堵死**「声明权 = 伪造权」**——v2.1.x 只要
往 `caps[].tests` 塞任意一条 pass 测试路径就能把能力刷成 verified。

- `judge_tier(unit_tests, report, binding_status)`：`verified` 改双条件，
  必须有报告 pass **且** 符号绑定 `bound`；via1/unbound/no_impl/no_tests
  一律降 declared（via1 隔一层编排不算直接证明）；
- 新 `binding_status_of_tests()` 从 `binding_advisory.py` 抽出，生成器在
  `build()` 内基于**实际证据**（`ev["unit_test"]` + `ev["impl"]`）计算，
  不是 registry 原始声明（demo 用 hints 派生，两者不同源）；`binding_status`
  写进账本 cnode；
- 第 7 条不变量 `verified_tier_traceable` 扩展：verified 必须带
  `binding_status=bound`，手改 tier 或抹字段都会被抓（2 条负向用例）；
- 4 条 judge_tier 负向用例（unbound/no_impl/via1 拒绝、bound 放行）+ 2 条
  防篡改用例，构成「伪造通道被堵」的双向证明；
- `EVIDENCE_TIER_SPEC` / docs 03、08、11、23 同步；ontology 派生重建。

主仓预期：verified 43 → 29（恰好等于 bound 数），14 个存疑能力诚实回落
declared。registry 数据未动——不靠改声明把数字做绿，靠机制让数字不可伪造。

## [2.1.2] - 2026-11-19

**证据绑定与资产对账**。v2.1.0 把证据来源钉死在 registry 声明，但留下两个
「写了就信」的死角：声明的测试与声明的实现之间**配对**是否成立，靠文件名
关键词猜；同一份专家/技能资产，安装器与路由器各算各的摘要，后者算完只打印
不对账。本版把两个死角都放到灯下。

### 符号级证据绑定 advisory（shadow 门禁）

- 新增独立模块 `binding_advisory.py`（生成器保持 1439 行，低于 1500
  模块大小硬限；`resolve_declared`/`glob_files` 由生成器注入，避免循环
  import）；`SymbolIndex` 让测试 import 的名字沿 `__init__.py` 再导出链
  解析到定义文件，按项目就近消歧（`projects/<x>` 内不串味）；
- 每次重算输出 `[BIND]` 摘要与逐条 `[UNBOUND]` 告警：bound（直接绑定）/
  via1（经一跳编排层触达，附桥接文件）/ unbound / no_impl / no_tests；
- `--binding-report <path>` 输出机器可读 JSON，供映射修正的人审消费；
- **不改 level / tier、不影响退出码**——判据先在 CI 晒出问题、被证明
  判得对，之后才升级为硬门禁。实测主仓 47 能力：bound 29 / via1 3 /
  unbound 10 / no_impl 1 / no_tests 4。

### 资产摘要统一与对账

- `route_expert.py` 的摘要规范化与 `asset_bundle.py` 的 `sha256-files-v1`
  完全一致（安装前缀 + 按路径排序 + 尾换行）：同一份资产从权威源算与从
  安装副本算得到同一个值；
- `--check-assets` 不再只打印摘要：清单存在时逐文件比对 sha256 + 整包
  摘要对账，任一不符即 fail-closed；无清单时显式 `manifest_checked=false`；
- 负向证明：篡改任一副本一个字节，逐文件与整包同时报警（3 个新用例）。

### 两条新不变量（24 → 26）

- **#25 `work_items_owned`**：未完结（open/doing/blocked）的工作项必须写
  owner（人或专家名），写不出必须写 `owner_note` 说明缺口。AI 不凭空指派
  owner——规矩不是替谁填，而是让缺口可见；
- **#26 `installed_assets_binding`**：`.workbuddy` 只读副本逐文件 sha256
  与 `ASSET_MANIFEST` 一致、整包摘要与账本 `installed_assets.digest` 一致
  （未安装资产时 na）。副本被改、清单过期、账本漂移三者任一即 fail。
  该不变量随 verify_ledger 部署，主仓 CI 与 pre-commit 无需新增步骤。

## [2.1.1] - 2026-11-19

**术语与实现视图**。看板此前有十个视图，全部回答「账本里有什么」；
没有一个视图回答「这套方法论怎么读」。新接手的人看到 D-NNN、verified、
漂移、M1–M8 这些词，只能翻文档逐个查——而文档与页面分离，注定漂移。

本版在看板新增第 11 个视图「术语与实现」，三个分区：

- **专有词汇表 / 术语释义**：20 条核心术语（账本、取代链、registry 声明、
  L2/L3/L5、verified/declared、漂移与 `--check`、可复算、干净检出、
  方法仓、三副本、四层摘要、append-only、fail-closed、专家路由…）；
- **编码思路**：6 条原则——单一事实源、派生优先、证据先于权威、
  两级门禁分工、破坏必经人批准、摘要绑定一切；
- **关键实现解说**：7 个关键件的职责与判定逻辑
  （生成器 / 不变量校验 / 测试报告 / 升级迁移 / 看板契约 / 资产安装与路由 /
  双仓门禁）。

### 纪律

- 内容与仓库实现同源：解说的是**当前实现**，不是愿景；改实现必须同步改模板；
- 视图数据是模板静态内容而非账本数据：术语是方法论事实，对所有项目一致，
  所以放权威模板，随 M6 归一化推送，禁止项目内手改；
- 遵守既有契约：分批走 `PAGE_SIZE`，样式只复用既有类，搜索框可过滤术语，
  视图契约测试同步锁定新锚点；
- 版面文档「十个视图」改为十一个；骨架摘要变更由各项目经 upgrade 重绑。

### 复验

- 模板契约测试新增 4 个锚点断言（`data-v="glossary"` / `renderGlossary` /
  三个内容数组）；
- `check.sh` 全绿（含脱敏：视图内容不含来源项目内部名词）；
- 示例项目看板经 `normalize` 重建，骨架摘要与权威模板一致；
- 目标项目经 `upgrade apply` 重绑后：账本不变量全绿、`--check` 无漂移、
  `upgrade verify` 全过。

## [2.1.0] - 2026-11-19

**声明驱动证据**。v2.0.3 让账本只描述仓库里有的东西；这一版追问下一层：
账本描述的东西，是不是它自己？

v1.8.0 曾让生成器从账本既有 `evidence` 派生 hints，形成
「账本 → hints → 证据 → 账本」的闭环。表面上是省配置，实质是自证。
实测办法很直接：把 47 个能力的 `evidence` 全部抹空再重算——
**20 个 L5 全部塌成 L2，verified 从 20 归零**。那份账本从仓库里重建不出来。

同一次审计还查出三类真实污染：

- **跨项目**：项目根写 `.` 时，`unit_test_dir` 展开成 `projects/*/tests`，
  于是内容项目能力的「摄入/发布决策」拿了 4 个交易项目的决策测试当证据；
- **同形异义**：`security` 同时是「证券池」与「安全边界」，安全边界能力
  因此挂着 3 个证券池测试；
- **宽词碰撞**：`risk` / `portfolio` 让两个不同能力共用同一份四件套，
  其中还混进了部署脚本测试。

### 本版内容

- registry 新增 `caps[].tests` / `caps[].test_records`：精确路径声明，
  逐条校验「存在且已入库」；声明了却找不到的文件按缺失处理并打印 `[WARN]`；
- 删除 `evidence_hints()`：生成器不再回读账本派生证据，`hints` 只来自 registry；
- 测试/记录扫描限制在能力所属项目子树（由 `impl` 前缀推导），杜绝跨项目串味；
- 新增 `--check` 漂移门禁：重算结果与已写账本不一致即 `exit 1` 并打印差异，
  把「账本 = f(registry, 仓库, 报告)」变成可执行判据；
- 新增 `tests/core/test_declared_evidence.py` 5 条负向证明：账本内容不得影响
  派生结果、声明缺失必须降级、扫描不得跨项目、差异比较能发现漂移；
- 目标项目 47 个能力全部改为显式声明：移除 5 条跨项目证据、3 条同形异义证据、
  若干宽词噪声，补入 24 个此前未被匹配的真实测试文件；
- 验收判据 `no_regression_guard` 从「必须有 evidence_hints」改为
  「必须有证据解析入口（`resolve_declared` 或 `evidence_hints`）+ `no_regress`」。

### 结果（目标项目实测）

| 指标 | 2.0.3 | 2.1.0 |
|---|---|---|
| 抹空证据后重算差异 | 20 个 L5 → L2，verified 0 | **0 处差异，verified 仍 43** |
| 声明测试文件 | 0（全靠账本自证） | 133（全部入库） |
| verified | 20/47 | **43/47** |
| 报告用例 | 182（24 文件） | **1290（127 文件）** |

仍未 verified 的 4 个本来就一条测试都没有（RSCOV.04 / ARES.DECIDE.02 / HELM×2）——
空就写空，不拿别的项目的测试凑数。

### 边界

- 声明只校验**存在与归属**，不校验语义相关性；「这个测试是否真的在测这个能力」
  仍需人审。本版做的是把这件事变得可 diff、可复核，而不是自动化判断；
- 本轮 133 个声明文件里有 6 个在干净检出里跑不绿（集成测试需外部服务、RSS/浏览器需网络与凭据），
  它们的能力保持原状，未计入 verified；
- `manual` 型关闭条件仍需人主动关闭；多副本同步税未处理。

## [2.0.3] - 2026-11-19

**路径全集补丁**。v2.0.2 把强制点搬到了机器上，随即暴露了机器上第一条真话：
主仓 24 条不变量在本机全绿，在干净检出里必红 2 条。根因不是账本写错，而是
生成器把「本机文件系统」当成了「仓库事实」——它把被 .gitignore 的 `data/`、
`logs/`、`*.egg-info` 和一份未入库的临时测试写进了架构树与证据索引。

于是出现最坏的一类绿灯：它只在作者机器上成立，别人一 clone 就是假的。
CI 因此只能加一张「本地产物放行名单」——而放行名单本身就是说谎的许可证。

### 本版内容

- 生成器新增 `RepoScope`：路径全集取自 `git ls-files`，仓库里没有的路径一律
  不进账本（源码扫描 / 单测证据 / 测试记录 / 文档索引 / 组件树全部收窄）；
- 非 git 环境退回文件系统全集，但打印 `[WARN]` 自报未核对，不假装验过；
- `norm_existing_path`：「存在但未入库」视同不存在，让 registry 指向仓库外
  文件这件事在校验阶段暴露，而不是悄悄写进账本；
- 新增 `tests/core/test_path_scope.py` 6 条负向证明：先造出本机有、仓库没有的
  文件与目录，再断言它们不出现；
- 主仓删除 CI 的 `doc_paths_exist` / `component_paths_exist` 放行名单，
  门禁回到「任一不变量失败即 exit 1」；
- 文档：`docs/08-可信性校验.md` 新增「路径全集：账本只描述仓库」一节。

### 边界

本版只保证「账本不引用仓库外路径」，不扩大证据覆盖（verified 仍 20/47）；
`manual` 型关闭条件仍需人主动关闭；多副本同步税未处理（模板改动仍需三处同步）。

## [2.0.2] - 2026-11-19

**业务诚信补丁**。v2.0.1 之后做了一次真实价值评估，暴露一个比任何功能都严重的问题：
24 条不变量全绿的同时，目标项目 3 条 `work_items` 全部已经完成却仍挂 `open`
（registry 已拆分、test_report.json 已存在、目标能力已 verified）。
结构自洽掩盖了业务说谎——看板与 `next_queue` 会指挥下一个执行者去做已完成的事。

### 本版内容

- 工作项新增 `close_condition`：`capability_verified` / `file_exists` / `manual`；
- 不变量 #22 `work_items_valid` 扩展语义：关闭条件已被证据满足却仍 `open/doing` 判失败
  （不新增第 25 条，避免契约膨胀）；判定不了的条件一律视为未满足，宁可漏关不可误关；
- `work_panel.py close` 支持 `--resolution` / `--close-condition`；声明了关闭条件的
  工作项关闭时必须写明依据，并记录 `closed_by` / `closed_at`；
- 修 README 两处漂移：测试文件数不再写死（以 `tests/MODULES.json` 为准）、
  删掉「不做 `registry/2` 数据迁移」这句与 v2.0.1 事实相反的话。

### 边界

`manual` 条件无法机器判定，此类工作项仍需人主动关闭；本版只保证「能判定的不许说谎」。

## [2.0.1] - 2026-11-19

**registry schema/2 容器版**。v2.0.0 修好了四段码生成，但 registry 仍是
`project` + 平坦 `modules[]`；多项目 monorepo 只是把项目段内嵌在模块码里，
本体 A4 的「registry 与 capability_model 项目基数一致」靠账本维持单项目掩盖。
本版把容器层契约化：新增唯一 codec，支持 `schema=registry/2` + `projects[]`，
同时保留单项目双读；目标项目的 registry 数据形状迁移仍须人批准、备份与重绑。

### 本版内容

- 新增 `templates/registry_codec.py`，统一 `code_namespace` / `cap_code` /
  `normalize_projects` / `iter_caps`，成为生成器、校验器与可追溯投影器的唯一 codec；
- 生成器遍历归一化后的 projects[]，summary.projects 不再硬编码为 1；
- 校验器不变量 #9 与 `trace_common.iter_caps()` 改为消费同一 codec，堵住
  `trace_common` 裸拼五段码的盲区；
- 第四工具副本 `governance/registry_codec.py` 纳入 TOOLING、布局契约、
  初始化与逐字节同步门禁；
- `acceptance/1` 第七层（L7）四项机器断言：`registry_schema_doc` /
  `registry_schema_test` / `registry_codec_contract` / `registry_dual_read`；
- `tests/core/test_registry_schema.py` 7 项专项覆盖双读、稳定码与唯一 codec。

### 边界

本版只交付工具链契约；真实 registry 从单项目容器迁移为四项目 `projects[]`
属于破坏性数据迁移，需人批准、带清单备份、append-only 审计与独立复放核实。

## [2.0.0] - 2026-11-19

**registry/2 多项目编码契约版**。承接 v1.8.0 交付核实与用户「a」（正式立项 v2.0.0
破坏性迁移授权）：v1.8.0 的工具层已能保证证据适配与不降级，但主仓 registry 的
`project.code=<ROOT>` + `module.code=<PROJ>.DATA` 会被生成器拼成 5 段码
`<ROOT>.<PROJ>.DATA.READY.01`，写盘后 24 不变量跌为 21 pass / 3 fail。本版从根上
修复编码契约：生成器新增 `code_namespace()`，module/cap code 均经它生成，
产出合法 4 段码并保持单项目模板双写兼容；P1 的真实 verified 升级随之可安全落盘。

### 决策依据（第一性原理）

「判据绿 ≠ 结果绿」：v1.8.0 的 `no_regress()` 靠剥离前缀对齐得出「降级 0」，
但写盘把 5 段码写进权威账本，校验器的 `CODE_RE`（4 段）立即判非法。教育是：
判据必须与写盘结果同格式，不能靠对齐技巧绕过。本版让生成器直接产出与账本、
校验器一致的 4 段码，从源头消除失配，而不是继续在判据层打补丁。

### 本版内容

- `templates/build_capability_model.py` 新增 `code_namespace(project_code, module_code)`：
  module_code 含项目段（首段大写）时直接用，否则补 project_code 前缀；
- `build()` 的 module code 与 cap code 均改经命名空间生成，无 5 段码泄漏；
- `acceptance/1` 第六层（L6）四项机器断言：`code_namespace` / `registry2_contract` /
  `no_prefix_leak` / `cap_code_format`；
- `tests/core/test_registry2.py` 9 项专项（双写 / 4 段 / 无泄漏 / no_regress 对齐 /
  真实账本 47 code 合法）；
- 单项目模板 `DEMO.DATA.READY.01` 双写兼容，示例项目不受影响。

### 顺延

| 版本 | 内容 | 状态 |
|---|---|---|
| v1.9.0 | Risk & Evidence（polarity / confidence / contradicting evidence）+ Agent Autonomy Ladder | 顺延 |
| v2.0.0 | `registry/2` 多项目编码契约 / P1 数据迁移 | **本版发布** |
| 待定 | Semantic Graph（Statement 再化 / K3 推理机 / 最小割集 RCA） | 顺延，须先满足 P1–P3（P1 本版满足） |

## [1.8.0] - 2026-11-18

**证据适配与不降级版**。承接 v1.7.0 交付核实与用户「先做 a」的真实执行：
P1 未被满足的根因不是「主仓没有测试」（主仓有 1,248 个自有测试文件、
12,186 个可收集用例），而是方法论仓与生成器的四处适配缺口。本版把这四处
缺口产品化为机器保证，**不碰主仓权威数据**；主仓 registry / capability_model
的修复作为独立的人批准数据迁移方案另行处理。

### 决策依据（第一性原理）

选项 A（人批准真实证据绑定）在写盘前被证伪： runners 能产出 19 passed 的真实
JUnit，合规映射也能让 `judge_tier` 命中 `verified`，但生成器用现有 registry
重算会把 47 个能力从 `L5:20/L3:22/L2:5` 降到 `L2:46/L0:1` —— 绿灯没拿到，
既有等级先毁。按「诚实 > 绿灯」「先确认数据正常再重建快照」停止写盘，
转以工具层根治：先保证重算不降级，再谈升级 verified。

### 新增：acceptance/1 第五层（L5）

四项机器断言：`evidence_adapter`（work_panel 布局探测 + classname→file + 空绑定拒绝）、
`no_regression_guard`（生成器 hints 派生 + 不降级门禁）、`l5_contract_doc`、
`evidence_end_to_end`。`only_preconditions` 范围仍为原 L4 三项，v1.7.0 语义不变。
统一门禁从 15 阶段扩到 16 阶段。

### 缺口 → 实现

- **A 空绑定判绿**：`work_panel.default_source_dirs()` 探测根 `src/tests` 或
  `projects/*/{src,tests}`；空 `evidence_binding.inputs` 时 `overall=fail`。
- **B JUnit 无 file**：`work_panel.classname_to_file()` 按账本 unit_tests 白名单
  反解 basename，命中不到返回空串（不猜）。
- **C 目录失配**：生成器 `_monorepo_dirs()` 把单目录扩展为 `projects/*` 同名目录。
- **D hints 失配**：生成器 `evidence_hints()` 从账本既有 evidence 派生文件名 stem。
- **不降级门禁**：`no_regress()` 比较 code→level，任何下降即 `[BLOCK]` 拒绝写盘；
  `--allow-regress` 仅供人批准的数据迁移显式绕过。

### 验证

真实探针报告（19 passed）在新模板上 `build()`：level 保持 `L5:20/L3:22/L2:5`、
降级数 0、`verified=9`；此前一次「降级 0」是 code 前缀失配造成的假阴性，已纠正。
264/264 单测、16 阶段门禁、`acceptance/1` 十项全 PASS。

### 边界

语义图仍顺延（P1 最终满足需主仓数据迁移 + 人批准）；主仓账本与 registry
在本版未被写盘；`ontology_digest` 因 SOURCE_FILES 含被改脚本而变化，S4 需重绑。

## [1.7.0] - 2026-11-18

「一致性与可适配性」收敛版。**修的是「规划与发布是否一致、无测试报告项目
能否诚实降级、未激活状态能否被账本表达」，不是新增治理对象**；已引入项目
需人批准重绑一次资产摘要。

### 决策依据（第一性原理）

用户授权落实 A（完整 S1 → S2 → S3 → S4 → 发版 + `P` 重绑），但语义图的三项
启动前置条件在本版起点全部未满足：P1 `P` 的真实 CI 报告（无 `tests/`、
无 `test_report.json`、47 能力仍 `declared`）、P2 `ontology.py check` 的 A2
可判定、P3 规划一致性机器断言。按 `feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md`
的 R4 / G6，**语义图顺延**，本版只做 R1–R3：不把 `declared` 伪装成 `verified`，
不把 6 条 `open` 观察勾成闭环，也不为改一句路线图单独发一版。

顺序不可交换：S1 固化证据 → S2 先把 G1–G3 落成 `acceptance.py` 第四层机器
断言并刻意红灯（13 阶段绿 / 2 阶段红）→ S3 实现 R1–R3 转绿 → S4 人批准
重绑 `P` → 发版。

### 新增：`acceptance.py` 第四层（G1–G3）

- G1 `roadmap_consistency`：抽 `docs/23` 第七节与 `CHANGELOG` 的 1.7.0 段落，
  断言两处都含 `v1.7.0 / v1.8.0 / v1.9.0 / v2.0.0` 顺延锚点与「收敛版」，
  且不再出现「v1.6.0 才做语义图」；由机器判定而非人眼复核。
- G2 `conditional_sop`：静态断言 `POST_UPGRADE` 三条取证命令带 shell 守卫与
  `SKIP / status=na`；动态在空 `tests/` fixture 上真实执行，断言不生成
  `governance/test_report.json`。`POST_UPGRADE` 长度仍为 19。
- G3 `activation_placeholder`：在临时副本上真实调用 `upgrade.apply()`，
  断言无报告项目写入 `governance_meta.activation`（`state=unbound`），
  且 24 条三态不变量仍 `23 pass + 1 na`、`all_active=false`。
- `scripts/check.sh` 新增第 15 阶段 `stage_preconditions`（`--preconditions`
  只跑 L4）；检测器自测由 16 个扩到 20 个，全部绿灯且不断言仓库红绿。

### 修复 / 收敛

- **R1 规划一致性**：`docs/23` 第七节改为顺延表，与本版 `CHANGELOG`、
  `RELEASE_CHECKLIST.md` 一致；失配不再靠人眼复核挂着。
- **R2 条件化 SOP**：`POST_UPGRADE` 的取证与 `sync-tests` 命令对无 `tests/`、
  无报告项目降级为显式 `na` + 可审计 skip 记录，绝不伪造报告。
- **R3 M8 `activation` 占位**：`plan()` 把 `governance_meta.activation` 缺失
  纳入 M8 触发条件；`apply()` 写入 `evidence-activation/1` 的 `unbound` 占位，
  使「证据能力未激活」成为可判定账本事实而非 `null`。`verify` 仍 12 项、
  `upgrade_complete` 仍九项判据，三态语义不回归。
- 顺带修 `scripts/ontology.py digest` 的非 `--json` 文本输出（`KeyError: 'mode'`）；
  该缺陷不影响任何摘要与门禁，S1 基线已如实记录。

### 版本提升的成本与边界

`METHOD_VERSION` 与 28 份资产 frontmatter 统一 1.7.0；`docs/16` 的当前示例值
同步，历史引用（tag `v1.6.0`、「v1.5.0 起」）保留。`ontology.py` 的
`SOURCE_FILES` 不含版本脚本、编号文档与 `acceptance.py`，因此
`ontology_digest` 不变；但 `scripts/upgrade.py` / `docs/23` / frontmatter 均在
`ASSET_GROUPS`，`method_assets.digest` 必变，`P` 需一次性人批准
`M4 + M5 + M7` 重绑并留新备份与回滚命令。

### 顺延表（与 `docs/23` 第七节机器校验一致）

| 版本 | 内容 | 状态 |
|---|---|---|
| v1.7.0 | 一致性与可适配性收敛版（R1–R3） | **本版发布** |
| v1.8.0 | Risk & Evidence（polarity / confidence / contradicting evidence） | 顺延 |
| v1.9.0 | Agent Autonomy Ladder | 顺延 |
| v2.0.0 | `registry/2` 多项目数据契约 | 不变，需人批准数据迁移 |
| 待定 | Semantic Graph（Statement 再化 / K3 推理机 / 最小割集 RCA） | 再次顺延，须先满足 P1–P3 |

未做（留后续）：语义图（P1–P3 缺一不可）、`registry/2`。设计内告警
E7 `cardinality_contradiction`、`evidence_rebaseline=na`、`scale_budget`
项目文件阈值均如实保留，未掩盖。

## [1.6.0] - 2026-11-18

验收契约与写入语义的收口版。**修的是「怎么证明修好了」和「证据会不会被自己删掉」，
不是新增治理对象**；已引入项目需人批准重绑一次摘要。

### 决策依据

v1.5.0 之后出现两个必须按序处理的问题：

1. 正文里的计数（六轴 / 18 步 / 11 项 / 八项）与 `upgrade.py` 的真实常量
   （七轴 / 19 步 / 12 项 / 九项）漂移了 27 处，而门禁全绿 —— 测试只证明代码自洽，
   不证明文档没有在骗人。
2. `ledger_feedback.py export` 的覆盖写会把已收敛的 triage 证据抹掉：
   第 19 步 SOP 在真实项目上重跑，观察包从 13 行变 10 行、4 条闭环证据全部消失。
   **反向回流闭环能产证据，却不能保住证据**，这是根因级缺陷。

顺序按「先定义验收，再改权威源」：S1 本地固化升级前后证据（不 push / 不打 tag）
→ S2 写会失败的负向回归与第 14 个门禁阶段（刻意红灯）→ S3 让三层验收转绿
→ S4 人批准重绑目标项目 → 本版统一发版。任何一步反过来做，都无法证明改动有效。

发版时否决了「把版本号从资产摘要口径剥离」：`upgrade.py` 既是权威工具又定义版本，
其 sha 属于 `tools` 轴与 `scripts` 资产；剥离等于让版本标识与规则内容脱钩，正是
本系统要防的第二事实源。**发版触发实例重绑是正确语义**。真正该解耦的是测试里的
硬编码版本号 —— `test_acceptance.py` 改为从 `upgrade.py` 动态读取。

### 新增：`scripts/acceptance.py`（`acceptance/1`）

- 期望值全部从 `upgrade.py` 的 **AST** 抽取（版本 / 七轴 / 1 pre / 19 post /
  12 个 verify id / 9 个判据 id），检测器里不写死任何计数。
- 三层判定：`L1` 字面量扫描手写源、资产与生成器源（含派生文件），按行级历史豁免
  区分 `drift` 与 `review`；`L2` 三份派生文档必须可由各自生成器复算；
  `L3` 用真实 export 探针验证观察包 append-only、已收敛 triage 证据不丢、
  `obs_id` 去重、重复导出幂等。
- `--check` 非零退出；`scripts/check.sh` 新增第 14 阶段 `stage_acceptance`。
- 16 个绿灯自测只证明检测器本身有效，不断言当前仓库是红是绿；S3 转绿后仍全通过。
- 扫描范围含 `scripts/*.py`，因此找出了 11 个文档复核没发现的根因：
  2 份派生文件的漂移源头在 **4 个生成器源码**里。只改派生文件会让 `L2` 立刻变红。

### 修复

- **`ledger_feedback.py` append-only**：新增 `merge_observations()` 纯函数，
  `export` 写盘改为「读既有行 → 按 `obs_id` 合并 → 既有行优先 → 确定性顺序」，
  已收敛 triage 证据永不被覆盖；`triage` 的整体重写语义保持不变；
  payload 的 `count` / `sha256` / `observations` 与 `merge` 统计反映实际写入结果。
  4 个新增回归，`docs/22` 补写入契约。
- **27 处计数漂移**：先改 4 个生成器源，再用 `--emit-md` 重算派生文件，
  从未手改 `docs/generated/`；10 处历史演进陈述逐条确认并补版本边界，不伪装成当前值。
  `upgrade.py` / `docs/16` 写明「计数以代码常量为准，由 `acceptance.py` 校验」。
- **`stage_scenarios` 误判**：原先唯一用 `git diff --exit-code`（与 HEAD 比）检查
  派生文件，把合法重算当成手改；统一到另两阶段的「临时重算 + `cmp`」只读口径。
- 因 `ledger_feedback.py` / `scenario_matrix.py` 属于 `ontology.py` 的 `SOURCE_FILES`，
  重算第七轴 `ontology_digest`：`c399ff18… → e258dec1…`。

### 版本提升的成本与边界

- `METHOD_VERSION` 与 28 份资产 frontmatter 统一 1.6.0；`docs/16` 的示例值同步，
  历史性「v1.5.0 起」保留。
- 本体的 `SOURCE_FILES` 刻意不含版本脚本，因此**升版本不改 `ontology_digest`**；
  但 `scripts/upgrade.py` 在资产摘要作用域内，`method_assets.digest` 必变，
  已引入项目需再跑一次 M4 + M5 + M7 并复验。
- 未做（留后续）：条件化第 1/2/15 步 SOP、M8 `activation` 占位、`registry/2`
  多项目数据契约。设计内告警 E7 `cardinality_contradiction`、
  `evidence_rebaseline=na`、`scale_budget` 项目文件阈值均未掩盖。

## [1.5.0] - 2026-11-18

本体投影层落地。**只改方法论仓库权威源，不触碰任何已引入项目的账本数据契约、
不自动升级任何项目、不改 `registry` 数据形状。**

### 决策依据

这套系统早就在隐式回答本体四问（实体 / 取值域 / 关系基数 / 公理），问题不是
「要不要有本体」，而是「要不要把散落的答案收成一份可机器复算的元契约」。
取证发现 `docs/STANDARD.md` 第四章只声明 4 类状态机、实际运行 9 套以上；
账本 `fields` 只自述 5 个字段而实际条目有 12 个；`registry.project` 是单数 dict
而派生能力模型有 4 个项目。**没有任何机器能命名这是一条基数公理违例**，
所以此前只能靠「不跑生成器重算」人为回避。

关键判断：本体一旦变成第二份手维护的事实，`registry.json` 的覆辙会原样重演。
因此唯一自洽的形态是 `ONTOLOGY = f(权威源)` 的**派生只读投影**：删光派生文件
也能逐字节复原。另外「状态词全项目统一」这句抽象本身是错的——9 套状态机属于
9 类实体，本体统一的是 `<Type>.field` 形式，不是取值。

顺序上本体必须排在 `registry/2` 之前：**先定义什么合法，再改数据长什么样**。

### 新增：`scripts/ontology.py`

- `build` 用 AST 从 `docs/STANDARD.md` 词表 + 6 个脚本的真实枚举 + 校验器
  `add()` 的 24 个不变量 id 抽取 TBox，输出确定性 `ledger-ontology/1`；
  每个来源带 `sha256`，每条关系带 `derivation` 与 `source_ref`（无孤儿边）。
- `check` 校验投影同步、来源绑定、幂等、声明值 ↔ 代码枚举一致、词表分型；
  `--target P` 只读检查三类漂移：`polyseme_violation` /
  `cardinality_contradiction` / `undeclared_entity` + `undeclared_value`。
  未升级项目记 `na`，不把「未启用」算成通过。
- `diff --target P` 复用 `ledger_feedback.make_obs` 输出
  `affected_axis=ontology` 观察，走 v1.4.0 四产物 triage 闭环；
  `emit-md` / `digest` 提供只读视图与摘要。写盘一律需 `--apply --approved-by`。
- 不引入 OWL / RDF / 图数据库 / 开放世界语义；零第三方依赖、无时间戳。

### 词表与第七轴

- `docs/STANDARD.md` 第四章改写为 **18 个 `<Type>.field` 分型取值域**，
  并把 `level` / `evidence_tier` / `severity` / `confidence` 四条序数尺度解耦。
  只改代码不改词表判 `undeclared_value`，只改词表不改代码判 `undeclared_entity`。
- `docs/generated/ONTOLOGY.json` + `ONTOLOGY.md` 为派生只读投影。
- `upgrade.py apply` 在 **M5 分支**写入 `governance_meta.ontology_digest`
  （第七轴，只存摘要不复制本体）；`verify` 新增 `ontology_binding`
  （`pass` / `na` / `warn`）。**8 条迁移与 19 步升级后流程保持不变**。

### 真实闭环

首次对存量多项目仓库运行 `diff`，把此前模糊的 monorepo gap 命名为
`cardinality_contradiction`（4 个项目 vs 单数 project，命中 A4），
并 triage 成 `tests/meta/test_ontology.py` 的负向回归。观察包从
**12 条 / 3 收敛**变为 **13 条 / 4 收敛**。

### 验证

- 新增 `tests/meta/test_ontology.py` 12 个回归（含「先失败后通过」、
  非法状态词、伪造单项目 registry、幂等、无批准人写盘被拒、第七轴绑定）；
  `tests/MODULES.json` 纳管 23 个测试文件。
- `scripts/check.sh` 新增「本体层」阶段（共 13 阶段），并在「升级与接入」
  阶段校验升级后的第七轴绑定。
- `docs/23-本体投影.md`；28 份资产 frontmatter 与 `METHOD_VERSION` 统一 1.5.0。

### 边界

`registry/2` 多项目契约仍留 **v2.0.0** 且需人批准数据迁移；语义图、
风险/证据语义、Agent 自治阶梯顺延 v1.6.0 / v1.7.0 / v1.8.0。

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
