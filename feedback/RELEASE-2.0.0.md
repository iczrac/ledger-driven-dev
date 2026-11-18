# v2.0.0 发版报告：registry/2 多项目编码契约 / P1 数据迁移

> 用户授权：「a」（2026-11-19）= 正式立项 v2.0.0 破坏性迁移（S1→S4→发版+核实）。
> 序列：S1 固化 → S2 红灯 → S3 转绿 → S4 人批准重绑 + P1 数据迁移 → 发版。
> 目标项目记作 `P`（P 根仓库）；方法论仓为独立 git 仓库。

## 一、发版内容

修 v1.8.0 写盘会产生 5 段码（`<ROOT>.<PROJ>.DATA.READY.01`）的根因，使生成器产出
与账本、校验器一致的 4 段码，并让 P1 的真实 verified 升级可安全落盘。

| 缺口 | 实现 | 验证 |
|---|---|---|
| 5 段码 | `code_namespace(project_code, module_code)`：module 已含项目段直用，否则补前缀 | 主仓 `<PROJ>.DATA`、模板 `DEMO.DATA` 均 4 段 |
| build 裸拼 | module/cap code 均经 `cap_ns` 生成 | 无 `f"{code}.{mcode}"` |
| P1 写盘坏账本 | 4 段码 + 不降级门禁 | 24 不变量 24 pass/0 fail |
| activation 说谎 | `activation_from_report()` 在 sync-tests 时同步激活态 | active/all_active=true |

`acceptance/1` 第六层（L6）四项机器断言，14 项 checks 全 PASS；统一门禁 16 阶段；
273/273 单测；双写兼容（单项目模板 + monorepo）。

## 二、S4 人批准重绑 P

- **批准人**：`用户授权-2026-11-19-a-v2.0.0破坏性迁移`；
- **迁移**：M3-tool-sync + M4-method-version + M5-method-assets + M7-asset-install
  （首轮）+ M5 摘要重绑（activation 返工后）；
- **备份**：`20261118T162441Z-p1final`（阻断轮）+ upgrade apply 自带快照；
- **P1 数据迁移**：`import-report --apply`（182 用例）→ `sync-tests --apply`
  （test_results + activation）→ 主仓新生成器写盘（verified:20、4 段码、不降级）。
- **返工诚实记录**：activation 首次未同步（仍 unbound 且 reason 与事实相反），
  已产品化修复并重做，详见 `S4-2.0.0-REBIND.md` 第三节；审计链 append-only。

## 三、三方摘要（升级后）

| 轴 | v1.8.0 | v2.0.0 |
|---|---|---|
| `method_version` | 1.8.0 | **2.0.0** |
| `method_assets.digest` | `ecf7f2c9…` | **`99856a1d…`** |
| `installed_assets.digest` | `927bc681…` | 按 2.0.0 重绑 |
| `ontology_digest` | `63ab23df…` | **`af552716…`**（SOURCE_FILES 含 work_panel/生成器） |
| `board_skeleton.digest` | `735bcd09…` | 不变 |

## 四、复验

- 24 条三态不变量：**24 pass / 0 fail / 0 na**、`all_ok=true`、`all_active=true`
  （v1.8.0 为 23 pass + 1 na）；
- 47 能力 code 全 4 段、0 个 5 段码、0 个 `<ROOT>.` 泄漏；level `L5:20/L3:22/L2:5` 不降级；
- `evidence_tier` `verified:20/declared:27`、`test_results` 绑定真实报告 182 用例、
  `activation.state=active`；
- `upgrade.py verify` → `overall=pass`、`upgrade_complete=true`、12 pass/0 warn；
- 三包观察 sha 不变：`observations 414506bd… / baseline 06d950c6… / post-v150 e8cf19ae…`；
- 门禁：273/273 单测、`acceptance/1` 14 项 PASS、ontology/test_modules 自证通过。

## 五、边界与未做（诚实清单）

- **P1 已满足**（20 能力 verified、24 不变量全绿）；但 P2（ontology A2 可判定）、
  P3（规划一致性机器校验，v1.7.0 G1 已实现）**未复验**，故语义图 R4 仍顺延；
- E7 `cardinality_contradiction`：**本版顺带治愈**——4 段码与本体基数公理一致后，
  `ontology.py check --target P` 由 v1.8.0 的 `ok=false` 变为 `ok=true`（已实测）；
  但 registry 单项目结构本身未改，若未来再引入跨项目码仍可能因契约漂移复现；
- `scale_budget` 告警、6 条 `open` 观察保留；
- 28 份 frontmatter、CHANGELOG / RELEASE_CHECKLIST / docs16 / docs23 顺延表同步。

## 六、回滚

```bash
python3 scripts/upgrade.py --target P rollback \
    --backup-id <S4-self-snapshot> --approved-by <人>
```

回滚后需重新 apply 并复验；P1 数据迁移的 test_report.json / test_results / activation
需一并处理；append-only 审计记录不因回滚消失。
