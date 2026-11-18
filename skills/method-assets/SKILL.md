---
name: method-assets
description: |
  方法论资产清单：把专家、技能、路由卡、模板与编号文档压成确定性 sha256，
  由 upgrade.py 写进目标账本；资产随仓库 tag 升级，权威源不复制进目标项目，
  但任何资产变化都要求项目重新批准升级（M5 整包摘要 + M7 只读副本）。
  Triggers: "专家升级", "技能升级", "资产摘要", "资产漂移", "模板版本", "文档发版",
  "method-assets", "asset digest", "expert version", "skill version"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "1.6.0"
  risk_level: read_only
  related_skills: [ledger-upgrade, expert-route, board-layout, scale-budget, asset-install]
---

# 方法论资产清单（method-assets）

## 输入 / 输出契约

| 命令 | 输入 | 输出 | 副作用 |
|---|---|---|---|
| `method_assets.py --check` | 方法论仓库根（默认脚本所在仓库） | `method-assets-check/1`：齐备性、确定性、摘要 | **无** |
| `method_assets.py --json` | 同上 | `method-assets/1`：分组计数、逐文件相对路径与 sha256、聚合摘要 | **无** |
| `upgrade.py ... plan --json` | `--target P` | 计划里的 `assets.digest` 与 `assets.recorded_digest` | **无** |

退出码：资产组缺文件 / 摘要不确定 → 2；其余 0。

## 回答「专家与 skill 是否一起升级」

**权威源**不复制进被治理项目（`file_layout.py` 的 NOT_IN_TARGET），
但 v1.2.0 起「只绑摘要」已经不够——Agent 在项目里必须能加载技能。于是分两层：

```
方法论仓库 git tag（专家 / 技能 / 路由卡 / 模板 / 文档一起发版）
   → method_assets.py 算出新的整包摘要（本技能负责）
   → 目标项目 upgrade.py plan 发现 recorded_digest 落后，列入 M5 与 M7
   → 人批准 apply：M5 写 governance_meta.method_assets
                    M7 由 asset_bundle.py 装 28 份只读副本到 .workbuddy/
                        写 ASSET_MANIFEST.json 与 governance_meta.installed_assets
   → asset_bundle.py verify + route_expert.py --check-assets
   → verify 的 method_assets / installed_assets 两项 pass，upgrade_complete 才为 true
```

也就是说：整包摘要证明「用哪批规则」，逐文件摘要证明「副本有没有被改」，
**权威源始终只有一份**。用 v1.0 专家卡指挥 v1.1 骨架会被判资产漂移；
项目里手改 `SKILL.md` 会被 `asset_bundle.py verify` 判 drift，
唯一修复是重新人批准安装。详见 [19-专家与技能可用](../../docs/19-专家与技能可用.md)
与 `asset-install` 技能。

## 资产组与下限

| 组 | glob | 下限 |
|---|---|---:|
| experts | `experts/*/EXPERT.md` | 8 |
| skills | `skills/*/SKILL.md` | 20 |
| scripts | `scripts/*.py` | 26 |
| templates | `templates/*` | 4 |
| method_docs | `docs/[0-9][0-9]-*.md` | 21 |
| standard | `docs/STANDARD.md` | 1 |

派生生成物（`docs/generated/*`、`*.json` 报告）**不纳入**，否则每次生成都会改变摘要。
相对路径排序后聚合，输出不含机器绝对路径与时间戳。

## 步骤

1. `method_assets.py --check`：改动专家/技能/模板/文档后先确认清单齐备、摘要稳定。
2. 发版：提交方法论仓库并打 tag；`METHOD_VERSION` 与资产摘要一起变。
3. 对每个目标项目：`upgrade.py --target P plan --json`，看 `assets` / `installed` 与迁移 M5 / M7。
4. 人批准 `apply --approved-by <人>`；再跑 `asset_bundle.py verify --target P --json`
   与 `route_expert.py --target P --check-assets --json`；`upgrade.py verify --json` 中
   `method_assets` / `installed_assets` 都必须 pass。
5. 把新摘要、安装摘要与 `upgrade_log` 末条写进交接卡，交回 `expert-router`。

## 纪律

- 摘要是账本内字段，**不新建 ASSETS.json / 版本清单文件**。
- 禁止为了让 `verify` 变绿而手改账本里的 `method_assets.digest`；那等于伪造版本绑定。
- 资产变了但项目不能立即升级：如实标 `upgrade_complete=false`，不要跳过 M5。
- 新增专家/技能本身就是一次资产变更：写完必须重跑 `--check`，并让所有项目重新批准升级。

详见 [16-升级与迁移](../../docs/16-升级与迁移.md)、[19-专家与技能可用](../../docs/19-专家与技能可用.md)、[10-AI集成](../../docs/10-AI集成.md)。
