# v1.8.0 发版报告：证据适配与不降级

> 用户授权：「確認授權擴大範圍的1.8」（2026-11-18）。
> 序列：S1 固化 → S2 红灯 → S3 实现转绿 → S4 人批准重绑 `P` → 发版。
> 目标项目记作 `P`（RacOS 根仓库）；方法论仓为独立 git 仓库。

## 一、发版内容

修 P1 可达性审计发现的四处适配缺口，并把「重算不降级」做成机器门禁：

| 缺口 | 实现 | 验证 |
|---|---|---|
| A 空绑定判绿 | `work_panel.default_source_dirs()` 探测 monorepo；空 inputs 置 `overall=fail` | 空 fixture fail、P 探测 8 目录 |
| B JUnit 无 file | `work_panel.classname_to_file()` 按账本白名单反解 basename | 19 用例映射 10 文件 |
| C 目录失配 | 生成器 `_monorepo_dirs()` 覆盖 `projects/*` | build 全项目覆盖 |
| D hints 失配 | 生成器 `evidence_hints()` 从账本 evidence 派生 | 与新目录合并后 level 保持 |
| 不降级 | `no_regress()` + `--allow-regress` 显式绕过 | 降级数 0、`no_regress()=[]` |

`acceptance/1` 第五层（L5）四项机器断言，十项 checks 全 PASS；统一门禁 16 阶段；264/264 单测。

## 二、S4 人批准重绑 `P`

- **批准人**：`用户授权-2026-11-18-v1.8.0-扩大范围`；
- **迁移**：`M3-tool-sync + M4-method-version + M5-method-assets + M7-asset-install`；
- **写盘前备份**：`20261118T160604Z-299b15e3`（35 文件、`created=[]`）；
- **审计链诚实记录**：
  - `seq=7` 是一次 `rollback`（backup `20261118T160522Z-1094451c`）——首次 apply 时
    我误用了 `PREVIEW-DRY-RUN` 作为批准人字段（写盘本身在授权范围内，但字段不严谨）；
    按「不伪造、不偷偷改历史」纪律，**回滚后以正确批准人重做**，两次操作都留在审计链上。
  - `seq=8` 是本次正式 apply，`approved_by=用户授权-2026-11-18-v1.8.0-扩大范围`。
- **工具同步**：3 个工具 sha 与权威模板逐字节一致（build_capability_model `36c00416…`、
  verify_ledger `3747a5e2…`、run_tests `fcc40977…`）。

## 三、三方摘要（升级后）

| 轴 | v1.7.0 | v1.8.0 |
|---|---|---|
| `method_version` | 1.7.0 | **1.8.0** |
| `method_assets.digest` | `d5c9109c…` | **`ecf7f2c9…`**（85 文件数不变） |
| `installed_assets.digest` | `ddb88625…` | **`927bc681…`**（28 份） |
| `ontology_digest` | `e258dec1…` | **`63ab23df…`**（`SOURCE_FILES` 含被改脚本，本版必然变化） |
| `board_skeleton` | `735bcd09…` | 不变 |

## 四、复验

- `upgrade.py verify --target P --json` → `overall=pass`、`upgrade_complete=true`，
  唯一 `na` 是 `evidence_rebaseline`（无实测报告，诚实保留）；
- 24 条三态不变量：`23 pass + 0 fail + 1 na`、`all_ok=true`、`all_active=false`；
- 业务数据未变：47 能力 level 保持 `L5:20/L3:22/L2:5`、`test_results=null`、
  `activation.state=unbound`（未伪造 verified）；
- 三包观察 sha 不变：`observations 414506bd… / baseline 06d950c6… / post-v150 e8cf19ae…`；
- 门禁：264/264 单测、`acceptance/1` 十项 PASS、卫生 CLEAN、幂等 PASS、upgrade 自检通过。

## 五、边界与未做（诚实清单）

- **P1 未最终满足**：本版只保证「工具层能让 verified 升上去且不降级」；主仓
  `governance/registry.json` 的目录/hints 修复与受控重算属于**独立的人批准数据迁移**，
  本版**未对主仓账本 capability_model 做任何重算或 verified 写入**。
- 语义图（R4）仍顺延（须 P1–P3 全满足）；`registry/2` 仍 v2.0.0。
- E7 `cardinality_contradiction`、`evidence_rebaseline=na`、`scale_budget` 阈值告警、
  6 条 `open` 观察均如实保留，未掩盖。
- `ontology_digest` 本版变化（与 v1.7.0 不同）——因 `SOURCE_FILES` 含被改的
  work_panel 与生成器模板；已由 M5 重绑第七轴。
- 门禁完整 16 阶段在单次工具时限内因测试阶段 ~280s 未完成，已分段验证各阶段无红灯。

## 六、回滚

```bash
python3 scripts/upgrade.py --target P rollback \
    --backup-id 20261118T160604Z-299b15e3 --approved-by <人>
```

回滚后需重新 apply 并复验；`seq=7/8` 的审计记录不因回滚消失。
