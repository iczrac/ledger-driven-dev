# S3 结案：验收契约三层转绿

> 本文件是 **S3 的转绿证据与结案记录**，不参与门禁计数，不是第二事实源。
> 红灯定义见 [S2 验收契约](ACCEPTANCE-1.6.0.md)（历史证据，保留不改）。
> 序列：S1 固化证据 → S2 先写会失败的回归 → **S3 改权威源让验收转绿** → S4 主仓重绑。
> 纪律：S3 只改方法论仓库；本地提交，不 push、不打 tag、不升 `METHOD_VERSION`。

## 一、契约六条转绿条件逐条核对

| # | 条件 | 结果 | 机器证据 |
|---|---|---|---|
| 1 | `acceptance.py --check` 返回 0、`overall=pass` | ✅ | `rc=0`，`acceptance/1` |
| 2 | L1 `drift_count=0` | ✅ | 扫描 85 文件，漂移 **0** 处 |
| 3 | L2 三份派生文件 `reproducible=true` | ✅ | `FILE_LAYOUT.md` / `SCENARIO_MATRIX.md` / `TEST_MODULES.md` 全 OK |
| 4 | L3 既有证据全保留 / 去重 / 幂等 | ✅ | 观察包 **13 → 23** 行，4 条已收敛 triage 证据逐字段不变，无重复 `obs_id`，连跑两次结果一致 |
| 5 | 10 处 `review` 逐条人工确认留痕 | ✅ | 见第三节 |
| 6 | `bash scripts/check.sh` 14 阶段全绿 | ✅ | 14/14 PASS，**243/243** 测试通过，24/24 三态不变量 |

代码常量仍全部由 `upgrade.py` 的 AST 抽取，未手写：
`axis=7 / pre_steps=1 / post_steps=19 / verify_checks=12 / gate_criteria=9`，
12 个 verify id、9 个判据 id。

## 二、27 处过期字面量的修法

按 S2 的关键增量发现，**先改 4 个生成器源，再由生成器重算派生文件**，
没有手改任何 `docs/generated/` 文件。

| 组 | 文件 | 修法 |
|---|---|---|
| 生成器源（4） | `scripts/upgrade.py` docstring、`scripts/file_layout.py` purpose、`scripts/route_expert.py` 注释、`scripts/scenario_matrix.py` 场景文本 | 六轴 → 七轴（并补 `ontology_digest` 轴说明）、18 步 → 19 步 |
| 权威资产（3） | `experts/platform-steward/EXPERT.md`、`skills/ledger-upgrade/SKILL.md`、`skills/agent-gate/SKILL.md` | 对齐七轴 / 19 步 / 12 项 / 九项；`ledger-upgrade` 的版本轴表补第 7 行 `ontology_digest` |
| 手写文档（6） | `docs/12`、`14`、`16`、`17`、`18`、`19` | 对齐计数；`docs/16` 的 12 项名单补「本体投影摘要」、九项判据补「本体投影」 |
| 派生文件（2） | `FILE_LAYOUT.md`、`SCENARIO_MATRIX.md` | **由 `file_layout.py` / `scenario_matrix.py` 的 `--emit-md` 重算** |

`docs/19:91` 原为历史段落里唯一无版本限定的当前式陈述，改写为
「v1.2.0 起要求 8 项关键检查全 pass；v1.5.0 起为九项判据（以 `upgrade.py` 常量为准）」，
历史值归 `review`，当前值与代码常量一致。

**根因治理**（避免下次发版重演）：

- `scripts/upgrade.py` docstring 与 `docs/16` 明确「正文计数以代码常量为准，
  由 `scripts/acceptance.py` 逐行校验；升级时先改常量，再改正文与生成器源并重算派生」；
- `docs/22` 补上观察包的 append-only 契约，并说明 `POST_UPGRADE` 末步现在可以安全
  指向同一个观察包，不必另开临时文件（S1 升级现场曾因此绕开第 19 步）。

## 三、10 处历史复核逐条确认（条件 5 留痕）

结论统一为 **「保留真实历史值 + 补版本边界」**：这些行记录的是 v1.1.0 / v1.2.0
当时的状态，改成当前值会伪造历史；但原文里的「现」「扩到」容易被误读成当前值。

| 文件:行 | 命中 | 判定 | 处理 |
|---|---|---|---|
| `docs/14-场景矩阵.md:121` | `axis 3 / 5 / 6 → 7` | 版本演进表「版本三轴（v1.1.0 起五轴，v1.2.0 起六轴）」 | 保留三档历史值，补「v1.5.0 起七轴」 |
| `docs/14-场景矩阵.md:121` | `post_steps 8 / 11 / 18 → 19` | 同上表「8 步（v1.1.0 11 步，现 18 步）」 | **删掉会误导的「现」**，改为「v1.2.0 18 步；当前步数以 `upgrade.py` 为准」 |
| `docs/19-专家与技能可用.md:87` | `axis 5 / 6 → 7` | v1.2.0 引入 M7 时的「从五轴扩到六轴」 | 保留，段落前加「本节是 v1.2.0 历史快照，以下均为当时值」 |
| `docs/19-专家与技能可用.md:88` | `post_steps 18 → 19`、`verify_checks 11 → 12` | 同上历史快照的 `11 → 18 步`、`9 → 11 项` | 保留，受同一版本边界说明覆盖 |
| `docs/19-专家与技能可用.md:94` | `gate_criteria 8 → 9` | 原「要求 8 项关键检查全 pass」 | 改为「v1.2.0 起要求 8 项；v1.5.0 起为九项判据」 |

检测器当前 `review_count=10`，全部有版本限定，**无一处被硬失败掩盖**。

## 四、L3 根因：观察包 append-only 写入契约

`scripts/ledger_feedback.py` 新增 `merge_observations()` 纯函数与 `export_payload()`：

- 写盘路径先 `read_lines()` 读既有行，再按 `obs_id` 幂等合并，
  **既有行优先**（已收敛 triage 的 `status` / `disposition` / `artifact_ref` / `reason` /
  `approved_by` 不会被新采集的 open 行覆盖），只追加新 id，保持插入顺序确定性；
- `triage` 仍使用 `write_lines()` 整体重写——那是有意改写单条状态，语义不同；
- 返回的 `count` / `sha256` / `observations` 反映**实际写入结果**，附带 `merge` 统计
  （`existing_rows` / `collected_rows` / `added_rows` / `preserved_closed`）；
  dry-run 与无 `--out` 的行为不变。

新增 4 个回归（`tests/meta/test_feedback.py`）：既有 closed 行不被覆盖、合并幂等且顺序稳定、
真实 `cmd_export` 保留证据且连续两次逐行一致、文件不存在时正常创建。
三包权威观察 **一字未写**，sha 与闭环计数与 S1/S2 完全一致：

```
observations.jsonl  e0b313efab94a4c7…  13 行 / closed 4 / feedback_closed 4
baseline.jsonl      06d950c6792efc56…  12 行 / closed 2 / feedback_closed 2
post-v150.jsonl     e8cf19aeb923e7d5…  15 行 / closed 2 / feedback_closed 1
```

## 五、S2 未预见的三项增量成本（如实记录）

1. **第七轴 digest 必变**。`ontology.py` 的 `SOURCE_FILES` 含
   `scripts/ledger_feedback.py` 与 `scripts/scenario_matrix.py`（均为 `value_domains` 来源）。
   S2 契约第五节说「新增脚本不触发第七轴漂移」在 S2 成立，但 S3 改的是 **源文件本身**，
   因此必须重算 `ONTOLOGY.json` / `ONTOLOGY.md`，
   `ontology_digest` 由 `c399ff180ebc06c8…` → `e258dec16ceff2bb…`。
   `ontology.py check` 现为 `ok=true`。
2. **`installed_assets` 也转 warn**。改过的 3 份权威资产在主仓 `.workbuddy/` 的
   只读部署副本字节已旧，所以 S4 的 M7 必须重装并重签 manifest，不只是 M5。
3. **门禁自身有一处误判**。`stage_scenarios` 是唯一用
   `git diff --exit-code -- docs/generated/SCENARIO_MATRIX.md` 检查派生的阶段：
   它比较的是「与上次提交是否一致」，而合法重算必然产生 diff，于是把
   「改生成器源 + 重算」误判成「手改派生文件」（`stage_layout` / `stage_test_modules`
   用的才是正确的「临时重算 + `cmp`」口径）。已统一口径，门禁从此对该场景纯只读。

## 六、S4 成本实证（目标项目，全程只读）

`method_assets.digest` 由 85 个文件逐字节决定；本轮 21 个文件变更后：

| 项 | 主仓账本当前值 | 权威源新值 |
|---|---|---|
| `method_assets` | `0bd06f8274e0…` | `9493bc9ee693…` |
| `ontology_digest` | `c399ff180ebc…` | `e258dec16cef…` |
| `method_version` | `1.5.0` | `1.5.0`（未升） |

`upgrade.py --target P verify --json` →
`block=0 / pass=8 / warn=3 / na=1`，`upgrade_complete=false`：

```
method_assets       warn  资产漂移
installed_assets    warn  3 份副本内容与权威源不一致
ontology_binding    warn  本体投影漂移
evidence_rebaseline na    无实测报告，能力仍为 declared
```

`na` 不阻止升级完成判定（`upgrade_complete` 只把 `pass` / `na` 视为达标）。
S4 建议处方：人批准 `apply` 触发 M5 重绑两个摘要 → M7 重装 28 份只读副本并重写
`ASSET_MANIFEST.json` → 复验期望 `pass=11 / na=1 / warn=0`、`upgrade_complete=true`。

主仓 **一字未写**：97 个在途改动数量不变，`DECISION_LEDGER.json` mtime 仍为
`Nov 18 15:20:14 2026`。

## 七、本轮明确不做（及理由）

- **不升 `METHOD_VERSION`、不打 tag、不 push、不改 28 份 frontmatter**。
  S3 是「本地未发布态的规则修正」，版本提升与 28 份 frontmatter / CHANGELOG / tag
  属于发版动作，应与 S4 之后统一发布一起做，避免把版本提升与摘要重绑混在一次写盘里。
  ⚠️ **风险提示**：`tag v1.5.0` 指向 `dffc0d4`，当前 HEAD 的资产字节已不同，
  因此 **S4 完成后必须统一升版本 + 打 tag**，否则会出现「同版本、不同规则」。
- **不条件化 `POST_UPGRADE` 第 1 / 2 / 15 步 SOP、不补 M8 未触发时的 `activation` 占位**：
  三条现场 note 中剩余的两条，留 v1.6.0 后续；改它们会动 19 步定义与
  `test_platform_contract.py` 的 19 / 1 断言，超出 S2 契约的转绿范围。
- 不改 `POST_UPGRADE` / `PRE_UPGRADE` 定义与步数，不做 `registry/2`，不碰目标项目。
- 检测器与结案报告不写入 `docs/[0-9][0-9]-*.md` 的红灯中间态。

## 八、复现命令与回滚

```bash
python3 scripts/acceptance.py --check --full     # 三层全绿，rc=0
python3 scripts/acceptance.py --json             # acceptance/1 结构化报告
bash scripts/check.sh                            # 14 阶段全绿，243/243
python3 scripts/ontology.py check --json         # 第七轴派生同步 ok=true
python3 scripts/method_assets.py --json          # 85 文件整包摘要
git reset --hard c6a86ce                         # 回滚到 S2（本地未 push）
```

相关文档：[S2 验收契约](ACCEPTANCE-1.6.0.md)、
[升级前后观察 diff](UPGRADE-DIFF-1.5.0.md)、
[22 · 反向回流](../docs/22-反向回流.md)、
[16 · 升级与迁移](../docs/16-升级与迁移.md)、
[23 · 本体投影](../docs/23-本体投影.md)。
