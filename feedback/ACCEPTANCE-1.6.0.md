# S2 验收契约 —— 先定义「什么算修好」

> 本文件是**验收定义与红灯证据**，不参与门禁计数，不是第二事实源。
> 位置：S1 固化升级现场证据（本地 commit `dad503c`）之后，S3 改权威源之前。
> 纪律：S2 只写「会失败的回归 + 门禁断言」，**不改任何实现**。

## 一、为什么是这一序列

第一性原理裁决把「提交证据 or 开工 v1.6.0」判成严格四步：

| 步 | 动作 | 状态 |
|---|---|---|
| S1 | 固化升级前后观察证据（本地 commit，不 push / 不 tag） | 已完成 |
| **S2** | **先写「先失败」的回归 + 门禁断言（定义验收）** | **本文件** |
| S3 | 改权威源让三层验收转绿 | 待批准 |
| S4 | 重新人批准目标项目 M5 + M7 重绑 | 待批准 |

S2 与「本体先于 `registry/2`」同构：先定义什么合法，再改数据 / 实现。
若先改正文再补断言，就无法证明门禁真的能拦住这类漂移。

## 二、验收契约的三层（`acceptance/1`）

新增只读检测器 `scripts/acceptance.py`，输出结构化报告，`--check` 未达标返回 1。

| 层 | id | 判定 | 作用 |
|---|---|---|---|
| L1 | `literal_drift` | 手写源与派生文件里的计数 == `upgrade.py` 代码常量 | 拦住「只改 frontmatter version、不同步正文」 |
| L2 | `derived_reproducible` | 3 份 `docs/generated/` 派生文件可由既有 `--emit-md` 复算 | 禁止手改派生文件绕过 L1 |
| L3 | `append_only` | 重复导出不销毁既有证据、按 `obs_id` 去重、连续两次幂等 | 修「第 19 步覆盖写」与「升级后发现的新摩擦无法补录」的同一根因 |

**期望值不手写**：`scripts/upgrade.py` 的 AST 抽取
`METHOD_VERSION` / `PRE_UPGRADE` 长度 / `POST_UPGRADE` 长度 /
`verify()` 内 `add()` 的去重 id / `c["id"] in (...)` 判据元组，得

```
axis=7   pre_steps=1   post_steps=19   verify_checks=12   gate_criteria=9
verify_ids 12 个  ·  gate_ids 9 个
```

第七轴清单 `AXIS_KEYS` 是契约声明，自检要求每个键都被 `upgrade.py` 真实消费，
避免它退化成凭空手写的第二份清单。检测器自身豁免字面量扫描，避免自指级联。

**两类误报已显式排除**（有负向绿灯回归守着）：
「这一步 / 下一步 / 1 步升级前基线」「场景矩阵十轴」
「`scenario-preflight/1` 的 14 项检查」以及「第 12–18 步」区间。
含版本演进词（`扩到` / `→` / `起` / `新增的`）的历史陈述归入 `review` 不阻断，
但同一棵树里无版本限定的当前式陈述仍必须硬失败。

## 三、当前红灯证据（S2 预期，不得绕过）

`python3 scripts/acceptance.py --check --full` → `rc=1`，`overall=fail`。

### L1：`literal_drift` FAIL —— 27 处 / 15 个文件

| 文件组 | 文件 | 处数 | 漂移类型 |
|---|---|---:|---|
| 权威资产 | `experts/platform-steward/EXPERT.md` | 3 | 六轴 ×2 / 18 步 |
| 权威资产 | `skills/ledger-upgrade/SKILL.md` | 6 | 六轴 ×2 / 11 项 ×2 / 18 步 / 八项 |
| 权威资产 | `skills/agent-gate/SKILL.md` | 1 | 18 步 |
| 手写文档 | `docs/12-专家路由.md` | 1 | 18 步 |
| 手写文档 | `docs/14-场景矩阵.md` | 1 | 18 步 |
| 手写文档 | `docs/16-升级与迁移.md` | 4 | 18 步 ×2 / 11 项 / 八项 |
| 手写文档 | `docs/17-多Agent接入控制.md` | 1 | 18 步 |
| 手写文档 | `docs/18-规模化与版面契约.md` | 3 | 11 项 ×2 / 18 步 |
| 手写文档 | `docs/19-专家与技能可用.md` | 1 | 八项（无版本限定的当前式陈述） |
| 派生文件 | `docs/generated/FILE_LAYOUT.md` | 1 | 六轴 |
| 派生文件 | `docs/generated/SCENARIO_MATRIX.md` | 1 | 18 步 |
| 生成器源 | `scripts/upgrade.py` | 1 | 六轴（docstring） |
| 生成器源 | `scripts/file_layout.py` | 1 | 六轴（`purpose` 文本） |
| 生成器源 | `scripts/route_expert.py` | 1 | 六轴（注释） |
| 生成器源 | `scripts/scenario_matrix.py` | 1 | 18 步（场景文本） |

`review`（历史演进陈述，10 处，不阻断）：
`docs/14-场景矩阵.md:121` 的版本演进行 6 处、
`docs/19-专家与技能可用.md:84-85` 的 v1.2.0 边界变化 4 处。
S3 需人工确认这些行是否补上版本限定，避免读者误读成当前值。

**关键发现（S2 相对复核结论的增量）**：原先只数出 11 个 `.md` 文件命中；
检测器把扫描范围扩到 `scripts/*.py` 后，发现 **2 份派生文件的漂移源头在 4 个生成器源码里**。
因此 S3 **不能批量替换派生 `.md`**：只改派生文件会让 L2 立刻变红。
正确顺序是「改生成器源文本 → 重跑 `--emit-md` 重算派生文件 → L1 与 L2 同时转绿」。

### L2：`derived_reproducible` PASS

`FILE_LAYOUT.md` / `SCENARIO_MATRIX.md` / `TEST_MODULES.md` 当前均可由
`file_layout.py` / `scenario_matrix.py` / `test_modules.py` 复算。
这一层现在是绿的，正是它把 S3 的修法约束成「改源头、重算派生」。

### L3：`append_only` FAIL

在临时副本上连跑两次真实 `ledger_feedback.py export --out <同一文件> --apply`：

```
观察包 13 → 10 行
append-only 违例：13 条既有观察消失
已收敛 triage 证据被销毁：4 条（含 OBS-99e62022038e 本体漂移回归）
重复导出行数少于原包：既有观察未保留
```

当前 `write_lines()` 是覆盖写，`cmd_export()` 不读既有行。
S3 应统一修 `ledger_feedback.py` 的写入语义（merge + `obs_id` 幂等去重），
而不是只改 `POST_UPGRADE` 第 19 步的命令字符串——三条现场 note 同源。

## 四、S3 的转绿条件（可机器判定）

1. `python3 scripts/acceptance.py --check` 返回 0，`overall=pass`；
2. L1 `drift_count=0`（27 处全部对齐，或明确改写为不带硬编码计数的表述）；
3. L2 三份派生文件仍全部 `reproducible=true`（证明改的是源头）；
4. L3 重复导出后 13 条既有观察全部保留、4 条已收敛证据字段不变、
   无重复 `obs_id`、连续两次结果一致；
5. 10 处 `review` 逐条人工确认并留痕；
6. `bash scripts/check.sh` 14 阶段全绿（含新增的「验收契约」阶段）。

## 五、S4 的隐藏成本（已实证，非推测）

`method_assets.digest` 由 84 个文件逐字节决定。S2 只新增一个检测器脚本，
摘要已从 `0bd06f8274e…` → `3ed7a4488b9e…`（85 文件，scripts 28 → 29）。

- 目标项目账本仍绑定 `0bd06f8274e…`，因此其 `verify.method_assets` 现在会 `warn`；
- `ontology_digest` 仍是 `c399ff180ebc06c8…` **未变**：`ontology.py` 的
  `SOURCE_FILES` 是固定 6 文件元组，新增脚本不触发第七轴漂移；
- S3 改 15 个文件会再次改变摘要，所以 S4 必须在 S3 完成后**一次性**重新
  人批准 M5 + 重装 M7 + 复验，不要在 S2 阶段提前重绑（会形成第三次写盘）。

## 六、本轮明确不做

- 不改那 27 处正文 / 不批量替换数字（留给 S3）；
- 不改 `ledger_feedback.py` 的写入语义（留给 S3）；
- 不改 `POST_UPGRADE` 定义与步数（`test_platform_contract.py` 的 19 / 1 断言保持）；
- 不条件化第 1 / 2 / 15 步 SOP、不补 M8 未触发时的 `activation` 占位
  （三条现场 note 中的另外两条，留 v1.6.0 后续）；
- 不碰目标项目任何文件、不重绑账本、不 push、不打 tag；
- 检测器与自测不写入 `docs/[0-9][0-9]-*.md`，避免把红灯中间态写进权威文档编号体系。

## 七、复现命令

```bash
python3 scripts/acceptance.py --check --full      # 红灯明细，rc=1
python3 scripts/acceptance.py --json              # acceptance/1 结构化报告
python3 -m unittest discover -s tests -p 'test_acceptance.py' -v   # 16 个绿灯自测
bash scripts/check.sh                            # 14 阶段，最后一项预期红灯
```

相关文档：[22 · 反向回流](../docs/22-反向回流.md)、
[23 · 本体投影](../docs/23-本体投影.md)、
[16 · 升级与迁移](../docs/16-升级与迁移.md)、
[升级前后观察 diff](UPGRADE-DIFF-1.5.0.md)。
