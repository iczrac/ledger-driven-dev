# Demo Shop（示例项目）

一个**虚构**的电商项目，用来演示账本驱动开发（Ledger-Driven Dev）的完整产出。本项目所有代码、决策、文档均为演示内容，不含真实业务数据。

## 看什么

直接用浏览器打开 [`governance/index.html`](governance/index.html)（离线可用），重点看：

- **架构钻取**：项目 → 模块 → 嵌套组件树（点目录逐层展开）→ 文档索引 → 能力编码；
- **能力地图**：4 个能力点的等级、完成度、规划与可点开的文档索引；
- **演进历史**：3 条真实生成事件——初始化基线、定价服务 L2→L5、决策取代引发的索引更新；指纹链可查、当时状态可回放；
- **经验库**：1 条已确认经验（自动附到任务卡）+ 2 个机器识别候选（长期停滞、决策被取代）；
- **全部条目**：3 条决策，含一条 `superseded` 与取代它的 `done`，演示决策演进不改写历史。

## 能力分布

| 编码 | 名称 | 等级 | 说明 |
|---|---|---|---|
| `DEMO.DATA.READY.01` | 数据就绪契约 | L5 | 契约+实现+单测+测试记录+治理门禁，完整闭环 |
| `DEMO.CORE.ORDER.01` | 订单领域模型 | L5 | 同上，关联 D-001 决策 |
| `DEMO.CORE.PRICE.02` | 定价服务 | L5 | 补齐单测与测试记录后由 L2 跃迁；D-003 取代了暂缓补测的 D-002 |
| `DEMO.API.QUERY.01` | 订单查询接口 | L2 | 只有实现，连续两个事件停滞，被识别为经验候选 |

整体完成度 80%。

## 复算

```bash
# 从项目根（ledger-driven-dev/）运行，registry 里的 root 是相对仓库根的
cd ../..
python3 examples/demo-shop/governance/build_capability_model.py \
  --root . \
  --registry examples/demo-shop/governance/registry.json \
  --ledger examples/demo-shop/governance/DECISION_LEDGER.json \
  --board examples/demo-shop/governance/index.html \
  --dry-run
```

去掉 `--dry-run` 即正式重算并同步看板。你会看到：删掉某份测试记录后重跑，对应能力从 L5 回落到 L4——这就是「完成度由证据判定、可回落」。

dry-run 还会打印**下一轮任务队列**（`next_queue`）——按完成度升序排列，每条告诉你要补什么证据、读哪些文档，并附上匹配的成功经验。这是循环协议 SELECT 步骤的机器可读产出。

状态没变时连续重跑，历史事件数和指纹不会变化——历史由指纹驱动，重跑不产生噪音。想看历史前进，补一份证据（如给 `DEMO.API.QUERY.01` 加 `tests/unit/test_order_api.py`）再跑。

## 校验账本

```bash
python3 governance/verify_ledger.py --root . --strict
```

检查 18 条不变量，全部通过返回 0。想看它真的能抓错：把账本里某个 `completion` 改成 0.99 → `completion_matches_level` 报 FAIL；把历史事件的 `fingerprint_before` 改掉 → `history_chain_consistent` 报 FAIL；把已确认经验的 `action` 清空 → `lessons_valid` 报 FAIL。

## 目录

```
demo-shop/
├── governance/         账本、注册表、生成器、校验器、看板
├── src/
│   ├── contracts/      L1 契约
│   ├── domain/         L2 领域实现
│   └── api/            L2 接口实现
├── tests/unit/         L3 单测
└── docs/
    ├── plans/          规划文档
    └── test_records/   L4 测试记录
```
