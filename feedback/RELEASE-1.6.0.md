# v1.6.0 发版结案报告

> 目标：消除「同版本、不同规则」。本报告只记录事实与可复放命令，不替代任何权威源。
> 目标项目一律记作 `P`；所有写盘动作均以人批准为前提。

## 一、决策（第一性原理）

发版前状态：`tag v1.5.0 → dffc0d4`，而目标项目 `P` 的账本标 `method_version=1.5.0`
却绑定 S3 之后的资产字节 `9493bc9e…`。按 tag 复放得到的规则 ≠ 项目实际执行的规则，
治理系统「可复放」这一唯一目的已失效，且随时间推移只会更难对齐。

| 候选方案 | 判断 | 理由 |
|---|---|---|
| 把版本号从资产摘要口径剥离 | **否决** | `upgrade.py` 既是权威工具又定义版本，其 sha 属于 `tools` 轴与 `scripts` 资产；剥离等于让版本标识与规则内容脱钩，正是本系统要防的第二事实源。发版触发实例重绑是正确语义。 |
| 与下一次功能迭代合并发版 | **否决** | 迭代内容与时点都不确定，期间不一致持续；且任何新资产改动都会再变摘要，届时基线与复验必须重做。 |
| **立即发 1.6.0，一次收口** | **采纳** | 当前证据最齐、diff 最小、门禁全绿；顺带把真正该解耦的点修掉：`test_acceptance.py` 改为从 `upgrade.py` 动态读版本，以后发版无需手改测试。 |

发布纪律与 S1 不同：S1 只是证据固化，故不 push / 不打 tag；**正式发版正是不可变
发布点的用途**，且若只留本地，版本不一致会从「本地 vs tag」平移成「本地 vs 远端」。
因此本版统一执行 `commit → tag v1.6.0 → push`。

## 二、序列与提交锚点

| 步骤 | 提交 | 内容 |
|---|---|---|
| S1 | `dad503c` | 固化升级前后观察证据，未 push / 未打 tag |
| S2 | `c6a86ce` | 验收契约 + 16 个绿灯自测 + 第 14 个门禁阶段（刻意红灯） |
| S3 | `5c8bd37` | 三层验收转绿、append-only 根因修复、派生与本体重算 |
| S4 | `ffcbcae` | 人批准 `M5 + M7` 重绑，证据报告 |
| 发版 A | **`b6c4e09`** | 固化 v1.6.0 权威源字节（31 文件），`method_assets → 264026fd…` |
| 发版 B | 本文件所在提交 | `CHANGELOG` / `RELEASE_CHECKLIST` / 本报告；`tag v1.6.0` |

发版 A 与 B 的划分有意为之：A 决定目标项目绑定的资产摘要；B 只改根级文档与
`feedback/`，均不在 `ASSET_GROUPS` 作用域内，因此 tag 指向的资产字节与 A 完全一致。

## 三、写盘预演与实际结果

只读 `plan`（写盘前）：`from 1.5.0 → to 1.6.0`、`noop=false`、`risk=medium`、
`blocks=[]`、迁移恰为 `M4-method-version` + `M5-method-assets` + `M7-asset-install`；
工具副本 3 个 `in-sync`、看板骨架 `match=true`、`missing=0` / `stale_protected=0`。

与 S4 的差别：S4 只有 3 份资产副本 drifted（正文计数改动）；本版改了 28 份
frontmatter 的版本号，**28 份副本全部 drifted**，M7 需全量重装。

```bash
python3 scripts/upgrade.py --target P apply \
    --approved-by '用户授权-2026-11-18-v1.6.0-发版' --json
```

- 新备份：`20261118T102418Z-5cd2106a`（35 文件、`created=[]`）
- `upgrade_log` 追加 `seq=5`：`1.5.0 → 1.6.0`、三条迁移、`risk=medium`

### 绑定值前后对比

| 字段 | 发版前 | 发版后 |
|---|---|---|
| `method_version` | `1.5.0` | **`1.6.0`** |
| `method_assets` | `9493bc9e…`（85 文件） | **`264026fd…`**（85 文件） |
| `installed_assets` | `47dfc3c3…`（28 份） | **`4e46f733…`**（28 份） |
| `ontology_digest` | `e258dec1…` | `e258dec1…`（**未变**） |
| `board_skeleton` | `735bcd09…` | `735bcd09…`（未变） |

`ontology_digest` 不变是有意设计：`ontology.py` 的 `SOURCE_FILES` 不含版本脚本与
编号文档，改 `METHOD_VERSION` 不需要重算本体投影。这把发版成本限定在 M4 + M5 + M7。

### 写盘半径

备份 35 文件中 **31 个内容变化、4 个逐字节未变、0 缺失**：
3 个 `governance/` 文件（账本 / 看板 / manifest）+ 28 份 `.workbuddy/` 只读副本。

## 四、复验结果

| 检查 | 结果 |
|---|---|
| `upgrade.py verify` | `block=0 / pass=11 / warn=0 / na=1`，`upgrade_complete=true` |
| `upgrade.py plan`（连跑两次） | `noop=true / risk=none / migrations=[] / blocks=0` |
| 24 条三态不变量 | `23 pass + 1 na`、`all_ok=true`、`--strict rc=0` |
| `asset_bundle verify` | 28 份 ok、`errors=[]`；`route_expert --check-assets scoped=true` |
| `ontology.py check --target P` | `target.binding=pass`；`ok=false` 仅因 E7（见下） |
| 看板 / 工作台 / 预检 / 布局 | 骨架 match、工作台 ok（72 节点）、blocks=0、布局 governed |
| 方法论仓门禁 | `check.sh` 14/14 全绿、243/243 测试、`acceptance/1 overall=pass` |

`verify` 的唯一 `na` 是 `evidence_rebaseline`：目标项目无实测报告，47 个能力仍
`declared`，三态语义下「未启用」不算通过也不算失败。

### 独立取证（写盘前后逐项比对）

- `entries` / `capability_model` / `work_items` / `history` / `lessons` / `access`
  六段内容 digest 全部一致（21 决策 / 4 项目 / 3 工作项）。
- 三包观察 sha 与 S1 完全一致：`observations e0b313ef…` / `baseline 06d950c6…` /
  `post-v150 e8cf19ae…`；闭环计数未变。
- 目标项目 97 个在途改动的数量与列表指纹 `88415cc9…` 均未变 —— **未触碰原有在途改动**。

## 五、设计内告警（不掩盖、不在本版修）

1. E7 `cardinality_contradiction`：单项目 `registry` vs 4 项目能力模型。它使
   `ontology.py check --target P` 的 `ok=false`，但第七轴 `binding=pass`；
   彻底修需 `registry/2` 多项目数据契约，属 v2.0.0 的人批准数据迁移。
2. `evidence_rebaseline=na` / `all_active=false`：无实测报告。
3. `scale_budget` 的 `project_files` 超阈值告警（大型存量项目，非治理层膨胀）。

## 六、回滚

```bash
python3 scripts/upgrade.py --target P \
    rollback --backup-id 20261118T102418Z-5cd2106a --approved-by <人>
```

方法论仓侧（本地 tag / push 前）：`git reset --hard b6c4e09` 可退回发版 A。
tag 与远端发布点为不可变标识，回滚方法论仓后须同步处理，否则再次出现版本漂移。

## 七、本版未做（后续处方）

- 条件化第 1/2/15 步 SOP：目标项目无 `tests/` / 无 `test_report.json` 时的降级路径。
- M8 `activation` 占位与 `all_active` 语义。
- `registry/2` 多项目数据契约（同时解决 E7）。

## 八、发布动作

本文件提交后执行 `git tag v1.6.0` 与 `git push origin main --follow-tags`（非 force），
使 `origin/main` 与 tag 指向同一发布点。执行结果以 `git log` / `git ls-remote` 为准。
