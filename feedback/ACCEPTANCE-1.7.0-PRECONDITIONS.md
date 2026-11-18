# v1.7.0 验收前置契约（S2 红灯定义书）

> **性质**：一次性决策取证 + 下一版的验收定义。**不是状态清单、不是第二事实源**。
> 观察状态权威源是 `feedback/observations.jsonl`；发布状态权威源是
> `DECISION_LEDGER.json`；发布自检权威源是 `RELEASE_CHECKLIST.md`；
> 当前验收判据权威源是 `scripts/acceptance.py`。
> 目标项目一律记作 `P`；所有写盘动作均以人批准为前提。
>
> 本文**取代** `feedback/ROADMAP-AUDIT-1.6.0.md` 第八节给出的启动顺序。
> 那份报告是「一次性取证对账」，按 append-only 证据纪律**保持原文不改**，
> 本文以新增文件的方式记录后续决策，不回补、不覆盖历史。

## 一、决策结论

**本轮不启动 v1.7.0、不发版、不改任何权威源字节、不写 `P` 的账本。**

从「治理系统唯一目的 = 规则可复放 + 事实可验证 + 不可伪造」推出三条硬约束，
三条都指向同一结论：

| 约束 | 取证事实 | 推出的排除项 |
|---|---|---|
| **C1 诚实 > 绿灯** | `P` 无 `tests/`、无 `governance/test_report.json`，账本 `activation=null`、`test_results=null`；`docs/11` 的 `verified_tier_traceable` / `verified_tier_not_premature` 会抓任何伪造 `verified` | 排除「目标项目侧消费」：`import-report` 只能用 `P` 自己的真实 CI 报告；用方法论仓自身测试顶替是张冠李戴的第二事实源。`na` 与 47 个 `declared` 必须保持 |
| **C2 依赖顺序不可倒置** | `ontology.py` A2「`level >= L3` 必须有新鲜 `verified` 证据」、G3「含 Unknown 不得派生 `pass`」；`P` 的 47 能力全 `declared` → A2 全违例 → K3 恒 Unknown | 排除语义图（Statement 再化 / K3 推理机 / 最小割集 RCA）作为本轮主体：在零 `verified` 事实上是空集推理 |
| **C3 版本经济** | 实证 `docs/[0-9][0-9]-*.md`、`scripts/*.py`、`templates/*`、frontmatter 均在 `ASSET_GROUPS`；改任一处 → `method_assets.digest` 变 → 固定成本 = 一次发版 + `P` 的 `M4+M5+M7` 全量重绑（28 副本 drift）+ 人批准 | 排除「刚发 v1.6.0 就为 3 个小修再发一版」：这正是本方法论明令避免的零散发版 |

C2 挡住唯一够格的功能包（语义图），C3 随即禁止为零散小修单独发版；C1 挡住
`P` 侧消费；`registry/2` 是破坏性数据契约且明定「不得由 Agent 自动执行」；
早期数据治理线 6 项存在用户侧阻塞（凭证轮换 / 系统安装 / live 写入边界）。
**没有任何一项够格在本轮改变权威字节。**

## 二、依赖顺序证明（为什么语义图不能先做）

`G = g(L0, ONTOLOGY)`：语义图的输入是 L0 的 `evidence_tier` 与
`evidence_binding`，不是本体词表本身。

1. A2 要求 L3+ 能力持有新鲜 `verified` 证据；当前 `P` 无任何
   `test_report.json`，全部 47 能力为 `declared`。
2. G3（Kleene K3）规定「含 Unknown 不得派生 `pass`」；A2 全违例意味着
   所有 L3+ 断言落入 Unknown。
3. 于是最小割集 RCA、依赖推理、置信度传播的输入全为 Unknown，输出也只能是
   Unknown —— 推理机产不出任何可行动的结论。

结论：语义图不是「可以提前做的功能」，而是**以真实证据为前置条件的推理层**。
先建推理机再补证据，等于先造仪表再接传感器。

## 三、C1 补充：为什么 `na` 不能被「修好」

`POST_UPGRADE` 第 1/2/15 步在 `P` 上不可安全执行，其原文为：

```
1  cd P && python3 governance/run_tests.py --dir tests --top . --out governance/test_report.json --label project
2  cd P && python3 governance/build_capability_model.py --root . --test-report governance/test_report.json --strict-evidence
15 python3 scripts/work_panel.py --target P sync-tests --apply --approved-by <人>
```

第 1 步要求 `P/tests/` 存在；不存在时任何「补一份报告」的动作都是伪造。
v1.3.0 引入三态 `pass / fail / na`，正是为了让这种「无报告」被诚实表达为
`na` 而非假绿灯。因此 `evidence_rebaseline=na` / `all_active=false` 是
**当前事实的正确表达**，不是待修缺陷。剩余 6 条 `open` 观察中的
`access` 名册激活、`lifecycle` 登记、经验候选确认也只写治理元数据，
不产生 `verified` 证据；把它们勾掉只是「为了闭环而闭环」的假收敛。

## 四、本轮实际推进（零摘要成本）

| # | 动作 | 作用域 | 效果 |
|---|---|---|---|
| 1 | 修订仓外 `Ontology-Driven-Ledger-Architecture.md` 第 7 节 | 两仓之外 | 立即消除一处「v1.6.0 = Semantic Graph」的错误陈述；补依赖顺序判据、P1–P3 前置条件、U 已执行的史实 |
| 2 | 新增本文 | `feedback/`（`ZERO` 作用域） | 把下一次发版的验收条件、启动条件、成本写死 |
| 3 | 更新 `RELEASE_CHECKLIST.md` 路线图对账节 | 根级 md（`ZERO` 作用域） | 3 个未勾项改为「攒批 + 带门禁条件」 |

三者均**不在** `ASSET_GROUPS`（实证：`feedback/*`、`RELEASE_CHECKLIST.md`、
`CHANGELOG.md` 为 `ZERO`；`docs/23-本体投影.md`、`scripts/upgrade.py`、
`templates/verify_ledger.py` 为 `ASSET`）。因此
`method_assets.digest` 与 `ontology_digest` 都不变，`P` 的绑定保持有效，
**不需要重绑、不需要发版**。

`docs/23` 第七节仍写着旧规划 —— 这是**已知且刻意保留**的失配：修它属于
`ASSET` 改动，必须与 v1.7.0 的实现攒成一次发版。为防止它永久挂着，
下面 G1 把它列为必须由机器门禁校验的转绿判据。

## 五、v1.7.0 的验收定义（S2 红灯 → S3 转绿判据）

> **诚实边界**：本节是**定义**，尚未落成机器门禁。把判据写进
> `scripts/acceptance.py` 本身是 `ASSET` 改动，只能在 v1.7.0 的 S2 执行。
> 在此之前由 `RELEASE_CHECKLIST.md` 提供弱保证（人批准清单），
> S2 必须把 G1–G3 升级为机器断言，否则不算完成验收。

**范围（必须一次合并，不得零散发版）**

- R1 `docs/23` 第七节路线图与 `CHANGELOG` 一致；
- R2 条件化 `POST_UPGRADE` 第 1/2/15 步（无 `tests/` / 无报告项目的降级路径）；
- R3 M8 `activation` 占位与 `all_active` 语义；
- R4 语义图 —— **仅当 P1–P3 全部满足时**才纳入；否则 v1.7.0 降级为
  「一致性与可适配性」收敛版，语义图再次顺延。

**六条转绿判据**

| id | 判据 | 验证方式 |
|---|---|---|
| G1 | `docs/23` 第七节不再出现「v1.6.0 才做语义图」，且与 `CHANGELOG` / 本文顺延表一致 | 新增 `acceptance.py` 的规划一致性断言（机器）；不是人眼复核 |
| G2 | 第 1/2/15 步在无 `tests/` 项目上降级为显式 `na` + 可审计 skip 记录，**不生成任何报告**；19 步常量与 `acceptance.py` 的 AST 抽取保持同步 | 负向回归：注入空 `tests/` fixture，断言不产生 `test_report.json`；`POST_UPGRADE` 长度断言仍为 19 |
| G3 | 无报告时账本写入显式 `activation` 占位（非 `null`），`all_active` 语义不回归；24 条三态不变量仍 `23 pass + 1 na` | `templates/verify_ledger.py` + `P` 侧 `--json` / `--strict` 复验 |
| G4 | 三包观察 sha 与既有 7 条 `closed` 证据逐字段不变；append-only 探针仍幂等 | `ledger_feedback.py check` + `acceptance.py` L3 |
| G5 | `bash scripts/check.sh` 14/14 全绿、`acceptance/1 overall=pass`、`drift=0`、3 份派生可复算 | 门禁输出 |
| G6 | P1–P3 前置条件在发版报告中被显式记录（满足 / 未满足及对应范围裁剪） | `feedback/RELEASE-1.7.0.md` |

**语义图启动前置条件**（P1–P3，缺一不可）

- **P1**：`P` 至少一条能力升为 `verified`，且由 `P` 自己的真实 CI 报告经
  `import-report` + `sync-tests` 绑定；
- **P2**：`ontology.py check --target P` 中 A2 可判定（不再是 `na`）；
- **P3**：G1 的机器断言已上线并通过。

## 六、启动序列与固定成本

按既有纪律 **S1 → S2 → S3 → S4 → 发版**，顺序不可交换：

1. **S1**：本地固化当前证据（三包 sha、两项摘要、门禁基线），不 push / 不打 tag；
2. **S2**：把 G1–G3 落成 `acceptance.py` 第 4 层 + 新门禁阶段，刻意红灯；
3. **S3**：实现 R1–R3（以及满足条件时的 R4），重算派生与本体投影，转绿；
4. **S4**：人批准 `apply` 重绑 `P`（备份 + `M4 + M5 + M7` + 复验）；
5. **发版**：升 `METHOD_VERSION` 1.7.0 + 28 份 frontmatter + `CHANGELOG` /
   `RELEASE_CHECKLIST` + 附注 tag + push。

**固定成本**：`METHOD_VERSION` 定义在 `scripts/upgrade.py`（`ASSET`），
28 份 frontmatter 也在 `ASSET` → `method_assets.digest` 必变；
frontmatter 版本变化使 `installed_assets` 的 28 份副本**全部** drifted；
`P` 需一次性人批准 `M4 + M5 + M7`，并留新备份与回滚命令。
`ontology_digest` 是否变化取决于是否改到 `ontology.py` 的 `SOURCE_FILES`
（`ledger_feedback.py` / `scenario_matrix.py` 等）；若变化须一并重算 `ONTOLOGY.json/.md`。

## 七、明确不做 / 边界

- 未改任何 `ASSET` 文件：`docs/23`、`upgrade.py`、`templates/*`、
  28 份 frontmatter、`scripts/acceptance.py` 全部保持 v1.6.0 字节；
- 未升 `METHOD_VERSION`（仍 1.6.0）、未打新 tag、未发版；
- 未写 `P` 的账本（97 个在途改动与账本 mtime 不变）；
- 未执行 `registry/2`、未触碰早期数据治理线、未实现语义图；
- 未把 6 条 `open` 观察伪装成收敛；未回补 `ROADMAP-AUDIT-1.6.0.md` 原文。

## 八、取证数据（本轮起点，2026-11-18）

| 项 | 值 |
|---|---|
| 方法论仓 HEAD / tag | `a09a9d8`（= `origin/main`）/ `v1.6.0` → `a22f3eb` |
| `METHOD_VERSION` | `1.6.0` |
| `method_assets.digest` | `264026fdceb5…`（85 文件：8 专家 / 20 技能 / 29 脚本 / 4 模板 / 23 编号文档 / 1 标准） |
| `ontology_digest` | `e258dec16cef…` |
| 门禁 | `check.sh` 14 阶段全绿、243 测试、24 条三态不变量（23 pass + 1 na） |
| `acceptance/1` | `overall=pass`；`literal_drift` / `derived_reproducible` / `append_only` 三层全绿 |
| 三包 | `observations` 13 条（open 6 / closed 7 / `feedback_closed=5`）；`baseline` 12（10 / 2 / 2）；`post-v150` 15（13 / 2 / 1） |
| `P` | `verify = block=0 / pass=11 / na=1 / warn=0`、`upgrade_complete=true`、97 个在途改动 |

**下一轮批准点**：若决定直接实现 v1.7.0，需一并授权一次完整
「S1→S4→发版 + `P` 重绑」；在此之前本轮不产生任何不可逆后果。
