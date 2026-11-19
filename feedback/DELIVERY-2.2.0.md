# DELIVERY 2.2.0 — 绑定硬门禁（verified ⟺ bound）

- 日期：2026-11-19
- 状态：已发布（tag v2.2.0；方法仓 53eaff8，主仓 1fc2412b8）
- 批准：用户选「机制治本」——把符号绑定从 shadow advisory 升级为 verified 硬门禁

## 一、从第一性原理定位的病

账本唯一的价值是「它是仓库的真实函数、不可伪造」：
`账本 = f(registry, 仓库, 报告)`。

v2.1.0 把信任从「账本自证」搬到「registry 声明」，但声明本身从未被语义校验。
v2.1.2 的符号绑定 advisory 揭穿了后果：47 个能力里 43 个挂 verified，其中
14 个的测试符号上零个触达实现。根因不是某个 tier 填错，而是——

> **声明权 = 伪造权**：`verified` 只要求「registry 声明的测试在报告里有 pass」。
> 往 `caps[].tests` 塞任意一条 pass 测试路径，能力就能刷成 verified，账本无法
> 分辨它测的是不是本能力。

实锤抽样：`RS.SECTOR.03` impl 是 `sector_benchmarks.py`，4 个声明测试 import
的全是 metadata/fetcher/coverage 别家模块。fresh 绑定报告与 MAPPING-REVIEW
计数逐项一致（bound 29 / via1 3 / unbound 10 / no_impl 1 / no_tests 4），
诊断可信。

## 二、为什么不选「把数字修绿」

MAPPING-REVIEW 给了三选一：补直接单测 / 声明 via / 接受降级。但 14 条里
绝大多数「全库零测试触达 impl」——改声明也改不出绑定，除非补真测试。
那是逐条人审的 registry 数据迁移（需批准），且就算修绿，下次有人塞错路径
照样能伪造。治本是让 `verified` 由代码真实结构决定，不由一行字符串决定。

## 三、交付内容

1. **硬门禁**：`judge_tier` 的 `verified` 改双条件（报告 pass + binding=bound）。
   via1/unbound/no_impl 全降 declared。verified 数必然等于 bound 数，规则单一。
2. **同源绑定**：新 `binding_status_of_tests()` 在 `build()` 内基于实际证据
   `ev["unit_test"]`/`ev["impl"]` 计算（不是 registry 原始声明），写入 cnode。
   这与 `--check` 的可复算口径一致。
3. **防篡改**：第 7 条不变量校验 verified 必带 `binding_status=bound`；
   手改 tier、抹绑定字段、旧账本无字段，都会被抓（2 条负向用例）。
4. **双向负向证明**：4 条 judge_tier 用例（unbound/no_impl/via1 拒绝、bound 放行）
   + 2 条 verifier 用例。
5. **版本与文档**：METHOD_VERSION 2.2.0；EVIDENCE_TIER_SPEC、docs 03/08/11/23、
   CHANGELOG、ontology 派生同步。

## 四、复验（终态）

- 方法仓 `check.sh all` EXIT=0；321 单测全绿（原 315 + 新增 6）；acceptance 目标版本 2.2.0；
  generator 1476 行 < 1500 硬限；
- 主仓干净 clone 重绑：verified 43 → **29**（恰好 = bound 数），18 declared
  （10 unbound + 3 via1 + 1 no_impl + 4 no_tests）；29 个 verified **全部** bound，
  零新增 verified，cap 总数 47 不变——没有任何东西被做绿；
- 真实降级 14 个：COVERAGE.04 / BARRA.03 / CC.02（via1）+ 10 个 unbound + LEDGER.04（no_impl）；
- 报告仍 fresh（绑定集只含 `projects/**`，治理工具改动不影响摘要，无需重跑 <P1> 全量测试）；
- 干净检出 CI 门禁：`OK: 26 pass / 0 fail / 0 na（零放行）` + `OK: 无漂移`，EXIT=0；
  upgrade verify 12 轴全 pass、complete=True；board/work_panel/assets 校验全绿。

## 五、边界（不掩盖）

- 绑定是**必要条件不是充分条件**：有调用关系 ≠ 测的是该能力语义。硬门禁只
  堵「完全无调用关系」的伪造，不保证语义正确——那仍需人审。
- advisory（`--binding-report`）仍读 registry 声明，是独立旁路观察；主仓与
  硬门禁同源（registry 声明了 tests），demo 用 hints 故两者会不同源（已知
  fixture 差异，不影响判定正确性）。
- 14 个能力的 registry 映射**未改**：诚实降级，不是把错的声明改对。修映射
  是独立的、需逐条人审的数据迁移，与本次机制升级解耦。
- 不变量数量不变（扩展第 7 条而非新增），避免契约膨胀。
