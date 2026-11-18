# v1.7.0 独立交付成果核实

> 性质：发版后的独立复放核实，**不复用发版流程里的命令口径**。
> 目标项目一律记作 `P`；核实只读取证与临时副本，不写任何权威字节。

## 一、结论

**全部核实项通过：0 项不一致、0 项需修、0 项「声称完成但实际未做」。**

核心结论依旧是治理系统的唯一目的：**按 tag 复放出来的规则字节，就是 `P`
实际执行的规则字节**。本次还额外验证了「tag 自带的升级器可以直接复验 `P`」，
而不只是比对摘要。

## 二、核心检验：tag 干净树复放

用 `git archive v1.7.0` 检出 **168 文件**干净树（无 `.git`），**只用该版本自带的
脚本**重算，与当前 HEAD、`P` 账本三方比对：

| 字段 | tag 干净树 | 当前 HEAD | `P` 账本 | 结论 |
|---|---|---|---|---|
| `method_assets` | `d5c9109c…`（85 文件） | `d5c9109c…`（85） | `d5c9109c…`（85） | **全等** |
| `ontology_digest` | `e258dec1…` | `e258dec1…` | `e258dec1…` | **全等**（`SOURCE_FILES` 未改） |
| `installed_assets` | `ddb88625…`（28 份） | — | `ddb88625…`（28） | **全等** |
| `METHOD_VERSION` | `1.7.0` | `1.7.0` | `1.7.0` | **全等** |

干净树内另跑自带脚本，均通过：

- `upgrade.py check` → 3 工具 / 8 迁移 / 1 步基线 / **19 步**流程；
- `acceptance.py --check --json` → `overall=pass`、`scope=full`、
  六项 `pass`（`literal_drift` / `derived_reproducible` / `append_only` /
  `roadmap_consistency` / `conditional_sop` / `activation_placeholder`）；
- **`upgrade.py --target P verify --json`（tag 自带升级器复验真实项目）** →
  `overall=pass`、`upgrade_complete=true`、`block=0 / pass=11 / na=1 / warn=0`。

这一步证明的不是「摘要抄对了」，而是**发布点自带的判定逻辑在 `P` 上仍然成立**。

## 三、其余核实（独立口径）

**门禁与计数**：`bash scripts/check.sh` **15/15 全绿**、`FAIL=0`；
`unittest discover -s tests` **249/249**；`acceptance/1 overall=pass`、
`literal_drift drift=0`（扫描 85 文件、历史复核 10 处）、3 份派生可复算。

**防过度声明**：4 份证据文档（S1 / S2 / S3 / 发版报告）齐备；发版报告含
G6 的 P1–P3 显式记录与「语义图顺延」；`docs/23` 第七节的
「v1.6.0 才做语义图」已消失；`CHANGELOG` 有 `## [1.7.0]`；
`RELEASE_CHECKLIST` 的 `registry/2` 仍为**未勾**；S2 红灯证据原文
（「13 阶段绿 / 2 阶段红」）保留，未被回补成绿灯。

**观察包 append-only（在 tag 干净树副本上真实执行）**：权威包 13 条
（`open 6 / closed 7`）、7 条已收敛证据全部带 `disposition`；三包 sha
不变（`observations 414506bd…` / `baseline 06d950c6…` / `post-v150 e8cf19ae…`）。
`export` 连跑两次 `13 → 23 → 23`，第二次 `added=0`、两次 sha 同为
`14c2a4ac…`、7 条 `closed` 的 `disposition` 逐条保留。

**`P` 边界**：24 条三态不变量 `23 pass + 1 na`（`test_results_binding_valid`）、
`all_ok=true` / `all_active=false`；`governance_meta.activation` =
`evidence-activation/1 · state=unbound`；`test_results` 仍 `null`（未伪造报告）；
`upgrade_log` 末条 `seq=6`；97 个在途改动数量未变；六段业务 digest 与 S4
写盘前一致；E7 `cardinality_contradiction` 仍在（`ok=false`），但第七轴
`binding=pass`；`evidence_rebaseline=na` 与 `scale_budget` 阈值告警**均未被掩盖**。

**发布点与仓库完整性**：`git fsck --no-reflogs` 无 `missing` / `error` / `fatal`；
`HEAD = origin/main = v1.7.0^{commit} = ca1f49e`；附注 tag 对象
`3fe13763…`；`tag v1.6.0` 对象本地与远端同为 `e426f9b4…`（**未变**）；
`git ls-remote` 确认 `refs/heads/main` 与 `refs/tags/v1.7.0` 均已推送。
S1 / S2 两份一次性证据文档分别从其提交点到 `ca1f49e` 的 `git diff --stat`
**均为空**（未被回补）；四份新报告脱敏 CLEAN、无绝对路径残留、无断链
（门禁卫生阶段全绿）。

## 四、三处口径说明（非仓库缺陷，已如实记录）

首次核实脚本报出 3 项 `false`，逐项复核后确认都是**脚本/命令口径**，不涉及
任何仓库文件：

1. **S2 红灯关键词**：文档原文是「**13 阶段绿 / 2 阶段红**」，脚本查的是
   「13 绿 / 2 红」，字符串不匹配；红灯记录本身完整存在。
2. **S1/S2 原文未回补**：脚本把两个文件合并对 `54f53e2` 做 `diff --stat`，
   而 S2 文档是在 `7764419` 才新增的，被算成「有差异」。改为分别从各自
   提交点比对后，**两者 diff 均为空**。
3. **`v1.6.0` tag 未变**：`subprocess.check_output` 返回 `bytes`，脚本拿它与
   `str` 常量比较，恒为 false。decode 后本地与远端同为 `e426f9b4…`，
   确认未变。

修正口径后全部转绿；三处均不需要改动仓库。

## 五、边界与未做（诚实清单）

- P1 / P2 仍未满足（无 `P` 的真实 CI 报告、A2 仍 Unknown），**语义图顺延**，
  本版是收敛版不是语义图版；P3 已由本版 G1 机器断言满足；
- 未执行 `registry/2`（破坏性数据契约，不得由 Agent 自动执行）；
- 未在 `P` 上跑完整 `post_upgrade` SOP（本版只做重绑与复验），条件化路径
  由门禁的空 fixture 负向回归证明；
- E7、`evidence_rebaseline=na`、`scale_budget` 阈值三项设计内告警未掩盖；
- 6 条 `open` 观察仍 open，未伪装成收敛。

## 六、提交

仅新增本文件（`feedback/`，`ZERO` 作用域，不在 `ASSET_GROUPS`），随提交 push 到
`origin/main`。**不改任何 ASSET 字节、不改 `P` 账本、不升版本、不打新 tag**；
因此 `tag v1.7.0` 的资产字节与 `ca1f49e` 完全一致，tag 复放结论不受影响。
`v1.7.0` 与 `origin/main` 的关系同 v1.6.0：tag 指向发版点，核实报告是
发布点之后一个零摘要成本的信息面提交。
