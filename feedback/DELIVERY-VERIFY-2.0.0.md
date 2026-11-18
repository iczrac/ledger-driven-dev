# v2.0.0 独立交付成果核实

> 性质：发版后的独立复放核实，**不复用发版流程的命令口径**；只读取证与临时副本，不写权威字节。
> 目标项目记作 `P`；核实只用一个干净的 `git archive v2.0.0` 树（186 文件、无 `.git`）+ 真实 `P`。

## 一、结论

**全部核实项通过：0 项不一致、0 项需修、0 项「声称完成但实际未做」。**

## 二、核心检验：tag 干净树复放

用 `git archive v2.0.0` 检出 186 文件干净树，只用该 tag 自带脚本重算并与 `P` 账本比对：

| 字段 | tag 干净树 | `P` 账本 | 结论 |
|---|---|---|---|
| `method_assets.digest` | `99856a1d9c346d0a…` | `99856a1d9c346d0a…` | **全等** |
| `ontology_digest` | `af5527160ddc8797…` | `af5527160ddc8797…` | **全等** |
| `method_version` | 2.0.0 | 2.0.0 | **全等** |

tag 干净树内另跑自带脚本，均通过：

- `acceptance.py --check --full` → `overall=pass`（14 项 checks 全 PASS）；
- **`upgrade.py --target P verify`（tag 自带升级器复验真实项目）** →
  `overall=pass`、`upgrade_complete=true`、12 pass/0 warn/0 fail。

这一步证明的不是「摘要抄对了」，而是**发布点自带的判定逻辑在 `P` 上仍成立**。

## 三、其余核实（独立口径）

- **主仓终态**：24 条不变量 `24 pass / 0 fail / 0 na`、`all_ok=true`、`all_active=true`
  （v1.8.0 为 23 pass + 1 na）；47 能力 code 全 4 段、0 个 5 段码、0 个前缀泄漏；
  level `L5:20/L3:22/L2:5` 不降级；`evidence_tier` `verified:20/declared:27`；
  `test_results` 绑定真实报告 182 用例、`activation.state=active`。
- **P1 满足**：20 个能力由真实 CI 报告（182 passed / 0 fail，JUnit 由项目 venv pytest 原生产出）
  升 `verified`；未伪造任何用例状态。
- **顺带治愈 E7**：`ontology.py check --target P` → `ok=true`（v1.8.0 为 `ok=false`）；
  4 段码与本体基数公理一致。
- **P2/P3 复测**：P2 `ontology check --target P` A2 可判定（`ok=true`、`drift_count=0`、
  31 条公理）；P3 `roadmap_consistency=pass`。**P1–P3 现已全部满足**，语义图 R4 的
  启动前置条件已具备（语义图本身不在本版范围，需独立立项）。
- **门禁与计数**：`bash scripts/check.sh` 16 阶段全绿（EXIT=0，含 275/275 单测、
  同步、卫生、本体层、验收契约、前置条件）；双写兼容（示例项目 `DEMO.DATA.READY.01`
  仍 4 段合法，同步阶段 `cmp` 一致）。
- **审计诚实**：S4 首次重绑后 activation 未同步（仍 unbound 且 reason 与事实相反），
  已产品化 `activation_from_report()` 并重做，两次重绑都在账本 `upgrade_log` append-only
  链上；`feedback/S4-2.0.0-REBIND.md` 第三节如实记录。
- **观察包 append-only**：权威三包 sha 全程不变
  （`observations 414506bd… / baseline 06d950c6… / post-v150 e8cf19ae…`）。
- **发布点与仓库完整性**：`git archive` 186 文件；`git fsck --no-reflogs` 无
  `missing`/`error`/`fatal`；`git ls-remote origin` 确认 `refs/heads/main=58b1149`、
  `refs/tags/v2.0.0=6419f99…` 均已推送；`tag v1.8.0` 对象本地与远端同为 `67b8ab65…`（未变）。

## 四、边界与未做

- 语义图 R4（Statement 再化 / K3 推理机 / 最小割集 RCA）未实现——P1–P3 虽已满足，
  但语义图属独立功能立项，本版（v2.0.0 registry/2）不含；
- `scale_budget` 阈值告警、6 条 `open` 观察按既有状态保留；
- registry 单项目结构本身未改（code 契约已修），若未来再引入跨项目码仍需守 `code_namespace` 契约。

## 五、提交

仅新增本文件（`feedback/`，`ZERO` 作用域，不在 `ASSET_GROUPS`）；**不改 ASSET 字节、
不改 `P` 账本、不升版本、不打新 tag**，因此 `tag v2.0.0` 的资产字节与 `58b1149`
保持一致，tag 复放结论不受影响。
