# 交付成果独立核实报告 —— 2026-11-18

> **性质**：一次性独立取证核实，**不是状态清单、不是第二事实源**。
> 观察状态权威源 `feedback/observations.jsonl`；发布状态权威源 `DECISION_LEDGER.json`；
> 发布自检权威源 `RELEASE_CHECKLIST.md`；验收判据权威源 `scripts/acceptance.py`。
> 目标项目一律记作 `P`；所有写盘动作以人批准为前提。
>
> **核实口径**：刻意不复用上一轮命令。核心是「从 `tag v1.6.0` 检出干净树复放」，
> 以及用独立 AST / 独立重放 / 独立 unittest 交叉验证既有检测器，避免自证。

## 一、核实结论

**14 组核实全部通过：0 项不一致、0 项需修复、0 项「声称完成但实际未做」。**

v1.6.0 交付基线**可信且可复放**。但「基线可信」与「可启动不可逆动作」是两件事：
本轮据此**不启动发版、不写 `P`**，理由见第八节。

## 二、V1 · 发布点复放检验（核心，此前从未执行）

用 `git archive v1.6.0` 检出一份**无 `.git` 的干净树**（161 文件），
用**该版本自带脚本**重算摘要，与当前 HEAD 工作树、`P` 的账本绑定值三方比对：

| 字段 | tag 干净树 | 当前 HEAD (`d6c2da8`) | `P` 账本 | 结论 |
|---|---|---|---|---|
| `method_assets.digest` | `264026fdceb5…`（85 文件） | `264026fdceb5…`（85 文件） | `264026fdceb5…`（85 文件） | 三方一致 |
| `ontology_digest` | `e258dec16cef…` | `e258dec16cef…` | `e258dec16cef…` | 三方一致 |
| `METHOD_VERSION` | `1.6.0` | `1.6.0` | `1.6.0` | 三方一致 |
| `installed_assets.digest` | — | — | `4e46f7330e17…`（28 份） | `asset_bundle verify` 独立复算 `ok=true`、`errors=[]`、28 份一致 |

**意义**：v1.6.0 发版要修的「`tag v1.5.0` 与实际规则不同」问题已彻底消除 ——
按 tag 复放得到的规则字节，就是 `P` 实际绑定并执行的规则字节。
tag 之后两个 commit（`a09a9d8`、`d6c2da8`）只改 4 个 `ZERO` 作用域文件
（`RELEASE_CHECKLIST.md`、`feedback/ROADMAP-AUDIT-1.6.0.md`、
`feedback/observations.jsonl`、`feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md`），
未触碰任何 `ASSET`，这正是摘要保持不变的原因。

## 三、V2 · 提交链与对象库

- `v1.6.0` 为**附注 tag**（`git cat-file -t` = `tag`），解引用 = `a22f3eb1…`；
  tag 说明 `v1.6.0: acceptance contract, append-only feedback, version unification`。
- 远端 tag 对象 `e426f9b4…`；`origin/main = d6c2da8… = 本地 HEAD`，无偏差、无 force 迹象。
- `git fsck --connectivity-only`：**19 个 dangling blob**，
  **无 `missing`、无 `error`** —— 本地暂存过的悬空对象，非损坏，如实记录不掩盖。
- 两个后续 commit 的 stat 与提交信息声明一致（`a09a9d8` 3 文件 / `+207−10`，
  `d6c2da8` 2 文件 / `+194−3`）。

## 四、V3 · 四份交付的真实性（含「声明未做」也要核实）

| 交付 | 核实方式 | 结果 |
|---|---|---|
| `feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md` | 关键词集合逐项命中 | 6471 字；C1/C2/C3、P1–P3、G1–G6、R1–R4、S1–S4、取代声明、append-only 纪律 **全部命中** |
| 仓外 `Ontology-Driven-Ledger-Architecture.md` | 关键词集合 + `git ls-files` | 头部状态行、「v1.6.0（实际发布，非语义图）」、P1–P3、依赖顺序节、修订注记、U 已执行 **全部命中**；两仓 `ls-files` 命中数均为 **0** → 该文件不在任何 git 仓库内，**未纳入任何提交**，如实说明 |
| `RELEASE_CHECKLIST.md` | 正则抓未勾项 + 节标题 | 未勾项恰 **3** 条且确实未勾；「依赖顺序修正」节与 `feedback_closed = 4` 声明均存在 |
| `feedback/ROADMAP-AUDIT-1.6.0.md` | `git log -- <file>` + `git diff d6c2da8^..d6c2da8` | 仅 `a09a9d8` 新增它，`d6c2da8` **未触碰** → 「不回补一次性报告」的声明属实 |

**反向核实（防止过度声明）**：契约文档声明「G1 尚未落成机器门禁」。
独立检查 `scripts/acceptance.py`：check id 恰为
`literal_drift / derived_reproducible / append_only` 三个，**无任何规划一致性断言** →
声明属实，没有把「打算做」写成「已做」。

## 五、V4 · 门禁、常量与观察包（独立口径）

- `bash scripts/check.sh`：**14 个阶段全部列出、0 FAIL**，`Ran 243 tests`；
  另用 `python3 -m unittest discover -s tests -p 'test_*.py'` 独立计数同为 **243 / OK**。
- **独立 AST 抽取**（不调用 `acceptance.py`）与检测器交叉比对：
  `PRE_UPGRADE=1`、`POST_UPGRADE=19`、`verify add() 去重 id=12`、
  `upgrade_complete 判据=9`、`METHOD_VERSION=1.6.0` —— **逐项一致**；
  检测器 `verify_ids` 12 条、`gate_ids` 9 条。
- **七轴独立核实**：`upgrade.py` docstring「版本七轴」7 条；
  `P` 的 `governance_meta` 七个绑定字段（`method_version` / `ledger_version` / `tools` /
  `method_assets` / `board_skeleton` / `installed_assets` / `ontology_digest`）齐备。
- **观察包 append-only 独立重放**（不调用 `acceptance.py`，在 `/tmp` 副本上连跑两次真实 export）：
  `13 → 17`（第 1 次 `existing 13 / collected 14 / added 4 / preserved_closed 7`）
  `→ 17`（第 2 次 `added 0`），两次文件 sha 同为 `7e62e2f6526a…`，
  17 个唯一 `obs_id`、7 条既有 closed 全保留；
  **权威观察包 sha `414506bddf87…` 未被触碰**，`check ok=true / total=13 / closed=7 / fc=5`。
- **待办未被伪装收敛**：13 条观察中 `open=6`（逐条仍在）、`closed=7`（均带
  `disposition`）、`obs_id` 无重复。

## 六、V5 · `P` 的边界与告警（未掩盖）

| 项 | 实测 |
|---|---|
| 在途改动 | **97** 条，列表指纹 `88415cc946f5…`；账本 mtime `Nov 18 18:24:19 2026` |
| 六段业务数据 | 21 决策 / 4 项目 / 3 工作项；`entries aaa41412…`、`capability_model 9ce706b7…`、`work_items f5013833…`、`history dbf629d5…`、`lessons ecee33a1…`、`access 00e70d95…` |
| 12 项 `verify` | `block=0 / pass=11 / na=1 / warn=0`、`upgrade_complete=true`（`evidence_rebaseline=na`） |
| 24 条不变量 | `23 pass + 1 na`（`test_results_binding_valid`）、`all_ok=true`、`all_active=false` |
| `na` 诚实性 | `activation` / `test_results` / `lifecycle` 全为 `null`，`access.agents` 长度为 0 |
| 三个设计内告警 | E7 `cardinality_contradiction`（`ontology.py check --target` `ok=false`）、`evidence_rebaseline=na`、`scale_budget project_files=49117` warn —— **全部如实存在，未被抹掉** |

## 七、两处口径说明（非缺陷，如实记录）

1. **首次 AST 比对出现 `★不一致`**：核实脚本把版本写成
   `constants.version`，而检测器实际把版本放在顶层 `method_version`
   （`constants` 里只有 5 个计数）。修正口径后 `1.6.0 = 1.6.0` 一致。
   这是**核实脚本的字段位置问题**，不涉及仓库任何文件。
2. **`project_files` 由 49078 → 49117**：方法论仓位于 `P` 的目录树内（实测 `YES`），
   新增 `feedback/` 证据文档（现 10 份）与 5 个升级备份目录（151 文件）
   使该计数自然增长；属规模预算的口径内现象，非数据异常。
   在途改动前 5 条均为既有文件，无本轮临时文件残留。

## 八、批准范围的第一性原理界定

用户本轮要求「批准相关工作，**但需做好交付成果核实**」。据此：

1. **核实通过 ≠ 授权不可逆动作**。核实证明的是「基线可信」；
   发版 + `P` 重绑会写账本、重装 28 份副本、产生不可变 tag 与远端推送，
   需要独立、明确的授权信号，不能由「核实」推导出来。
2. **技术前置仍缺**：v1.7.0 的 **P1**（`P` 至少一条能力由其真实 CI 报告升
   `verified`）是用户侧输入，Agent 无法代劳；C2 依赖顺序（先有证据再推理）
   依然成立。缺 P1 时语义图不能纳入。
3. **链条必须一次走完**：任何 `ASSET` 改动会立即让 `P` 的 `method_assets`
   绑定漂移，中间态比「不动」更糟。因此要么不启动，要么一次做完
   S1→S2→S3→S4→发版，不能分批试探。

**结论**：本轮把批准落实到用户明确要求的硬约束 —— 完成上述独立核实，
并把它固化为可复核证据；**不启动发版、不升版本、不写 `P`**。

## 九、本轮变更与边界

- 仅新增本文件（位于 `feedback/`，`ZERO` 作用域，不改变任何摘要）；
  本地提交并 push `main`，**不升版本 / 不打 tag / 不发版 / 不写 `P`**。
- 三项权威值保持：`method_assets 264026fd…`、`ontology_digest e258dec1…`、
  `METHOD_VERSION 1.6.0`；`tag v1.6.0` 仍指 `a22f3eb`。
- 已知且刻意保留的失配：`docs/23` 第七节仍写旧规划（修它属 `ASSET` 改动，
  须与下次功能实现攒成一次发版）；G1 要求届时升级为机器断言。

## 十、下一步（两个明确选项）

- **A｜启动 v1.7.0**：需一句明确授权「完整 S1→S4→发版 + `P` 重绑」；
  并提供 P1 所需的 `P` 真实 CI 报告。缺报告时只能发「一致性与可适配性」
  收敛版（R1–R3，不含语义图）。
- **B｜继续零成本工作**：例如把 G1 的规划一致性断言写成 S2 规格细案、
  或为 P1 设计报告契约。只要不落 `ASSET`，就不需要发版与重绑。

> 本报告不修改 `ROADMAP-AUDIT-1.6.0.md` 与
> `ACCEPTANCE-1.7.0-PRECONDITIONS.md` 的任何既有结论，按 append-only
> 证据纪律以新增文件方式记录。
