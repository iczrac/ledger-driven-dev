# v1.8.0 独立交付成果核实

> 性质：发版后的独立复放核实，**不复用发版流程的命令口径**；只读取证与临时副本，不写权威字节。
> 目标项目记作 `P`；核实只用一个干净的 `git archive v1.8.0` 树（177 文件、无 `.git`）+ 真实 `P`。

## 一、结论

**全部核实项通过：0 项不一致、0 项需修、0 项「声称完成但实际未做」。**

## 二、核心检验：tag 干净树复放

用 `git archive v1.8.0` 检出 177 文件干净树，**只用该 tag 自带脚本**重算并与 `P` 账本比对：

| 字段 | tag 干净树 | `P` 账本 | 结论 |
|---|---|---|---|
| `method_assets.digest` | `ecf7f2c9033d43149229`（85 文件） | `ecf7f2c9033d43149229` | **全等** |
| `ontology_digest` | `63ab23dfe7c59ff27118` | `63ab23dfe7c59ff27118` | **全等**（本版 SOURCE_FILES 变化，已重绑） |
| `installed_assets.digest` | — | `927bc681346f4db34613`（28 份） | 已由 M7 安装 |
| `method_version` | 1.8.0 | 1.8.0 | **全等** |

tag 干净树内另跑自带脚本，均通过：

- `acceptance.py --check --full` → `overall=pass`（十项 checks 全 PASS）；
- **`upgrade.py --target P verify --json`（tag 自带升级器复验真实项目）** →
  `overall=pass`、`upgrade_complete=true`。

这一步证明的不是「摘要抄对了」，而是**发布点自带的判定逻辑在 `P` 上仍成立**。

## 三、其余核实（独立口径）

- **门禁与计数**：独立分段验证——264/264 单测 OK、`acceptance/1` 十项 PASS、
  `test_modules.py --check` 6 模块/25 测试文件一致、`upgrade.py check` 3 工具/8 迁移/19 步、
  卫生脱敏 CLEAN、幂等 PASS。完整 16 阶段单次执行因测试阶段约 280s 超出工具时限未完成，
  但**各阶段单独复跑无红灯**。
- **主仓边界**：升级 verify `23 pass + 0 fail + 1 na`（唯一 na 是 `evidence_rebaseline`）；
  47 能力 level 保持 `L5:20/L3:22/L2:5`（未降级）；`test_results=null`、
  `activation.state=unbound`（未伪造 verified）；3 工具 sha 与权威模板逐字节一致。
- **审计诚实**：`upgrade_log seq=7` 是一次 rollback（首次 apply 误用 `PREVIEW-DRY-RUN`
  作批准人字段）、`seq=8` 是正确批准人 `用户授权-2026-11-18-v1.8.0-扩大范围` 的正式 apply；
  两次都留在 append-only 审计链上，未抹除。
- **观察包 append-only**：权威三包 sha 全程不变
  （`observations 414506bd… / baseline 06d950c6… / post-v150 e8cf19ae…`）；
  `ledger_feedback.py export` 对 demo-shop 导出 10 条、幂等。
- **发布点与仓库完整性**：`git archive` 177 文件；`git fsck --no-reflogs` 无
  `missing` / `error` / `fatal`；`git ls-remote origin` 确认 `refs/heads/main=aee3a13`、
  `refs/tags/v1.8.0=67b8ab65…` 均已推送；`tag v1.7.0` 对象本地与远端同为
  `3fe13763…`（**未变**）。
- **防过度声明**：S1/S2/S3/发版四份证据文档齐备；RELEASE_CHECKLIST 的 `registry/2`
  仍为未勾、语义图仍顺延；`P1 最终满足` 被明确标注为「需独立人批准数据迁移」，
  没有声称本版已升 verified。

## 四、边界与未做

- P1 最终满足、P2 重查、语义图（R4）仍需主仓数据迁移 + 人批准，本版未做；
- 主仓 `registry.json` 的目录/hints 字段本版未写盘；
- E7 `cardinality_contradiction`、`scale_budget` 阈值告警、6 条 `open` 观察保留。

## 五、提交

仅新增本文件（`feedback/`，`ZERO` 作用域，不在 `ASSET_GROUPS`）；**不改 ASSET 字节、
不改 `P` 账本、不升版本、不打新 tag**，因此 `tag v1.8.0` 的资产字节与 `aee3a13`
保持一致，tag 复放结论不受影响。
