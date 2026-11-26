---
name: asset-install
description: |
  让专家与技能在目标项目里真正可用：只读安装、逐文件清单、账本绑定、漂移检测。
  Triggers: "资产安装", "专家可用", "技能可用", "asset install", "installed assets",
  "SKILL.md 漂移", "EXPERT.md 缺失", "upgrade M7"
license: MIT
metadata:
  author: iczrac
  version: "2.0.0"
  risk_level: write_with_guard
  related_skills: [method-assets, ledger-upgrade, expert-route, agent-gate]
---

# Asset Install

## 执行语境（先读）

本文命令示例中的 `scripts/xxx.py` 是**方法论仓库**（`ledger-driven-dev/`）内的权威工具路径，只在该仓库根目录执行才成立。

在已安装本体系的目标项目根目录下：

- 目标项目的 `scripts/` 下没有方法仓工具副本；照抄 `python3 scripts/route_expert.py` 一类命令会 file not found，不要照抄。
- 需要方法仓工具本体时，切到方法仓根目录执行。


## When to Use

- 升级后需要证明「Agent 在项目里能加载这批专家/技能」，而不只是账本里有一个 digest；
- 项目内 `.workbuddy/skills/` 或 `.workbuddy/experts/` 被人改过、缺文件、留着旧版本；
- 发布新 tag 后要把新专家/技能推到已接入的项目。

## 核心判断

v1.1.0 只有 `governance_meta.method_assets` 摘要，目标项目里没有一份可加载的 SKILL.md。
v1.2.0 用 **只读部署副本** 解决：权威源仍是方法论仓库 tag，副本逐字节一致、禁止编辑。

| 层 | 内容 | 谁写 |
|---|---|---|
| 权威源 | `experts/*/EXPERT.md`、`skills/*/SKILL.md` | 方法论仓库 + git tag |
| 部署副本 | `<P>/.workbuddy/{experts,skills}/<name>/…` | `asset_bundle.py install --apply` |
| 副本清单 | `<P>/governance/ASSET_MANIFEST.json` | 同上（逐文件 sha256 + 整包 digest） |
| 账本绑定 | `governance_meta.installed_assets.digest` | `upgrade.py` M7 |

**不产生第二事实源**：副本是带 sha256 的只读产物，任何手改都会被判 drift；
清单只记哈希，不含规则正文；`method_assets` 摘要与 `installed_assets` 摘要同源同算法。

## 步骤

```bash
python3 scripts/asset_bundle.py --check
python3 scripts/asset_bundle.py install --target P --json             # 只读预演
python3 scripts/asset_bundle.py install --target P --apply \
    --approved-by "审批人姓名" --json                                  # 人批准才写盘
python3 scripts/asset_bundle.py verify --target P --json              # 副本/清单/账本三方一致
python3 scripts/route_expert.py --target P --check-assets --json      # 路由真的读到了资产
python3 scripts/upgrade.py --target P verify --json                   # installed_assets 项必须 pass
```

日常升级不需要单独跑 install：`upgrade.py apply` 的 M7 会统一备份、安装、绑定。
`rollback` 会恢复旧副本，并移除升级前不存在的安装产物（仅按 `.workbuddy/` 白名单）。

## 输出契约

`asset-install-verify/1`：`ok` / `digest` / `file_count` / `counts` / `errors[]`。
`ok=false` 时退出码 1，常见错误：

| id | 含义 | 修复 |
|---|---|---|
| `missing` | 副本缺失 | 重新批准安装 |
| `drift` | 副本内容与权威源不一致 | 重新批准安装（不要手改追平） |
| `manifest_*` | 清单缺失 / 摘要不符 / 文件集合不符 | 重新批准安装 |
| `ledger_binding` | 账本没绑当前摘要 | 跑 `upgrade.py apply` 的 M7 |

## 禁止

- 在目标项目里编辑 `SKILL.md` / `EXPERT.md` 来「修好」校验；
- 为了让 `verify` 变绿手改 `ASSET_MANIFEST.json` 或 `installed_assets.digest`；
- 把整包资产复制进 `governance/` 造第二份规则；
- 跳过 `--approved-by` 自行安装。

## 失败处理

- `stale_protected`：旧清单里的文件被人改过，脚本不会删除，需人工比对后决定；
- `--check-assets` 报 `incomplete`：路由卡引用了不存在的专家/技能，先修资产再发版；
- Windows 等平台无 `fcntl` 不影响安装，但并发保护降级（见 `agent-gate`）。
