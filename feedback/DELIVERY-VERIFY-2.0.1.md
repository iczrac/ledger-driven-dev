# v2.0.1 独立交付成果核实

> 性质：发版后的独立复放核实，**不复用发版流程的命令口径**；只读标签干净树与真实 `P`。
> 目标项目记作 `P`；核实只用一个干净的 `git archive v2.0.1` 树（196 文件、无 `.git`）+ 真实 `P`。

## 一、结论

**全部核实项通过：0 项不一致、0 项需修、0 项「声称完成但实际未做」。**

## 二、核心检验：tag 干净树复放

用 `git archive v2.0.1` 检出 196 文件干净树，只用该 tag 自带脚本重算并与 `P` 账本比对：

| 字段 | tag 干净树 | `P` 账本 | 结论 |
|---|---|---|---|
| `method_assets.digest` | `b021d49f36d2eb7a…` | `b021d49f36d2eb7a…` | **全等** |
| `ontology_digest` | `b15889efe5cb2c4b…` | `b15889efe5cb2c4b…` | **全等** |
| `method_version` | `2.0.1` | `2.0.1` | **全等** |

tag 干净树内另跑自带脚本，均通过：

- `acceptance.py --check --json` → `overall=pass`，18 项 checks 全 PASS；
- `upgrade.py --target P verify --json` → `overall=pass`、`upgrade_complete=true`、
  12 pass / 0 warn / 0 fail；
- `ontology.py check --target P --json` → `ok=true`、`drift_count=0`、`binding=pass`。

这一步证明的不是「摘要抄对了」，而是**发布点自带的判定逻辑在 `P` 上仍成立**。

## 三、其余核实（独立口径）

- **主仓终态**：24 条不变量 `24 pass / 0 fail / 0 na`；registry 与 capability_model
  同为 4 个项目 / 20 模块 / 47 能力；47 个 code 全四段，迁移前后逐项全等；
  level `L5:20/L3:22/L2:5` 不降级；tier `verified:20/declared:27`。
- **P1**：20 个能力由同一份真实报告（182 passed / 0 fail）升 `verified`；
  `activation.state=active`；未伪造任何用例状态。
- **P2**：`ontology check --target P` → `ok=true`、`drift_count=0`、31 条公理；
  registry 与账本同为 4 项目，E7 在本版由容器迁移真正治愈，不再靠单项目形状掩盖。
- **P3**：`acceptance.roadmap_consistency=pass`，顺延表锚点一致。
- **双读**：单项目模板仍产出 `DEMO.DATA.READY.01`，多项目 monorepo 产出四段码；
  生成器、校验器、投影器共用 `registry_codec.py`，`trace_common` 五段码裸拼已删除。
- **审计诚实**：S4 备份、CAS 重算、M4/M5/M7 重绑、历史新 event 与升级日志均有记录；
  L7 红灯在前，绿灯在后，未改验收期望提前放行。
- **测试**：方法仓全量 282/282 单测通过；schema 专项 7/7 通过；
  一次合并 `check.sh` 在测试阶段因环境 10 分钟上限被 SIGTERM，
  后续非测试阶段已逐项独立复跑通过，未把超时粉饰为通过或失败。
- **仓库完整性**：`git fsck --no-reflogs` 无 `missing` / `error` / `fatal`；
  存在若干 dangling blob（历史写盘/暂存残留），不构成本次发布对象缺失。
  核实时刻远端 `main=cd46413`、`tag v2.0.0=6419f99…`（未变）、
  `tag v2.0.1=67e4cb59…`。本核实文档提交后 `main` 会前进一提交，tag 不变。

## 四、边界与未做

- 语义图 R4（Statement 再化 / K3 推理机 / 最小割集 RCA）未实现；本版只做 registry 容器与 codec 契约；
- `scale_budget` 告警、6 条 open 观察按既有状态保留；
- 目标项目根仓库有大量既有未提交文件，本版只改治理文件并保留备份，不代替用户整体提交主仓。

## 五、提交

仅新增本文件（`feedback/`，`ZERO` 作用域，不在 `ASSET_GROUPS`）；**不改 ASSET 字节、
不改 `P` 账本、不升版本、不打新 tag**，因此 `tag v2.0.1` 的资产字节与本核实文档提交前保持一致。
