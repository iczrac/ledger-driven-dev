---
name: doc-rebuild
description: |
  从 registry 与账本重建规范化项目文档，并生成能力编码全链路索引：
  文档/测试/代码/账本决策/git 提交一一对应。默认不覆盖人工文档。
  Triggers: "重建项目文档", "规范化文档", "生成能力索引", "编码对应",
  "文档和测试对不上", "rebuild docs", "code index", "traceability"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "0.8.0"
  risk_level: write_draft_only
  related_skills: [project-bootstrap, ledger-scan, graph-compare]
---

# Doc Rebuild

把「文档靠人肉同步」改成「文档由事实源渲染」。人不写完成度，也不手改生成文档。

## When to Use

项目接入后需要一套规范化文档；代码/账本变更后想刷新文档；审计问「某个能力编码对应哪些测试和代码」。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | `--target` 项目根；可选 `--out-dir` / `--out` / `--git-trace` |
| 输出 | `docs/generated/{PROJECT_BRIEF,MODULE_MAP,CAPABILITY_INDEX}.md`、`governance/CODE_INDEX.json` |
| 副作用 | 只写生成目录与索引；既有文件默认跳过，`--force` 才覆盖 |
| 保护 | 账本路径剥离仓库根前缀，输出不含机器绝对路径 |

## 步骤

```bash
python3 scripts/rebuild_docs.py --target /path/to/project --dry-run
python3 scripts/rebuild_docs.py --target /path/to/project
python3 scripts/code_index.py --target /path/to/project \
  --git-trace /path/to/project/governance/GIT_TRACE.json
```

## 解读输出

- `PROJECT_BRIEF.md` 的目标/现状来自账本，不是手写口号；
- `CAPABILITY_INDEX.md` 一行一个编码，`decisions` 列为空说明该能力还没有账本决策；
- `CODE_INDEX.json` 的 `commits` 为空通常是还没跑 `trace_git.py`，不是"没有历史"。

## 禁止

- 禁止手改 `docs/generated/**` 当作长期方案；改 registry/账本后重跑；
- 禁止为了让文档好看而补不存在的证据路径；
- 禁止用 `--force` 覆盖人工补充内容而不记录原因。

## 失败处理

| 现象 | 处理 |
|---|---|
| 缺少 registry | 退出码 2，先跑 `project-bootstrap` |
| 文档已存在 | 比对差异后由人决定是否 `--force` |
| 能力编码缺失 | 检查 registry `modules[].caps[].domain` 与序号 |
