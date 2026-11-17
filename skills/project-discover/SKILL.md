---
name: project-discover
description: |
  存量项目只读发现：扫描真实源码/测试/文档，生成 registry 草稿与接入报告；
  保留所有警告，不覆盖既有治理文件，不修改源码与账本。
  Triggers: "盘点历史项目", "梳理存量能力", "接手项目", "发现能力", "迁移到账本",
  "brownfield", "legacy", "adopt", "discover", "扫描目录生成清单"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "0.6.0"
  risk_level: write_draft_only
  related_skills: [expert-route, project-bootstrap, ledger-scan]
---

# Project Discover

历史项目的第一句话不是"我来实现"，而是"我先确认有什么"。本技能只产出草稿与报告。

## When to Use

路由结果是 `project-archaeologist`；目录有历史代码但没有可信账本；已有 registry 想生成对照草稿。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--target`（项目根）、`--max-files`、`--max-caps`、可选 `--out-dir` |
| 输出 | `governance/registry.draft.json`、`governance/ADOPTION_REPORT.md`；`--dry-run` 只打印报告 |
| 副作用 | 只写草稿与报告；既有同名文件默认跳过，`--force` 需人明确授权 |

## 步骤

```bash
# 1. 先看报告，不落盘
python3 scripts/discover_project.py --target /path/to/legacy --dry-run

# 2. 人确认候选模块/警告后写草稿
python3 scripts/discover_project.py --target /path/to/legacy

# 3. 人工精简草稿：删掉非能力文件、合并重复域、按技术栈校准 hints

# 4. 由 bootstrap 技能消费草稿（不直接复制成 registry.json）
python3 scripts/init_project.py --target /path/to/legacy --mode adopt \
  --from-draft /path/to/legacy/governance/registry.draft.json --code LEG

# 5. 对照真实等级
cd /path/to/legacy && python3 governance/build_capability_model.py --root . --dry-run
```

## 解读输出

- `confidence=low` → 没有测试或源码证据，草稿只提供骨架，不要据此声称完成度；
- 警告含"扫描截断" → 提高 `--max-files` 重跑，否则候选清单不完整；
- `candidate_caps` 远大于真实能力数 → 调低 `--max-caps` 并人工合并，不要照单全收；
- 报告中的 `src` 入口决定组件树，若指向过宽目录要手工收窄。

## 禁止

- 禁止把草稿直接当成正式 `registry.json` 而不人工审阅；
- 禁止覆盖既有 `registry.json` / `DECISION_LEDGER.json` / `index.html`；
- 禁止修改历史源码、测试、文档来"配合"扫描结果；
- 禁止把绝对机器路径写进草稿或报告（脚本只输出相对路径）。

## 失败处理

| 现象 | 处理 |
|---|---|
| 草稿已存在 | 比对差异后由人决定是否 `--force`，不默认覆盖 |
| 目标目录不存在 | 退出码 2，确认路径 |
| 未发现源码 | 保留 `CORE` 空模块警告，手工补能力清单 |
| 生成后等级普遍过低 | 检查 `hints` 是否与测试/记录文件名一致，而非手填等级 |
