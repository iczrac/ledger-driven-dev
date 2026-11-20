# DELIVERY 2.4.0 — 复述门：让意图被听懂之后再路由

- 版本：v2.4.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过，全量门禁 EXIT=0；主项目推广待用户另行确认（只在干净 clone 操作）

## 一、为什么做这一版

专家团闭环（v2.3.0）跑起来后暴露一个真实的洞：`route_expert.py` 面对
「让专家团接管全流程」这类编排元指令返回 `intents=[]`，然后照常路由——
**意图没被听懂，机器却往下走了**。路由只负责「已明确意图 → 谁负责」，
不负责把模糊意图变明确，中间缺一环。

外部方法对照（wquguru 拆解 @poteto 的 Agent 工程哲学）提供了「间接提示词：
先让 Agent 用自己的话复述问题、反向采访人」的思路，价值成立。但评估后否决了
用某图形化建模 prompt 规范实现：它零代码、产 SVG、不可机读、无退出码，
进不了 fail-closed 链；若以图为判定依据，等于新造一个不可复算、可伪造的
声明面，与 v2.2.0 刚堵死的「声明权 = 伪造权」冲突。

于是取「复述」的思路，用项目自己的第一性原理落地：**结构化声明 + 机器锚定**。

## 二、改了什么

- **新元工具 `intent_restate.py`**（不进治理工具副本）：人话 → `intent.json`
  （意图 / 能力 code / 写入范围 / 开放问题）→ 用真实 registry 与账本机器校验。
  8 道校验：schema / 复述增量 / 意图合法 / **能力码锚定** / 写入范围 / 只读不写 /
  意图唯一 / 元指令披露。三态 `allow / need_clarification / reject`（退出码 0/1/2），
  `结论 = f(声明, registry, 账本)` 可复算、只读、零第三方依赖。
- **`route_expert.py` 接入前置**：新增 `--intent-file`，提供时先跑复述门，
  非 allow 即 `route.blocked=true`，`fix` 并入 `needs_clarification`；
  **不提供时行为与旧版完全一致**（11 条既有路由测试回归通过）。
- 新技能 `intent-restate` + 文档 [24-复述门](../docs/24-复述门.md)；更新 README /
  10-AI集成 / 12-专家路由 / 19-专家与技能可用的技能数与引用。
- 11 条单元测试（routing 模块）；测试资产计数从硬编码 28/20 改为从
  `method_assets.manifest()` 动态推导，消除同类硬编码漂移。
- 版本 2.3.0→2.4.0；资产摘要 `f677813e…`；技能数 20→21。

## 三、压测实证（先红后绿）

原型阶段用 10 个边界样本压测，首轮 8/10，暴露两个真实漏洞并修复：
1. **只读意图越权写入**：`verify`（审计）声明写 `src/**` 竟 allow →
   新增 `readonly_no_write` 校验 → reject。
2. **多意图竞争**：`["new","adopt","code"]` 竟 allow →
   新增 `intent_unambiguous` → need_clarification。

修复后 10/10 通过。正式版三案（元指令 / 幻觉码 / 合法意图）判定一致：
`need_clarification / reject / allow`，8 项校验全记录，可复算两次逐字节一致。

## 四、门禁实证

- `bash scripts/check.sh` **EXIT=0**，全 16 阶段绿：
  **341/341 单测**（v2.3.0 为 330，+11）、测试架构 6 模块 32 文件、
  27 条三态不变量、场景矩阵、文件布局、升级与接入端到端、资产与工作台契约、
  幂等、同步、反向回流、本体层、脱敏与文档内链、验收契约、前置条件。
- `upgrade.py check`：6 工具 / 8 迁移 / 19 步升级后流程自检通过。
- `method_assets --check`：91 文件 / 摘要 `f677813eda8a783a` 一致。
- `route_expert --check-assets`：8 专家 / 21 技能 / ok。

## 五、范围边界与已知取舍

- 复述门是**元工具**（`scripts/`），与 `route_expert` 同类，**不是**治理工具副本，
  故未纳入 TOOLING/templates/init_project 副本清单，也未新增方法仓自举能力点。
- 意图分类仍是关键词集合（对齐 `route_expert.INTENT_PATTERNS`），复杂语义
  走 fail-closed 让人确认——这是保守设计，不是缺陷。
- 主项目推广未在本版执行：会触发整包升级 + 所有项目重新批准（method-assets 纪律），
  且主项目工作区有 100 个既有改动，须在干净 clone 中另行确认后进行。
- 图形化建模规范（visual-model）未纳入资产，仅在 docs/24 记录否决理由。

## 六、交付清单

- [x] `scripts/intent_restate.py`（正式元工具 + `gate()` 供路由调用）
- [x] `skills/intent-restate/SKILL.md`（21 号技能）
- [x] `scripts/route_expert.py` 接入 `--intent-file` 前置门（向后兼容）
- [x] `tests/routing/test_intent_restate.py`（11 条）+ `tests/MODULES.json`
- [x] `docs/24-复述门.md` + README / docs 10/12/19 / CHANGELOG / RELEASE_CHECKLIST
- [x] `tests/views/test_assets.py` 计数动态化
- [x] 全量门禁 EXIT=0 / 341 单测 / 发版 tag v2.4.0
