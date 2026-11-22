# 交付卡 · v2.19.0

**主题**：风险下降判据与关闭回路——把「分数变旧」「风险下降」「人工裁决关闭」三件事分开。

## 做了什么

1. 新增 `docs/36-风险下降判据.md`：风险严重度（severity）与信号新鲜度（freshness）是两个正交维度。
   风险下降须同时满足同主体、同口径、方向改善且持续、人工裁决关闭四条；明确列出
   「衰减 ≠ 下降／跨母体 ≠ 下降／单点 ≠ 趋势／猜指标 = 误挂」四类 fail-closed。
2. `scripts/runtime_signals.py` 新增三个只读纯函数：
   `extract_metric_trend` 从原文抽取显式、连续、同口径的箭头序列（异口径混值返回空）；
   `risk_outcome` 并列输出 `decay_vs_metric`（`divergent` / `aligned` / `n/a`）与
   `outcome=observed_only`；`signal_disposition` 从账本决策判定信号是否已显式关闭。
3. 关闭判据不新增事实源：复用决策 schema，要求 evidence 指向 `*.md#E<n>`、
   status ∈ {done, decided, approved}、decision/title 含显式关闭意图标记；
   「引用但不关警报」判 `open`。
4. 主仓以只读 CLI 接入（独立入库）；方法仓只提供纯函数与判据文档。

## 验证

- 全量测试 461/461（`runtime_signals` 从 446 增至 461 例，含趋势抽取、衰减方向、
  异口径拒绝、关闭回路正反向与只读性）。
- `verify --strict` 31 条检查无 fail（1 条目标编排为 na）；生成器 `--check` 退出码 0；
  ontology 漂移 0；`check.sh` 16 阶段全绿。
- 真实事件实证：带阈值序列的信号判 `divergent`（分数降、指标升），混合方向判 `n/a`，
  异口径链与单点值均 fail-closed 返回空；对「引用但明写不关警报」的真实决策判 `open`。
- 方法仓与主仓的 `runtime_signals.py` 逐字节一致（sha256 `9cb07837…`）。

## 边界

- 观察器只读，不写账本、不关警报、不改能力等级、不下「风险已下降」结论。
- 具体风险关闭须先真实降低指标，再由 operator 写入带显式关闭意图的账本决策；本版不代裁。
- 目标项目的 E1（行为缺陷）与 E4（单调上升的 seam）仍保持 open；本版只交付判据与机制。
