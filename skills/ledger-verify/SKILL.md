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

## 禁止

- 为了让校验通过而手改 `completion`、删历史事件、伪造证据文件；
- 在 FAIL 未清零时继续写决策或经验。

## 校验器的边界

它检查**结构自洽**，不判断内容质量；检查路径存在，不保证文档仍有效。校验通过 ≠ 一切正确。指纹算法在校验器中独立实现，与生成器交叉验证——两处规范漂移会立即暴露。
