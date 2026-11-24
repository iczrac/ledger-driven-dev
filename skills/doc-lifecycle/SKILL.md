---
name: doc-lifecycle
description: |
  文档生命周期：生成带待填标记的骨架、结构/命名/链接/状态词/覆盖率 lint、
  上游指纹变化标 suspect、带签名清除 suspect、只读 check 供 CI。
  骨架永不判 compliant；不自动撰写"为什么"正文；不绕过账本改 ledger。
  Triggers: "文档生命周期", "文档过期", "文档失效", "文档漂移", "文档复核",
  "文档覆盖", "标 suspect", "清 suspect", "待人工填写", "doc lifecycle",
  "doc drift", "doc trust", "stale", "suspect", "mark stale", "clear suspect"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.0.0"
  risk_level: write_draft_only
  related_skills: [doc-rebuild, ledger-verify, ledger-guard, graph-compare]
---

# Doc Lifecycle（文档生命周期）

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 专家路由与资产/账本校验走唯一入口：`python3 scripts/ledger_entry.py --intent "任务描述"` 或 `--check-all`；任一门禁失败即退出码 1（fail-closed）。
- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。

## 触发词

文档过期 / 文档失效 / 文档漂移 / 文档复核 / 文档覆盖 / 标 suspect / 清 suspect / 文档生命周期 / doc drift / doc trust / stale / suspect。

## 输入 / 输出契约

| 命令 | 输入 | 输出 | 副作用 |
|---|---|---|---|
| `scaffold` | `--target P --doc <rel> --kind plan\|rationale\|reference\|record` | `doc-lifecycle/1`：status=incomplete + 路径 | 写骨架（含 `<!-- 待人工填写 -->`），已存在即拒绝 |
| `lint` | `--target P` | 结构/命名/链接/状态词/覆盖率报告 + issues[] | 无（只读） |
| `mark-stale` | `--target P --doc <rel> --reason <r>` | status=suspect + 原因 + 时间 | 无（状态裁决交 ledger-steward 写账本） |
| `clear-suspect` | `--target P --doc <rel> --signed-by <人> --reason <r>` | status=cleared + 签名 | 无（须签名与理由，缺一即拒绝） |
| `check` | `--target P` | 五项文档不变量只读报告（mode=shadow） | 无（只读，供 CI） |
| `gate` | `--target P [--strict]` | orphan/suspect/stale/信任告警计数 + 具体文件清单 | 无；默认 warn 退出码 0，`--strict` 才阻断 |
| `seed` | `--target P --approved-by <人>` | 确定性初判并写 `governance/DECISION_LEDGER.json#docs.registry` + 历史事件 | 写账本字段；全部 draft、verified 为空，重复执行 noop |
| `approve` | `--target P --doc <rel> --status current --signed-by <人> --reason <r> [--source-hash <h>]` | 带签名与可复算摘要的 current 裁决 + 历史事件 | 写账本字段；无签名/摘要不符一律拒绝 |

## 五项文档不变量（先 shadow，只告警不改状态）

1. **覆盖完整**：`docs.registry` 声明的每篇文档都存在；
2. **派生可复算**：每篇文档的状态词与 `source_hash` 可从文件复算；
3. **信任一致**：`verified` 必须同时具备 `source_hash` 与 `generated_from`（当前正文由何来源复核）；
4. **义务已声明**：非骨架文档必须在 `docs.registry` 有 owner/role/stale_after；
5. **无孤儿**：`docs/**` 中无未登记文档。

新判据先 shadow：报告告警但不改账本状态、不升硬门。唯一升硬门条件：连续 10 次 CI 运行中 `orphan=0`、`uncovered=0`、`obligation_missing=0`、`stale_unknown=0`、`suspect=0`、`stale=0`、`信任告警=0`、`派生漂移=0`，且任一指标不是 `n/a`，并经人工书面批准后，才允许 `--strict` 进 CI 阻断。`seed` 只做 draft 初判，禁止批量标 current；`owner` / `role` / `stale_after` 只能由人逐篇批准，禁止批量填充占位值。

## 允许动作

- `scaffold` 生成带 `<!-- 待人工填写 -->` 的骨架（status 固定 incomplete）；
- `lint` 调既有 `registry_codec` 四段码校验与 `ontology.py` 词表，核对链接存在性与状态词合法；
- `mark-stale` 在上游 `source_hash` 变化时给 suspect 建议；
- `clear-suspect` 取得签名与理由后给 cleared 建议；
- `check` 输出只读报告给 CI；
- `gate` 给统一门禁节提供可机读计数与文件清单（默认不阻断）；
- `seed` 仅在 ledger-steward 批准下做确定性 draft 初判并进历史链；
- `approve` 仅在人工签名 + 可复算摘要同时存在时把单篇升为 current。

## 禁止动作

- 禁止自动撰写"为什么"类正文（rationale 的为什么必须由人写）；
- 禁止把骨架标为 compliant；
- 禁止绕过账本直接改 ledger / docs.registry（裁决属 `ledger-steward`）；
- 禁止覆盖既有文档正文；禁止无签名 clear-suspect。

## 失败时的 fail-closed 行为

- 文档不可读 → status=unreadable，退出码 1，不猜内容；
- 骨架未填 → incomplete，不判 compliant；
- clear 缺签名或理由 → status=error，退出码 2；
- 五项不变量未达 → warn，退出码 1，不改状态。

## 与哪些专家交接

- `ledger-steward`：写 `docs.registry` / 裁决 stale/suspect / 批准 declared_no_impact；
- `loop-executor`：接 `kind=doc` 任务卡补正文，一次一张；
- `evidence-auditor`：只读审计信任三项（verified.at/generated.at、source_hash、stale_after），不写文档不关 issue；
- `release-steward`：发布门读 check 报告，stale 存在即阻塞；
- `goal-orchestrator`：把 doc 任务卡完成计入 stall 进展。
