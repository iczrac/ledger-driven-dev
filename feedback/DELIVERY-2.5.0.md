# DELIVERY 2.5.0 — 专家团自动编排：把路由链变成可执行分工 + 人工批准包

- 版本：v2.5.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过，全量门禁 EXIT=0；主项目推广待用户另行确认（只在干净 clone 操作）

## 一、为什么做这一版

用户目标「整个项目尽量全 AI 驱动」。只读检查发现真正的瓶颈不是门禁太多，
而是**编排层还在人肉**：P0 之前专家契约靠手工读 `EXPERT.md` 注入子代理、
交接靠口头转达、批准包没预生成。P0 先修好路由（未识别指令 fail-closed、
`route` 意图归位、多跳 `handoff.chain`），P1 再把「链 → 行动」落地。

外部 `ontology-driven-dev`（561 star / MIT，真有 Python+Go 底座）评估后
**不引入**：它的七模型 YAML 一旦落盘就成了与账本竞争的第二语义源，8 段硬暂停
正是要摆脱的瓶颈，其「一致性门禁」只有文档规则、无执行器或 CI——项目这边用
可复算脚本做得更严。可借鉴的只是 A/B 标注与完成定义（P2，未在本版做）。

## 二、改了什么

**P0 · 路由修复**（不新增资产）
- 未识别的非空指令 → `needs_clarification`，点名 `intent.json`，`confidence=low`；
  空意图仍默认路由，向后兼容。
- `route` 意图恢复强候选，由 `expert-router` 只读承接；补齐其专属只读命令集。
- `route.handoff.chain` 多跳交接链（3 跳，确定性），文本输出同步展示。

**P1 · expert-run 编排器**（新元工具 + 新技能）
- **`expert_run.py`**（不进治理工具副本）：沿交接链展开逐跳专家契约
  （skills / writes / EXPERT.md）+ 命令分类（readonly / approval / manual）+
  人工批准包。三条铁律：
  1. **零新判定权**——负责人/链/命令全部来自 `route_expert` 与 `EXPERT_CARDS`；
  2. **默认 dry-run 零执行**——不跑命令、不写文件、不碰账本；
  3. **权限授予者 ≠ 被授权者**——`--approved-by` / `--apply` / `register` /
     `unfreeze` 等写动作一律进批准包，只由人执行。
  结论 `run = f(intent, target, route_expert, EXPERT_CARDS, commands_for)` 可复算。
- 命令分类保守：写授权标志压过只读标志（含 `--apply --json` 仍判 approval），
  内联 `python3 -c` 归 manual；批准包命令透传真实 target，复制即可执行。
- 新技能 `expert-run` + 文档 [25-专家团自动编排](../docs/25-专家团自动编排.md)；
  更新 README / docs 10 / 12 / 19 的技能数与引用。
- 16 条单测（先红后绿）；版本 2.4.0→2.5.0；资产摘要 `7b629cec…`；技能数 21→22。

## 三、先红后绿实证

测试中抓到并修复两个真实问题（诚实报告）：
1. **target 未透传**：`_step` 里 `commands_for(expert, ".")` 硬编码占位符，
   批准包命令路径不可直接执行 → 改为透传真实 display，并加
   `test_hardcoded_placeholder_absent` 防回归。
2. **测试假绿**：`test_approval_bundle_aggregates` 原依赖 platform-steward 进入路由链，
   但该意图实际 fail-closed 返回空链，聚合分支从未执行 → 改为直接展开
   `_step(0, "platform-steward", ...)`，不依赖路由可达性。
   另把「所有命令都带 target」的过强断言修正：明确列出 5 条方法仓自检命令
   （check.sh / method_assets / asset_bundle / test_modules 的 --check）为合法例外。

## 四、门禁实证

- 全量 `check.sh` **EXIT=0 / 16 阶段全绿**；
- **361/361 单测**（v2.4.0 是 345，+16 正好）；
- 27 条三态不变量、场景矩阵、文件布局、升级与接入、资产与工作台契约、
  幂等、同步、反向回流、本体层、脱敏、文档链接、验收契约、前置条件全过；
- 可复算：同输入两次 `expert_run --json` 逐字节一致；
- 零执行：跑编排前后 `git status` 不变（13→13），无任何产物落盘；
- 登记自检：资产 8 专家 / 22 技能 / 30 可安装文件，升级定义 6 工具 / 8 迁移。

## 五、边界（诚实说明）

- **不自动执行**：v2.5.0 只产出计划与批准包，不代跑命令。真要「自动跑」由人/平台
  拿批准包执行——这是刻意保留的安全边界，不是功能缺失。
- **不判定业务优先级**：只展开路由结果，业务取舍仍由人 + `ledger-steward`。
- **不引入新事实源**：批准包是内存产物，不落盘；权威源仍是 `route_expert` 与 `EXPERT_CARDS`。
- **主仓未碰**：用户工作区 100 个既有改动全程未动。本版只在方法仓 `ledger-driven-dev` 发版。
- **整包升级待批准**：新增技能触发资产摘要变化，按 `method-assets` 纪律需所有项目
  重新批准升级；本次在干净 clone 验证 `upgrade plan/apply/verify` 可行，真正推广待用户确认。
