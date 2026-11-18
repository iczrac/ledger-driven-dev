---
name: project-bootstrap
description: |
  项目治理初始化：支持 greenfield 新建与 adopt 存量接入两种模式；
  从模板或已确认草稿生成 registry/账本/看板，记录来源 provenance，不覆盖既有文件。
  Triggers: "初始化项目", "新建项目骨架", "立项", "接入历史项目", "生成治理骨架",
  "bootstrap", "scaffold", "init project", "adopt project"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.3.0"
  risk_level: write_with_guard
  related_skills: [expert-route, project-discover, ledger-scan, ledger-verify]
---

# Project Bootstrap

把"一个决定"变成"一个可验证的起点"。新建与存量接入共用一套骨架，但来源不同、纪律相同。

## When to Use

路由结果为空目录（`greenfield-architect`）或草稿已被人确认（`project-archaeologist` 交接后）。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--target`、`--code`、`--name`、`--mode greenfield\|adopt`、可选 `--from-draft` / `--intent` |
| 输出 | `governance/{registry.json,DECISION_LEDGER.json,index.html,build_capability_model.py,verify_ledger.py,run_tests.py}` |
| 副作用 | 写治理骨架；既有文件默认跳过；账本写入 `provenance` 与一条 `D-001` 接入事实 |
| 保护 | 草稿、源码、既有账本永不自动改写；外部路径只保留文件名 |

## 步骤

```bash
# 新建：空目录
python3 scripts/init_project.py --target /path/to/new --code NEW --name "新项目" --intent "新建项目"

# 接入：已确认草稿
python3 scripts/init_project.py --target /path/to/legacy --mode adopt \
  --from-draft /path/to/legacy/governance/registry.draft.json --code LEG --intent "接手历史项目"

# 两种模式都必须做：
cd /path/to/project && python3 governance/build_capability_model.py --root . --dry-run
python3 governance/verify_ledger.py --root . --strict
```

## 解读输出

- `跳过（已存在）` → 保护生效；确认是否该人工合并，不要顺手加 `--force`；
- `provenance.source=template` 表示新建；`governance/registry.draft.json` 表示来自盘点；
- `D-001` 只记录接入事实，不代表任何能力完成；
- dry-run 显示的高等级若与事实不符，先查 `impl` 路径是否误命中。

## 禁止

- 禁止在目标非空时按 greenfield 直接写入；先回路由专家澄清边界；
- 禁止初始化时手填 `level` / `completion` / `history.events` / 看板内嵌数据；
- 禁止用 `--force` 绕过冲突而不记录原因；
- 禁止替人决定哪些历史决策作废——旧资料保留为证据。

## 失败处理

| 现象 | 处理 |
|---|---|
| adopt 找不到草稿 | 退出码 2；先跑 `project-discover`，或显式给 `--from-draft` |
| 草稿 JSON 不合法 | 修正草稿；必须是对象且含 `modules` 数组 |
| 目标目录不存在 | 退出码 2，确认路径 |
| `verify --strict` 失败 | 修 registry 配置后重跑生成器，不手改账本 |
