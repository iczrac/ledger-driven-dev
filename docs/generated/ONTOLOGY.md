# 本体投影（generated，只读）

schema `ledger-ontology/1` · digest `74fb561d806977d0734dd477b710a2872142b2bfd21df9d895eedfcd51292fbd`

由 `python3 scripts/ontology.py build --apply --approved-by <人>` 从事实源渲染。
**不是人工文档，也不是第二事实源**：删掉本文件后 build 可逐字节复原。

## 有界上下文

| 上下文 | 职责 | 关系 |
|---|---|---|
| BC-FACT · 账本事实 | 决策 / 能力 / 工作项 / 测试投影 | shared-kernel |
| BC-METHOD · 方法论与版本 | 版本 / 迁移 / 资产 / 发布 | published-language |
| BC-VERIFY · 校验与证据 | 不变量 / 门禁 / 证据分层 | downstream |
| BC-ADOPT · 目标项目落地 | 升级 / 只读副本 / 骨架 | conformist+acl |
| BC-FEEDBACK · 观察与回流 | 观察 / triage / 基线 diff | upstream |
| BC-DOMAIN · 业务领域 | 被治理项目 1..N | consumer |

## 统一语言（分型，禁止词表归一）

| 术语 | 出现实体 | 同形异义 | 限定形式 |
|---|---|---|---|
| affected_axis | Observation | 否 | `<Type>.affected_axis` |
| case_status | TestResult | 否 | `<Type>.case_status` |
| confidence | 序数尺度 | 否 | `<Type>.confidence` |
| disposition | Observation | 否 | `<Type>.disposition` |
| evidence_tier | Capability | 否 | `<Type>.evidence_tier` |
| kind | HistoryEvent, WorkItem | 是 | `<Type>.kind` |
| level | Capability | 否 | `<Type>.level` |
| role | Agent | 否 | `<Type>.role` |
| severity | Observation, WorkItem | 是 | `<Type>.severity` |
| source_adapter | TestReport | 否 | `<Type>.source_adapter` |
| status | Check, Decision, Lesson, LessonCandidate, Observation, Scenario, WorkItem | 是 | `<Type>.status` |

## 取值域（声明值 ↔ 代码枚举）

| 域 id | 声明取值 | 代码来源 | 一致 |
|---|---|---|---|
| `Agent.role` | evidence-auditor · expert-router · greenfield-architect · ledger-steward · loop-executor · platform-steward · project-archaeologist · release-steward | `scripts/agent_gateway.py#ROLE_POLICIES` | 是 |
| `Capability.evidence_tier` | declared · verified | `templates/build_capability_model.py#EVIDENCE_TIER_SPEC` | 是 |
| `Capability.level` | L0 · L1 · L2 · L3 · L4 · L5 | `templates/build_capability_model.py#LEVELS` | 是 |
| `Check.status` | fail · na · pass | `仅文档声明` | — |
| `Decision.status` | decided · deferred · done · proposed · superseded | `仅文档声明` | — |
| `HistoryEvent.kind` | change · genesis · manual | `仅文档声明` | — |
| `Lesson.status` | confirmed · draft · retired | `templates/verify_ledger.py#LESSON_STATUS` | 是 |
| `LessonCandidate.status` | dismissed · open | `仅文档声明` | — |
| `Observation.affected_axis` | access · board_skeleton · evidence · general · hygiene · installed_assets · ledger_version · lifecycle · method_assets · method_version · ontology · registry · scale · test_results · tool_hashes · work_items | `scripts/ledger_feedback.py#AXES` | 是 |
| `Observation.disposition` | invariant · migration · regression · scenario · wontfix | `scripts/ledger_feedback.py#DISPOSITIONS` | 是 |
| `Observation.severity` | high · low · med | `仅文档声明` | — |
| `Observation.status` | closed · open | `仅文档声明` | — |
| `Scenario.status` | by-design · covered · gap · partial | `scripts/scenario_matrix.py#STATUSES` | 是 |
| `TestReport.source_adapter` | auto · jest · junit · ledger | `scripts/work_panel.py#ADAPTERS` | 是 |
| `TestResult.case_status` | error · fail · pass · skip | `scripts/work_panel.py#CASE_STATUSES` | 是 |
| `WorkItem.kind` | issue · todo | `scripts/work_panel.py#KINDS` | 是 |
| `WorkItem.severity` | high · low · med | `scripts/work_panel.py#SEVERITIES` | 是 |
| `WorkItem.status` | blocked · doing · done · open | `scripts/work_panel.py#STATUSES` | 是 |

## 实体类型

| 类型 | 上下文 | 事实来源 |
|---|---|---|
| Project | BC-DOMAIN | `capability_model.projects[]` |
| Module | BC-DOMAIN | `capability_model.projects[].modules[]` |
| Capability | BC-DOMAIN | `registry.modules[].caps[]` |
| Decision | BC-FACT | `entries[]` |
| Rationale | BC-FACT | `entries[].rationale` |
| Evidence | BC-VERIFY | `entries[].evidence[] / test_results` |
| Claim | BC-VERIFY | `entries[].decision` |
| Risk | BC-FEEDBACK | `work_items[kind=issue] / observations` |
| Action | BC-FACT | `work_items[] / upgrade_log` |
| Outcome | BC-VERIFY | `test_results / verify 输出` |
| Observation | BC-FEEDBACK | `feedback/observations.jsonl` |
| Lesson | BC-FACT | `lessons.items[]` |
| Pattern | BC-METHOD | `lessons / 回归用例` |
| Agent | BC-ADOPT | `access.agents[]` |
| Asset | BC-METHOD | `governance_meta.method_assets` |
| Invariant | BC-VERIFY | `verify_ledger.py add() ids` |

## 关系（domain → range / 基数 / 派生）

| 谓词 | domain → range | 基数 | 派生 |
|---|---|---|---|
| `contains` | Project → Module | 1..N | `capability_model.projects[].modules[]` |
| `supersedes` | Decision → Decision | 0..1 | `entries[].supersedes` |
| `verifiedBy` | Capability → Evidence | 0..N | `test_results / evidence_binding` |
| `decides` | Decision → Capability | 0..N | `capability_model decision refs` |
| `actsOn` | Action → Capability | 0..N | `work_items[].scope` |
| `generalizesFrom` | Lesson → Outcome | 1..N | `lessons.candidates[]` |
| `detects` | Observation → Risk | 0..N | `feedback/observations.jsonl` |

## 公理

| id | 陈述 | 检查 |
|---|---|---|
| A1 | dependsOn 无环 | `acyclicity` |
| A2 | level >= L3 必须有新鲜 verified 证据 | `evidence_freshness` |
| A3 | 每个能力恰好一个 owner | `ownership_exactly_one` |
| A4 | Project 基数 1..N，能力编码在 project 内唯一 | `project_cardinality` |
| G1 | 无孤儿边：每条关系可从事实源复算 | `no_orphan_edge` |
| G3 | Kleene K3：含 Unknown 不得派生 pass | `three_valued` |
| G4 | append-only：只取代不删除 | `append_only` |

账本不变量 26 条：

`board_embed_synced` `completion_matches_level` `component_paths_exist` `decision_refs_valid` `doc_paths_exist` `encoding_format` `encoding_unique` `entry_ids_unique` `evidence_tier_valid` `history_chain_consistent` `history_current_matches` `history_event_fingerprints` `history_state_encoding` `installed_assets_binding` `lesson_candidates_dedup` `lessons_valid` `next_action_present` `queue_lessons_confirmed` `registry_impls_exist` `supersede_chain_consistent` `test_results_binding_valid` `verified_tier_not_premature` `verified_tier_traceable` `work_item_refs_valid` `work_items_owned` `work_items_valid`

## 来源绑定

| 文件 | 角色 | sha256 |
|---|---|---|
| `docs/STANDARD.md` | ubiquitous_language | `c4177d34f5472cc8…` |
| `scripts/work_panel.py` | value_domains | `106a91b55b35abb8…` |
| `scripts/scenario_matrix.py` | value_domains | `7ecc9c5a058eaf4f…` |
| `scripts/ledger_feedback.py` | value_domains | `ee3d577f0a600e05…` |
| `scripts/agent_gateway.py` | value_domains | `83d1b63a3e7bd850…` |
| `templates/build_capability_model.py` | value_domains | `a11c76f1666130a5…` |
| `templates/verify_ledger.py` | axioms | `b18e52ec26d796e4…` |

漂移条目：0
