# v2.0.2 交付与核实（业务诚信补丁）

> 起因不是「想加功能」，而是一次真实价值评估暴露的自相矛盾：
> **24 条不变量全绿，同时目标项目 3 条工作项全部已经完成却仍挂 `open`。**
> 结构自洽掩盖了业务说谎——看板与 `next_queue` 会指挥下一个执行者去做已完成的事。
> 本版只修这一件事，并把它变成机器强制点。

## 一、改了什么

| 层 | 改动 | 证据 |
|---|---|---|
| 契约 | `work_items[].close_condition`：`capability_verified` / `file_exists` / `manual` | `docs/21` 数据契约表 |
| 校验 | 不变量 #22 `work_items_valid` 扩展：关闭条件已被证据满足却仍 `open/doing` 判 fail | `templates/verify_ledger.py` |
| 工具 | `work_panel close` 支持 `--resolution` / `--close-condition`，必填校验 + `closed_at` | `scripts/work_panel.py` |
| 测试 | 校验器 2 项 + 工作台 6 项，正负双向 | `tests/core/test_verify.py`、`tests/views/test_work_panel.py` |
| 文档 | 修 README 两处漂移：测试文件数不再写死、删掉与 v2.0.1 事实相反的「不做 registry/2 迁移」 | `README.md` |
| 强制点 | 目标仓新增 `governance.yml`；`pre-commit` 第 11 步跑 24 条不变量 | `.github/workflows/governance.yml`、`git-hooks/pre-commit` |

设计取舍：**没有新增第 25 条不变量**，而是扩展第 22 条的语义。
理由：不变量数量是契约，膨胀会让「24 条全绿」这句话贬值；而「工作项不许说谎」
本来就属于「工作项自洽」，放回原处语义更准确，也避免全仓 24→25 的连锁改动。

判定原则：**无法判定的条件一律视为未满足，宁可漏关，不可误关。**

## 二、目标项目数据变更（人批准、可回滚）

批准人：`用户批准-P0P1-业务诚信与治理CI-2026-11-19`

| 工作项 | 原状态 | 关闭条件 | 结论 |
|---|---|---|---|
| `W-TODO-001` registry 拆分为多项目结构 | `open` | `file_exists governance/registry_codec.py` | v2.0.0/v2.0.1 已交付，关闭 |
| `W-ISSUE-001` 缺 test_report.json，47 能力仍 declared | `open` | `file_exists governance/test_report.json` | 报告已绑定 182 用例，20 能力 verified，关闭 |
| `W-TODO-002` 让 `<PROJ>.DATA.READY.01` 升 verified | `open` | `capability_verified <PROJ>.DATA.READY.01` | 该能力已 L5 + verified，关闭 |

备份：`.ledger-upgrade/backups/20261119T013534Z-p0p1/governance/`（含 `MANIFEST.sha256`）
重绑备份：`20261119T013606Z-88a1c321`（M4 版本 + M5 资产摘要）

## 三、复验结果（本机实测）

```
方法仓 check.sh                      EXIT=0
仓库测试                             290/290 passed
acceptance --check                   PASS，18 项，目标版本 2.0.2
目标项目 24 不变量                    24 pass / 0 fail / 0 na
目标项目 work_panel check            ok=true, work_items=3, test_cases=182, nodes=72
upgrade verify                       overall=pass, complete=true, 12 pass / 0 warn / 0 block
method_version                       2.0.2
method_assets.digest                 88838e41827c0b65d2e1d9e52f8abcb3c1a221a90bb0949858c39108d6533cfd
ontology_digest                      1dada5e265cef7486d14485c4d379143ae0f5c14fb24107b2299635caeb62805
activation                           active
```

**证据刷新不是走过场**：`upgrade verify` 首轮报 `evidence_rebaseline warn`——
某个能力引用测试文件 在报告生成后被改过，证据摘要过期。
处理方式是重跑那 24 个能力引用文件（`182 passed`）、重新 `import-report` + `sync-tests`、
再重算能力模型，`freshness` 回到 `fresh`，`upgrade_complete` 才从 `false` 变 `true`。
**没有为了让 `complete=true` 去改 warn 的判定。**

## 四、负向证明（新规则真的会咬人）

在真实账本上只读地把 `W-TODO-002` 翻回 `open`（不写盘，仅内存）：

```
failed: ['board_embed_synced', 'work_items_valid']
detail: 工作项 3 条 · 错误=['W-TODO-002: 关闭条件已满足（<PROJ>.DATA.READY.01 tier=verified）
        但仍 open——事件已完成，账本不许继续挂账']
```

`board_embed_synced` 同时失败是预期：看板与账本必须同源，改账本不重渲染就会被抓。

## 五、边界（不掩盖）

1. `manual` 型条件无法机器判定，这类工作项仍需人主动关闭；本版只保证「能判定的不许说谎」。
2. 本版**没有**扩大证据覆盖：verified 仍 `20/47`，`<P2>` 仍 0 测试、`<P3>` 8 能力 0 verified。
3. 本版**没有**做语义图 R4，也没有处理多副本同步税。
4. 目标项目根仓库的提交被一个既有技能树摘要漂移阻塞
   （`.workbuddy` 部署副本指向的上游技能在 11-18 有真实改动）。该漂移与本次改动无关，
   未绕过钩子、未重算清单，交由人工裁决。

## 六、怎么用

```bash
# 声明可机器判定的关闭条件（新建或关闭时）
python3 scripts/work_panel.py --target <项目> close \
  --id W-TODO-003 \
  --close-condition '{"kind":"capability_verified","capability":"X.Y.Z.01"}' \
  --resolution "该能力已 verified" \
  --approved-by "姓名" --apply

# 任何一次提交/PR 都会自动检查
python3 governance/verify_ledger.py --root . --strict
```
