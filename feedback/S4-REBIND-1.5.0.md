# S4 结案：目标项目 M5 + M7 重绑

> 本文件是 **S4 的写盘证据与复验记录**，不参与门禁计数，不是第二事实源。
> 序列：S1 固化证据 → S2 先写会失败的回归 → S3 三层转绿 → **S4 重新人批准主仓重绑**。
> 批准来源：用户「繼續s4」；批准人写入账本 `用户授权-2026-11-18-S4`。
> 纪律：只写目标项目，不 push、不打 tag、不升 `METHOD_VERSION`、不在方法论仓提交主仓改动。

## 一、只读预演（写盘前）

`upgrade.py --target P plan --json`：

```
from 1.5.0 -> to 1.5.0     noop=False   risk=medium   blocks=[]
migrations = ['M5-method-assets', 'M7-asset-install']
assets      recorded 0bd06f8274e0…  →  权威源 9493bc9ee693…（85 文件）
installed   noop=False · missing=0 · stale_protected=0
            drifted=3  .workbuddy/experts/platform-steward/EXPERT.md
                       .workbuddy/skills/agent-gate/SKILL.md
                       .workbuddy/skills/ledger-upgrade/SKILL.md
board       match=True       tools 3/3 in-sync
backup      35 个文件清单（含账本、看板、registry、3 工具副本、manifest、28 份只读副本）
```

与 [S3 结案报告](ACCEPTANCE-1.6.0-CLOSEOUT.md) 第六节的处方完全一致：
版本不变、仅摘要重绑，迁移恰为 M5 + M7，无需 M4（版本迁移）或 M6（骨架归一）。

## 二、写盘结果

```bash
python3 scripts/upgrade.py --target P apply \
    --approved-by '用户授权-2026-11-18-S4' --json
```

```
schema=upgrade-apply/1   noop=False
backup=20261118T100016Z-ccd42d92
migrations=['M5-method-assets','M7-asset-install']
from 1.5.0 -> to 1.5.0
```

`governance_meta.upgrade_log` 追加第 4 条（append-only）：
`seq=4 / action=apply / approved_by=用户授权-2026-11-18-S4 /
migrations=[M5,M7] / backup=20261118T100016Z-ccd42d92 / risk=medium`。

### 绑定值前后对比

| 字段 | 写盘前 | 写盘后 |
|---|---|---|
| `method_assets.digest` | `0bd06f8274e0…`（84 文件） | `9493bc9ee693…`（85 文件） |
| `ontology_digest` | `c399ff180ebc…` | `e258dec16cef…` |
| `installed_assets.digest` | `72afff96984d…`（28 份） | `47dfc3c3a7ad…`（28 份） |
| `method_version` | `1.5.0` | `1.5.0`（未升） |
| `board_skeleton.digest` | `735bcd09fb54…` | `735bcd09fb54…`（未变） |

### M7 实际写盘半径（用备份清单逐文件 sha 对比）

备份 35 文件，写盘后**仅 6 个内容变化**，其余 29 个逐字节未变，
`created=[]`（无新增路径，回滚无需删文件）：

```
governance/DECISION_LEDGER.json          ← M5 摘要 + upgrade_log
governance/index.html                    ← EMBED 数据段同步
governance/ASSET_MANIFEST.json           ← M7 重新签名
.workbuddy/experts/platform-steward/EXPERT.md
.workbuddy/skills/agent-gate/SKILL.md
.workbuddy/skills/ledger-upgrade/SKILL.md
```

即 M7 只重装了 3 份 drifted 副本，其余 25 份因内容一致未被改写——
与 `asset-install` 的幂等安装设计一致。

## 三、复验结果

| 检查 | 结果 |
|---|---|
| `upgrade.py verify` | **`block=0 / pass=11 / warn=0 / na=1` · `upgrade_complete=true`** |
| `upgrade.py plan` | **`noop=true` · `migrations=[]` · `risk=none`**（连跑两次 verify 结果一致） |
| 12 项明细 | 除 `evidence_rebaseline=na` 外全 pass；`method_assets` / `installed_assets` / `ontology_binding` 三项 warn 全部消失 |
| 24 条三态不变量 | `passed=23 / failed=0 / na=1 / all_ok=true`；`--strict` rc=0 |
| `asset_bundle verify` | `ok=true` · 28 份 · errors=[] |
| `route_expert --check-assets` | `ok=true` · asset_count=28 · `scoped=true` |
| `ontology.py check --target P` | **`binding=pass`**（S3 前的 `warn` 已消除）；`ok=false` 仍因 E7，见第四节 |
| `board_contract check` | `match=true`（骨架一致，数据段由账本同步） |
| `work_panel check` / `nodes` | `ok=true` / 72 个节点 |
| `file_layout --diff --strict` | `missing=0 / extra=0 / phase=governed` |
| `scenario_guard --strict` | `blocks=0 / warns=0` · rc=0 |
| 方法论仓 `acceptance.py --check` | `rc=0`（S3 的三层绿灯未被 S4 破坏） |

S3 处方里的预期 `pass=11 / na=1 / warn=0`、`upgrade_complete=true` **100% 命中**。

## 四、独立取证：业务数据一字未改

| 项 | 写盘前 | 写盘后 |
|---|---|---|
| `entries` / `capability_model` / `work_items` / `history` / `lessons` / `access` 六段 digest | `aaa41412…` / `9ce706b7…` / `f5013833…` / `dbf629d5…` / `ecee33a1…` / `00e70d95…` | **完全相同** |
| 决策 / 项目 / 工作项 | 21 / 4 / 3 | 21 / 4 / 3 |
| 三包观察 sha | `e0b313ef…` / `06d950c6…` / `e8cf19ae…` | **完全相同**（13/4/4、12/2/2、15/2/1 闭环计数不变） |
| 主仓在途改动 | 97 条，列表指纹 `88415cc9…` | 97 条，指纹 `88415cc9…`（无新增/删除路径，未触碰用户原有改动） |

只有 `governance_meta` 与由其派生的看板 EMBED 数据段、资产副本/manifest 被写。

### 设计内告警（与本轮无关，不修、不掩盖）

- **E7 基数违例**：`ontology.py check --target P` 仍报
  `cardinality_contradiction: registry 声明单项目 project，能力模型含 4 个项目`。
  这是主仓 monorepo 结构与单项目 `registry/2` 契约之间的已知 gap，v1.5.0 起由 A4 命名；
  S4 只负责 `binding` 那一支，已转 pass。
- **`evidence_rebaseline=na` / `all_active=false`**：主仓无 `test_report.json`，
  47 个能力仍为 `declared`；`na` 不阻止 `upgrade_complete` 判定，但「升级完成」≠「证据已激活」。
- **`scale_budget status=warn`**：唯一超阈值项是 `project_files=49078`
  （2000 文件扫描上限），是规模阈值告警，设计上只提示不自动拆账本。

## 五、回滚

```bash
python3 scripts/upgrade.py --target P \
    rollback --backup-id 20261118T100016Z-ccd42d92 --approved-by <人>
```

备份 `20261118T100016Z-ccd42d92` 含 35 个文件、清单完整、`created=[]`，
可恢复账本 / 看板 / manifest / 3 份 drifted 副本；
前三次备份 `20261117T232826Z-15875e19`、`20261117T234437Z-6bc49707`、
`20261118T072013Z-ad0f73f7` 仍保留。

## 六、边界与下一步（待决策）

**本轮明确不做**：不升 `METHOD_VERSION`、不改 28 份 frontmatter、不打 tag、
不 push、不跑 `POST_UPGRADE` 第 19 步（避免污染三包观察证据）、
不条件化第 1/2/15 步 SOP、不补 M8 `activation` 占位、不做 `registry/2`。

⚠️ **「同版本、不同规则」风险现已实际生效**：主仓 `method_version=1.5.0`，
但绑定的 `method_assets` 是 S3 之后的字节；`tag v1.5.0` 仍指向 `dffc0d4`（S3 之前）。
因此**必须统一发版**：升 `METHOD_VERSION` → 1.6.0、同步 28 份 frontmatter /
CHANGELOG / README / RELEASE_CHECKLIST、打 tag、push。

**发版的隐藏成本（需提前知晓）**：`METHOD_VERSION` 定义在
`scripts/upgrade.py`，而 `method_assets` 的资产组含 `scripts/*.py`；
28 份 `EXPERT.md` / `SKILL.md` 也在资产组内。改版本号与 frontmatter
**必然再次改变 `method_assets.digest`**，使主仓 `method_assets` 重新 warn，
需要再跑一次 M5（+ 可能的 M7）重绑。建议二选一：

1. 接受一次「纯版本号重绑」（成本低、审计清晰）；
2. 把发版与下一次功能迭代合并，减少写盘次数。

更彻底的做法是把 `METHOD_VERSION` 从资产摘要口径中剥离，但那属于
版本契约的架构改动，应单独立项决策，不要在发版里顺手做。

## 七、复现命令

```bash
python3 scripts/upgrade.py --target P plan --json     # noop=true
python3 scripts/upgrade.py --target P verify --json   # pass=11 / na=1 / warn=0
python3 scripts/asset_bundle.py --target P verify --json
python3 scripts/ontology.py check --target P --json   # binding=pass（E7 仍告警）
cd P && python3 governance/verify_ledger.py --json
```

相关文档：[S2 验收契约](ACCEPTANCE-1.6.0.md)、
[S3 结案](ACCEPTANCE-1.6.0-CLOSEOUT.md)、
[升级前后观察 diff](UPGRADE-DIFF-1.5.0.md)、
[16 · 升级与迁移](../docs/16-升级与迁移.md)。
