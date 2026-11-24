---
name: ledger-verify
description: |
  运行 31 条账本不变量校验：编码/完成度/路径/决策链、看板同步、历史链与指纹自证、
  经验合法性与任务卡经验状态。产出人类可读或机器可读结果，并给出每项失败的修复动作。
  Triggers: "校验账本", "verify", "账本有没有坏", "CI 检查", "历史链断了",
  "完成度对不上", "看板和账本不一致", "validate ledger"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.0.0"
  risk_level: read_only
  related_skills: [ledger-scan, ledger-guard]
---

# Ledger Verify

账本的"体检"。只读，不改任何文件。24 条检查一次跑完。

## When to Use

任何基于账本做决策之前；提交前；CI 门禁；怀疑账本被手改或腐化时。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--root`、`--ledger`、`--registry`、`--board` |
| 输出 | 24 条 `[PASS]/[FAIL]` 结果；`--json` 给机器；`--strict` 失败返回退出码 1 |
| 副作用 | 无（read_only） |

## 步骤

```bash
python3 governance/verify_ledger.py --root .                 # 人读
python3 governance/verify_ledger.py --root . --json          # 机器读 / AI 解析
python3 governance/verify_ledger.py --root . --strict        # CI 门禁
```

## 失败 → 修复动作

| 失败项 | 修复 |
|---|---|
| `encoding_format` / `encoding_unique` | 修 `registry.json` 的模块/域代码；序号不复用，废弃标 retired |
| `completion_matches_level` | **不要手改 completion**；重跑 `ledger-scan` 从证据重算 |
| `next_action_present` | 重跑生成器；仍缺则说明等级规则配置异常 |
| `doc_paths_exist` / `component_paths_exist` | 补回文件或修路径；不要留空链占位 |
| `decision_refs_valid` / `supersede_chain_consistent` | 补齐双向引用（`supersedes` / `superseded_by`） |
| `registry_impls_exist` | 修 `impl` glob 或创建实现文件 |
| `board_embed_synced` | 重跑生成器同步 EMBED |
| `history_chain_consistent` / `history_event_fingerprints` | 历史事件被改或删——从版本库恢复，**不可自行修补** |
| `history_current_matches` | 重跑生成器；若仍失败说明能力状态被手改 |
| `lessons_valid` / `lesson_candidates_dedup` | confirmed 必须补 `insight` + `action`；候选去重由生成器自动维护 |
| `queue_lessons_confirmed` | 任务卡只引用 confirmed 经验；先确认或移除该引用 |

## 文档信任不变量（先 shadow，只告警不改状态）

在既有账本不变量之外，纳入 5 条文档不变量。每条必须指向真实实现位置，禁止只留在文案里：

| 不变量 | 判据 | 实现来源 |
|---|---|---|
| 覆盖完整 | `docs.registry` 声明的文档都存在，且每篇非骨架文档的 `covers.codes` 或 `covers.decisions` 非空 | `scripts/doc_lifecycle.py::check()` → `doc_coverage` + `lint()` → `uncovered`；覆盖率由 `metrics.coverage.ratio` 给出 |
| 派生可复算 | 状态词与 `source_hash` 可从文件逐字节复算；派生文档存在时逐字节等于重算结果，on-demand 未生成不算缺失 | `scripts/doc_lifecycle.py::_scan()` → `doc_derived`；`scripts/rebuild_docs.py --check` 全量比对，存在性只读 `scripts/file_layout.py::presence_for()` |
| 信任一致 | verified 必须同时具备 `source_hash` 与 `generated_from` | `scripts/doc_lifecycle.py::check()` → `doc_trust`；`approve --status current` 校验签名与摘要 |
| 义务已声明 | 非骨架（status 非 incomplete 且 kind 非 scaffold）文档须登记 owner / role / stale_after | `scripts/doc_lifecycle.py::lint()` → `obligation_missing`；`check()` → `doc_obligation` 与 `metrics.obligation` |
| 无孤儿 | `docs/**` 无未登记文档 | `scripts/doc_lifecycle.py::lint()` → `orphan` issue；`gate()` 汇总数量与文件清单 |

时间判据：`_stale_after_expired(value, as_of)` 返回 `expired` / `fresh` / `unknown`；缺值、占位符与非法字符串都是 `unknown`，单列为 `stale_unknown` 告警，绝不并入 `stale=0`。`as_of` 显式参数优先，否则从账本 `last_updated` 派生，不读机器当前时间。

新判据先 shadow：`scripts/check.sh` 的文档生命周期节与 `gate` 默认只告警、退出码 0；`--strict` 才阻断。
升硬门条件（可判定式）：连续 10 次 CI 运行中 `orphan=0`、`uncovered=0`、`obligation_missing=0`、`stale_unknown=0`、`suspect=0`、`stale=0`、`信任告警=0`、`派生漂移=0`，且人工书面批准后才允许把 `--strict` 接入 CI；任一指标显示 `n/a` 不计为通过。

## 禁止

- 为了让校验通过而手改 `completion`、删历史事件、伪造证据文件；
- 在 FAIL 未清零时继续写决策或经验。

## 校验器的边界

它检查**结构自洽**，不判断内容质量；检查路径存在，不保证文档仍有效。校验通过 ≠ 一切正确。指纹算法在校验器中独立实现，与生成器交叉验证——两处规范漂移会立即暴露。
