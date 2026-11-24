---
name: layout-inspect
description: |
  检查「引入治理方案后」项目的文件架构：引入前后差异、目录含义、所有权分层、
  哪些文件能改、哪些是生成物、有没有第二事实源或越界文件。接手项目、初始化前后、
  升级模板、审计目录结构时使用。
  Triggers: "文件架构", "目录含义", "引入后多了什么", "哪些文件能改", "目录结构",
  "治理目录", "接手项目先看目录", "file layout", "directory map", "layout diff"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "2.0.0"
  risk_level: read_only
  related_skills: [expert-route, project-bootstrap, project-discover, doc-rebuild, scenario-guard]
---

# 文件架构检查（layout-inspect）

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 专家路由与资产/账本校验走唯一入口：`python3 scripts/ledger_entry.py --intent "任务描述"` 或 `--check-all`；任一门禁失败即退出码 1（fail-closed）。
- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。


## 输入 / 输出契约

| 项 | 说明 |
|---|---|
| 输入 | `--target P`；可选 `--check`、`--emit-md M`、`--json`、`--strict` |
| 输出 | `file-layout/1` 定义统计，或 `file-layout-diff/1`：阶段、已在位条目、缺失必需、按需未跑、`governance/` 越界文件、下一步提示 |
| 副作用 | **无**（`--emit-md` 只写指定的 Markdown，不碰目标项目任何文件） |
| 退出码 | 0 = 正常；2 = 清单自检失败、目标不存在，或 `--strict` 下存在必需缺失 / 越界文件 |

## 何时用

1. **接手任何项目**：先确定它在 `bootstrap / skeleton / governed` 哪个阶段，而不是先读源码猜。
2. **初始化前后**：用 `--diff` 对比引入前后多出哪些文件，确认没有覆盖人工内容。
3. **升级模板**：`--check` 验证目录清单与产出脚本源码仍一致；再用同步门禁比对工具副本。
4. **审计**：`governance/` 出现清单外文件时报警，防止散落报告变成第二事实源。

## 步骤

```bash
# 1) 清单自检（与代码交叉验证）
python3 scripts/file_layout.py --check

# 2) 只读对比目标项目
python3 scripts/file_layout.py --diff --target /path/to/project
python3 scripts/file_layout.py --diff --target /path/to/project --strict --json

# 3) 需要完整目录全量表时渲染（生成物，勿手改）
python3 scripts/file_layout.py --emit-md docs/generated/FILE_LAYOUT.md
```

判断顺序：

```
phase=bootstrap  → 先跑 init_project.py（greenfield / adopt 由 expert-route 决定）
phase=skeleton   → 骨架在但账本无 capability_model，跑 build_capability_model.py --dry-run 后正式生成
phase=governed   → 写入前先跑 scenario-guard，再按 next_queue 执行
unexpected 非空  → 不要直接删；先确认是不是人工报告，裁决后并入账本 entries 或移出 governance/
```

## 七层所有权（不得混淆）

| 层 | 路径 | 能否手改 |
|---|---|---|
| 业务层 | `src/`、`tests/`、`docs/plans/`、`docs/test_records/` | 可，位置不变 |
| 事实源层 | `governance/registry.json`、账本 `entries` | 可，但按纪律（唯一清单 / 脚本写入） |
| 派生层 | 账本 `capability_model` / `history` / `lessons`、`index.html` 的 EMBED、`governance/*.json`、`docs/generated/*` | **禁**，改事实源后重跑 |
| 工具层 | `governance/*.py` 三个模板副本 | **禁**在目标项目里改，升级靠 `upgrade.py` 同步 |
| 草稿层 | `registry.draft.json`、`ADOPTION_REPORT.md` | 人工精简后才可成为事实源 |
| 运行时层 | `.ledger-upgrade/`、`.ledger-write.lock` | 不是事实源；备份/锁由脚本管理 |
| 资产层 | `.workbuddy/experts/`、`.workbuddy/skills/`、`governance/ASSET_MANIFEST.json` | **禁**手改；只读部署副本，`asset_bundle.py verify` 逐字节校验 |

`lifecycle.log`、`capability_model`、`retired_caps`、`governance_meta`、`access` 等是**账本内 JSON 字段**，不是 `governance/` 里的独立文件；找不到它们是正常的，不要补建。

## 失败处理

| 现象 | 处理 |
|---|---|
| `--check` 报「清单与代码漂移」 | 产出脚本改名或默认输出变了：先改 `scripts/file_layout.py` 的 `ENTRIES`，再改文档，不要改正则绕过 |
| `missing_required` 有条目 | 按 `hint` 走初始化；若本该存在，检查是否被误删或 `.gitignore` 屏蔽 |
| `unexpected` 有条目 | 可能出现第二事实源；移交 `ledger-steward` 裁决，不自行删除 |
| `--strict` 返回 2 | CI 应停下；先修目录，不要继续写入账本 |

## 边界

- 只判断「文件在不在、有没有越界」，**不判断内容真实性**：内容靠 31 条不变量与场景预检。
- 不搬迁、不重命名、不删除任何项目文件；`--diff` 全程只读。
- 方法论仓库的 `experts/` / `skills/` / `scripts/` / `docs/01-21` 不属于被治理项目，不要在目标项目里找它们；整包摘要进 `governance_meta.method_assets`。v1.2.0 起例外是 M7 安装的**只读副本** `.workbuddy/`，由 `ASSET_MANIFEST.json` 与 `installed_assets` 绑定，`--diff` 标为 `on-demand`（不出现也正常）。
- `.ledger-upgrade/` 与 `.ledger-write.lock` 是运行时层（升级备份 / 写入互斥），不在 `governance/`，不是事实源。

## 关联

- [15 · 引入后的文件架构](../../docs/15-文件架构.md)
- [FILE_LAYOUT 全量表](../../docs/generated/FILE_LAYOUT.md)
- [06 · 落地指南](../../docs/06-落地指南.md)
