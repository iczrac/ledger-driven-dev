# v1.7.0 发版结案报告（一致性与可适配性收敛版）

> 目标项目一律记作 `P`；所有写盘动作均以人批准为前提。
> 本报告只记录事实与可复放命令，不替代任何权威源。

## 一、决策（第一性原理）

用户授权落实 A（完整 S1 → S2 → S3 → S4 → 发版 + `P` 重绑），并附带 P1 真实
CI 报告；**缺报告则只能发「一致性与可适配性」收敛版**。取证显示 P1–P3 在
起点全部未满足（见 `feedback/S1-1.7.0-BASELINE.md`），故本版只交付 R1–R3，
语义图顺延。

| 候选 | 判断 | 理由 |
|---|---|---|
| 用方法论仓自身 249 个测试给 `P` 刷 `verified` | **否决** | 张冠李戴即第二事实源；`docs/11` 的 `verified_tier_traceable` / `verified_tier_not_premature` 会抓伪造 |
| 先建 K3 推理机再补证据 | **否决** | A2 要求 L3+ 有新鲜 `verified` 证据、G3 规定含 Unknown 不得派生 `pass`；零事实上是空集推理 |
| 为改一句 `docs/23` 单独发一版 | **否决** | 整包摘要绑定使任何 ASSET 改动都触发一次发版 + 主仓重绑，零散发版被明令禁止 |
| **合并为一次收敛版发版** | **采纳** | S1–S4 证据齐备、15/15 门禁全绿、diff 收敛在 R1–R3 |

## 二、G6：启动前置条件与范围裁剪（发版时点显式记录）

| 前置 | 起点 | 发版时点 | 证据 | 对范围的影响 |
|---|---|---|---|---|
| **P1** `P` 至少一条能力由真实 CI 报告升 `verified` | 未满足 | **仍未满足** | `P/tests/` 与 `governance/test_report.json` 均不存在；47 能力仍 `declared` | R4 语义图不纳入；不写 `verified` |
| **P2** `ontology.py check --target P` 中 A2 可判定 | 未满足 | **仍未满足** | 输出仅 E7 `cardinality_contradiction`，A2 仍落 Unknown | 不做依赖推理 / 置信度传播 / 最小割集 RCA |
| **P3** 规划一致性机器断言上线 | 未满足 | **本版已满足** | `acceptance.py` 第四层 `roadmap_consistency` PASS | 失配不再靠人眼复核挂着 |

**裁掉**：R4 语义图（Statement 再化 / K3 推理机 / 最小割集 RCA）。
**保留**：R1 规划一致性、R2 条件化 SOP、R3 M8 `activation` 占位。
`feedback_closed` 仍为 5，6 条 `open` 观察未被伪装成收敛；`registry/2`
保持未执行。P1 所需的真实 CI 报告是唯一无法由 Agent 代劳的用户侧输入。

## 三、序列与提交锚点

| 步骤 | 提交 | 内容 |
|---|---|---|
| S1 | `54f53e2` | 固化基线，未 push / 未打 tag |
| S2 | `7764419` | G1–G3 机器断言 + 第 15 门禁阶段，刻意红灯 `13 绿 / 2 红` |
| S3 + 发版 A | **`1d5294a`** | R1–R3、`METHOD_VERSION` 1.7.0、28 份 frontmatter、`CHANGELOG` / 清单正文（36 文件），`method_assets → d5c9109c…` |
| S4 | 不产生方法论仓提交 | 人批准重绑 `P`，备份 `20261118T135753Z-ed92ea36` |
| 发版 B | 本文件所在提交 | 本报告 + `RELEASE_CHECKLIST.md` 两项勾选（**均 `ZERO` 作用域**） |

A 与 B 的划分沿用 v1.6.0：A 决定 `P` 绑定的资产字节；B 只改 `feedback/`
与根级清单，因此 `tag v1.7.0` 指向的 ASSET 字节与 A 完全一致。
S4 的 `apply` 读的是**本地**方法论仓（已含 1.7.0 字节），故可在打 tag 之前
执行，序列仍满足「S4 在发版前」，且不产生第二次重绑。

## 四、写盘预演与实际结果

只读 `plan`（写盘前）：`from 1.6.0 → to 1.7.0`、`noop=false`、`risk=medium`、
`blocks=[]`、迁移 **M4-method-version + M5-method-assets + M7-asset-install +
M8-work-panel**、3 个工具副本 `in-sync`、看板 `match=true`、
`installed.missing=0 / drifted=28 / stale_protected=0`、`post_upgrade` 19 步。

**与预估的差别（如实记录）**：`feedback/ACCEPTANCE-1.7.0-PRECONDITIONS.md`
第六节按 v1.6.0 的固定成本估的是 `M4 + M5 + M7` 三条；本版 R3 把
`governance_meta.activation` 缺失纳入 M8 触发条件，而 `P` 从无该字段，
因此 `plan()` 额外列出 M8 —— 这正是 G3「无报告时账本写入显式 activation
占位」在真实项目上的落点，不是计划外改动。写盘按四条如实执行：

```bash
python3 scripts/upgrade.py --target P apply \
    --approved-by '用户授权-2026-11-18-v1.7.0-A' --json
```

- 新备份 `20261118T135753Z-ed92ea36`（35 文件、`created=0`）
- `upgrade_log` 追加 `seq=6`：`1.6.0 → 1.7.0`、四条迁移、`risk=medium`

### 绑定值前后对比

| 字段 | 发版前 | 发版后 |
|---|---|---|
| `method_version` | `1.6.0` | **`1.7.0`** |
| `method_assets` | `264026fd…`（85 文件） | **`d5c9109c…`**（85 文件） |
| `installed_assets` | `4e46f733…`（28 份） | **`ddb88625…`**（28 份） |
| `ontology_digest` | `e258dec1…` | `e258dec1…`（**未变**：`SOURCE_FILES` 未改） |
| `board_skeleton` | `735bcd09…` | `735bcd09…`（未变） |
| `governance_meta.activation` | 缺失 | `evidence-activation/1` · `state=unbound` · `all_active=false` |
| `test_results` | `null` | `null`（**未伪造报告**） |

### 写盘半径

35 个备份文件中 **31 个内容变化、4 个逐字节未变、0 缺失**：
`governance/` 的账本 / 看板 / `ASSET_MANIFEST.json` + 28 份 `.workbuddy/`
只读副本；未变的是 `registry.json` 与 3 个工具副本（`in-sync`）。

## 五、复验结果

| 检查 | 结果 |
|---|---|
| `upgrade.py verify` | `block=0 / pass=11 / na=1 / warn=0`，`upgrade_complete=true` |
| `upgrade.py plan`（连跑两次） | `noop=true / risk=none / migrations=[] / blocks=0` |
| 24 条三态不变量 | `23 pass + 1 na`、`all_ok=true`、`--strict rc=0`、`all_active=false` |
| `asset_bundle verify` | 28 份 ok、摘要 `ddb88625…`、`errors=[]` |
| `route_expert --check-assets` | `ok=true` |
| `ontology.py check --target P` | `target.binding=pass`、`drift=0`；`ok=false` 仅因 E7（见下） |
| 看板骨架 / 节点工作台 / 布局 / 预检 | `match` / `ok` / `governed` / `blocks=0` |
| 方法论仓门禁 | `check.sh` **15/15 全绿**、**249/249 测试**、`acceptance/1 overall=pass`、drift 0 |

`verify` 的唯一 `na` 是 `evidence_rebaseline`：无实测报告，能力仍 `declared`；
三态语义下「未启用」不计 pass 也不计 fail。

### 独立取证（写盘前后逐项比对）

- `entries` / `capability_model` / `work_items` / `history` / `lessons` / `access`
  六段内容 digest **逐一一致**（`aaa41412…` / `9ce706b7…` / `f5013833…` /
  `dbf629d5…` / `ecee33a1…` / `00e70d95…`）。
- 三包观察 sha 与 S1 完全一致：`observations 414506bd…` /
  `baseline 06d950c6…` / `post-v150 e8cf19ae…`；闭环计数未变。
- `P` 的 97 个在途改动数量未变；账本 mtime `18:24:19 → 21:57:55`
  （写盘预期变化，非并发写入）。
- 三方摘要全等：仓库 `method_assets` / `P` 账本 / `asset_bundle` 独立复算，
  `ontology_digest` 三方同为 `e258dec1…`。
- 未对 `P` 执行完整 `post_upgrade` SOP（本版只做重绑与复验）；条件化路径由
  门禁的**空 `tests/` fixture 负向回归**证明（三步 SKIP、不生成报告），
  非在真实项目上跳过验证。

## 六、设计内告警（不掩盖、不在本版修）

1. E7 `cardinality_contradiction`：单项目 `registry` vs 4 项目能力模型，
   使 `ontology.py check --target P` 的 `ok=false`，但第七轴 `binding=pass`；
   彻底修需 `registry/2`，属 v2.0.0 的人批准数据迁移。
2. `evidence_rebaseline=na` / `all_active=false`：无实测报告；v1.7.0 起由
   `activation.state=unbound` 显式表达，未伪装成已激活。
3. `scale_budget` 的 `project_files` 超阈值告警（大型存量项目，非治理层膨胀）。

## 七、回滚

```bash
python3 scripts/upgrade.py --target P \
    rollback --backup-id 20261118T135753Z-ed92ea36 --approved-by <人>
```

方法论仓侧（tag / push 前）：`git reset --hard 1d5294a` 可退回发版 A。
tag 与远端发布点为不可变标识，回滚方法论仓后须同步处理，否则再次出现
版本漂移。

## 八、本版未做（后续处方）

- 语义图：需 P1（`P` 的真实 CI 报告）→ P2（A2 可判定）→ P3（已具备），
  三者齐备才纳入下一次功能发版；
- `registry/2` 多项目数据契约（同时解决 E7）；
- 条件化 SOP 在有 `tests/` 的真实项目上的正向执行留待该类项目接入时取证。

## 九、发布动作

本文件提交后执行 `git tag -a v1.7.0` 与 `git push origin main --follow-tags`
（非 force），使 `origin/main` 与 tag 指向同一发布点。执行结果以
`git log` / `git ls-remote` 为准。
