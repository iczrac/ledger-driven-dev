# 版本规划对账 —— v1.6.0 之后

> 一次性**取证对账**，不是状态清单、更不是第二事实源。
> 观察状态的权威源是 `feedback/observations.jsonl`；发布状态的权威源是
> `DECISION_LEDGER.json`；发布自检的权威源是 `RELEASE_CHECKLIST.md`。
> 本文只回答「还有哪些规划没落地、为什么、下一步怎么收口」。
> 目标项目一律记作 `P`；所有写盘动作均以人批准为前提。

## 一、结论摘要

**有，而且不只是「还没做」，还有两处规划本身失配 / 遗漏**：

1. **原定 v1.6.0 = Semantic Graph 没有实现**。ODLA 提案第 7 节与
   `docs/23-本体投影.md` 第七节都把 v1.6.0 定义为「Statement 再化 + K3 推理机 +
   最小割集根因分析 + `SEMANTIC_GRAPH.jsonl` / `AXIOMS.json` / `INFERENCE.jsonl`」。
   实际发布的 v1.6.0 是「验收契约 + append-only 写入语义 + 版本统一」
   （S1–S4 反向优化序列占用了该版本号）。**规划陈述必须顺延重编号**。
2. **发布纪律遗漏**：`RELEASE_CHECKLIST.md` 第 171 行规定「从本版起每个 tag 必须
   写明 `feedback_closed`，否则不算完整发布」，但 v1.6.0 段发布时漏写。本轮已补记。
3. **反向回流闭环未完成**：`docs/22` 明确「下一版必须先从 9 条 open 里挑出能收敛的，
   再谈新功能」，而发版时 9 条仍全部 open。本轮已收敛 3 条。
4. 另有 3 项真实待办（条件化 SOP / M8 `activation` / `registry/2`）、
   3 条升级现场摩擦、6 条早期数据治理线任务（其中 2 项属用户侧阻塞）。

## 二、六类规划来源全盘点

| # | 来源 | 性质 | 状态 |
|---|---|---|---|
| 1 | ODLA 提案第 7 节「演进路线图」 | 外部架构提案（历史证据） | v1.5.0 已落地；v1.6.0–v2.1.0 未落地且编号失配 |
| 2 | `docs/23-本体投影.md` 第七节「后续」 | 权威源内编号文档 | 同上，写「v1.6.0 才做语义图」，现已过时 |
| 3 | `CHANGELOG.md` v1.5.0 段「边界」 | 历史发布记录 | 写明语义图 / 风险语义 / 自治阶梯顺延 v1.6.0 / v1.7.0 / v1.8.0 |
| 4 | `RELEASE_CHECKLIST.md` 未勾项 | 发布自检清单 | 发版前 7 项：3 过期、1 重复、3 真实 |
| 5 | `feedback/observations.jsonl` | 反向回流权威观察包 | 13 条 / 9 open / `feedback_closed=4` |
| 6 | `feedback/UPGRADE-DIFF-1.5.0.md` | 升级现场证据 | 3 条现场摩擦 + 10 条持续观察 |

另有 `feedback/baseline.jsonl`（12 条 / 10 open / 2 收敛）与
`feedback/post-v150.jsonl`（15 条 / 13 open / 2 收敛）—— 它们是**升级时点快照**，
属于不可回补的历史证据，不是当前待办清单，不应与 `observations.jsonl` 混算。

## 三、核心失配：v1.6.0 Semantic Graph

| 原定版本 | 规划内容 | 实际 / 调整后 |
|---|---|---|
| v1.5.0 | Ontology Projection | **已发**：`ontology.py` / 第七轴 / 分型词表 |
| v1.6.0 | **Semantic Graph**（Statement 再化、K3 推理机、最小割集 RCA、依赖推理） | **未实现**；该版本号被 S1–S4 序列占用 → 顺延 **v1.7.0** |
| v1.7.0 | Risk & Evidence（polarity / confidence / contradicting evidence） | 顺延 **v1.8.0** |
| v1.8.0 | Agent Autonomy Ladder | 顺延 **v1.9.0** |
| v2.0.0 | `registry/2` 多项目契约（破坏性） | **不变**，仍需人批准数据迁移 + 备份 + 双写兼容期 |
| v2.1.0 | Cross-project Learning | 顺延，暂不排期 |

**为什么不马上改 `docs/23` 正文**：整包摘要 `method_assets.digest` 含
`docs/[0-9][0-9]-*.md`，改一句话就会让主仓刚绑定的 `264026fd…` 漂移，需要再次
人批准 `M5 + M7` 重绑并复验。为一句规划表述单独再发一版不划算；应与 v1.7.0
实现合并为一次发版。这是内容绑定的固有成本，不是设计缺陷。

## 四、观察包对账（本轮已执行）

`feedback/observations.jsonl` 13 条，人批准 triage 3 条：

| obs_id | 症状 | 处置 | 依据 |
|---|---|---|---|
| `OBS-177ea075fd95` | 项目版本落后于权威源 | `migration` → `scripts/upgrade.py` | v1.6.0 以 `M4-method-version` 重绑到 1.6.0，版本差归零；当前 `export` 已不再产生该观察 |
| `OBS-0c6f466b1f35` | 历史迁移日志 `1.2.0 → 1.2.1` | `wontfix` | append-only 事实记录，非摩擦；v1.6.0 起 export 合并写，不会覆盖既有证据 |
| `OBS-a9e373d99ef4` | 历史迁移日志 `pre-1.0.0 → 1.2.0` | `wontfix` | 同上 |

结果：`open 9 → 6`、`closed 4 → 7`、`feedback_closed 4 → 5`、`check ok=true`。
逐行取证：**仅 3 行变化**，既有 4 条已收敛证据逐字段不变；
`baseline.jsonl` / `post-v150.jsonl` 两包 sha 不变；
`observations.jsonl` sha 由 `e0b313ef…` → `414506bd…`（变化来自 triage 字段，
属预期的人批准更新，不是证据销毁）。

**当前 `export --target P` dry-run 对账**：采集到 14 条（`method_version=1.6.0`）。
与既有 13 条相比，消失 3 条（版本落差、两态校验器、本体基数违例——前两条已解决、
第三条已在观察包内收敛为负向回归），新增 4 条（3 条 append-only 迁移日志 +
1 条 `test_results_binding_valid=na`）。本轮**刻意不把 4 条新观察合并进观察包**：
它们是事实记录与三态语义，不是新摩擦，写入只会制造 4 条假待办；
按 UPGRADE-DIFF 的既有判例直接归为非缺陷。

### 剩余 6 条 open 的处方

| obs_id | 轴 | 处方 | 归属 |
|---|---|---|---|
| `OBS-398702b044d3` | `test_results` | 由 `work_panel.py import-report` 导入目标项目 CI 报告后 `sync-tests` 绑定，L5 能力才能升 `verified` | 目标项目侧，需人批准写盘 |
| `OBS-8e793c179a37` | `evidence` | 同上；`test_results` 投影绑定后能力等级不再停留 `declared` | 目标项目侧 |
| `OBS-3e1dc0bf5d08` | `registry` | `registry/2` 多项目契约，按 A4 公理迁移 | **v2.0.0**，人批准数据迁移 |
| `OBS-4a5df8fa3375` | `access` | `agent_gateway.py register --approved-by <人>` 激活名册；默认拒绝是设计，缺的是人批准动作 | 目标项目侧，需人批准 |
| `OBS-6d8fd8882341` | `general` | `lifecycle.py status` 写入生命周期；方法论仓已有状态机与冻结门 | 目标项目侧，需人批准 |
| `OBS-ae2cdd6e8130` | `general` | `ledger_lesson.py --confirm --insight ... --action ...` 确认经验候选 | 目标项目侧，需人批准 |

结论：**方法论仓侧真正未做的只有 `registry/2` 与 v1.7.0 功能迭代**；其余 5 条是
「能力已具备、目标项目尚未消费」，不应伪装成代码缺陷。

## 五、发布清单对账（本轮已清理）

发版前 7 个未勾项，分类如下：

| 类型 | 条目 | 处置 |
|---|---|---|
| 过期 3 项 | 重新批准 `M4+M5` 重绑、升级到 1.4.0、升级到 1.5.0 | 已由 U（`1.2.1 → 1.5.0`）与 v1.6.0 发版完成 → **勾除并注明证据** |
| 重复 1 项 | v1.5.0 段的 `registry/2` | 合并到文末唯一主条目 → **删除重复** |
| 真实 3 项 | 条件化第 1/2/15 步 SOP、M8 `activation` 占位、`registry/2` | 保留，前两项标注合并进 v1.7.0 |

同时补上 v1.6.0 段缺失的 `feedback_closed` 声明：
发布时点 = 4，本轮 triage 后 = 5（两个时点都写明，不伪造历史）。
清单末尾新增「路线图对账」节，记录顺延重编号与启动成本。

## 六、升级现场三条摩擦（UPGRADE-DIFF-1.5.0）

| # | 摩擦 | 状态 |
|---|---|---|
| 1 | `POST_UPGRADE` 第 19 步覆盖写会销毁既有 triage 证据 | **已修**：v1.6.0 `merge_observations()` append-only 合并 + 4 个回归 + `acceptance/1` L3 探针 |
| 2 | 第 1/2/15 步对「多项目 + 无实测报告」项目不可安全执行 | **未修**：v1.3.0 已给 `import-report` 适配器，流程本身未条件化 → v1.7.0 |
| 3 | M8 未触发时 `activation` 占位缺失 | **未修**：只能靠 `evidence_rebaseline=na` 表达 → v1.7.0 |

## 七、早期数据治理线 6 项（另一条线，不属本仓版本规划）

任务列表里另有 6 项 2026-11-16 的 `in_progress / pending`：
T34 写入口 dry-run 预设、T35 历史凭证轮换与清理、T38 依赖上锁与漏洞扫描、
T39 索引重建与 size gate、T40 工具链故障、T43 章节与闸门推广。

按当日记录，它们不属于 `ledger-driven-dev` 的版本路线图，且存在**用户侧阻塞**：

- T35：第三方后台凭证轮换 + git 历史清理，AI 无法代劳（用户已明确系统凭证与
  待轮换的第三方 key 是两回事，且后台轮换需人操作）；
- T40：需系统级安装依赖（openssl@3 / Rosetta），沙箱拦截无法代劳；
- T34：被「live 写入边界」决策阻塞；T38 / T39 / T43 依赖 CI 门禁前置。

本轮**不擅自执行**：涉及凭证轮换、git 历史改写与生产写入默认值，属高风险且已有
明确的人侧边界。若需推进，应单独立项并逐项确认。

## 八、收口顺序与启动成本

**v1.7.0（建议合并为一次迭代）**：语义图（原 v1.6.0）+ 条件化第 1/2/15 步 SOP +
M8 `activation` 占位 + `docs/23` 规划表述修正 + 新一轮观察收敛。
按既有纪律 S1 固化证据 → S2 先写红灯 → S3 转绿 → S4 人批准重绑 → 发版推进。

**v1.8.0** Risk & Evidence；**v1.9.0** Agent Autonomy Ladder；
**v2.0.0** `registry/2`（独立立项，人批准数据迁移 + 备份 + 双写兼容期，
不得由 Agent 自动执行）。

**成本提醒**：任何权威源改动（编号文档、`upgrade.py`、`templates/*`、新增脚本）
都会改变 `method_assets.digest`，需再次人批准 `M4 + M5 + M7` 重绑主仓并复验。
因此切忌零散发版；上述 v1.7.0 内容必须一次合并。

## 九、本轮边界

已做：triage 3 条观察（人批准）、清理发布清单、补 `feedback_closed` 声明、
撰写本对账报告、跑门禁并同步远端。

**未做**：未改任何权威源字节（`method_assets.digest` 仍 `264026fd…`、
`ontology_digest` 仍 `e258dec1…`）、未升 `METHOD_VERSION`、未打新 tag、
未写目标项目账本（97 个在途改动不变）、未执行 `registry/2`、未触碰早期数据治理线任务、
未实现语义图。所有剩余功能与数据迁移均需另行决策与人批准。
