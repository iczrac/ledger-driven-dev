# P1 数据迁移预演：写盘后阻断并回滚（未留权威字节）

> 用户指令：「授權下一步」（2026-11-19）。
> 解读：v1.8.0 已完整发版并独立核实，唯一明确的「下一步需独立人批准数据迁移」是
> **P1 最终满足**（主仓 `P` 至少一条能力由其真实 CI 报告升为 `verified`）。
> **裁定：预演证明当前工具链写盘必然破坏 24 不变量，已回滚，未留任何权威字节变更。**

## 一、先给结论

1. **真实报告已拿到**：临时 venv 装齐 <app> 依赖后，24 个账本白名单内的能力引用单测
   **182 passed / 0 fail / 0 error**，JUnit sha256 `bb45007671aabb1a2841ed6b…`。
2. **导入适配链全绿**：`import-report --dry-run` → `overall=pass`、182 用例；
   182/182 由 `classname_to_file()` 反解命中账本白名单真实文件（0 未映射）；
   `default_source_dirs()` 探测出 8 个 `projects/*/{src,tests}`；`source_digest=b2dbd595929e75f0`。
3. **生成器内存判据全绿**：真实报告在 `P` 上 `build()` → `freshness=(True,'fresh')`、
   level 分布 `L5:20/L3:22/L2:5`（**不降级**）、`tier verified:20/declared:27`、
   `verified_coverage=0.43`、`no_regress()=[]`。
4. **但真实写盘破坏账本**：三步 apply 后 24 不变量从 `23 pass + 1 na / all_ok=true`
   跌为 `21 pass + 3 fail`：
   - `encoding_format` 非法码 `<ROOT>.<PROJ>.DATA.READY.01`（5 段）；
   - `history_state_encoding` 历史码 `<PROJ>.x` 与新码失配；
   - `work_items_valid` 工作项 `W-TODO-002 scope 无法解析`（引用旧 code）。
5. 按「诚实 > 绿灯」「先确认数据正常再重建快照」**立即回滚**，账本/看板 hash 逐字节
   回到写盘前基线（`3c478d20…` / `ba1b4fa2…`），`test_report.json` 移除，
   校验器恢复 `23 pass + 0 fail + 1 na`。

## 二、根因（写盘实证，非推测）

生成器 `templates/build_capability_model.py#build` 第 503/596 行：

```python
code = project_cfg["code"]          # registry.json project.code = "<ROOT>"
cap_code = f"{code}.{mcode}.{domain}.{cidx:02d}"
# mcode 已是 "<PROJ>.DATA"（含项目前缀）→ 拼出 <ROOT>.<PROJ>.DATA.READY.01（5 段）
```

而权威校验器 `governance/verify_ledger.py:66`：

```python
CODE_RE = re.compile(r"^[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}$")  # 恰好 4 段
```

账本原生存量码是 `<PROJ>.DATA.READY.01`（4 段）。这是 registry 的「单项目 project.code
前缀」与账本「多项目编码」的**系统性失配**——即 `A-EXECUTION-BLOCKED.md` 第五节、
`RELEASE_CHECKLIST.md:215` 的 `registry/2` 问题。

**v1.8.0 的 `no_regress()` 只修了「降级判定」**（剥离前缀后比较 level），**没有修生成器
写出的 code 本身**：dry-run 判据通过，写盘却把 5 段码写进权威账本，必然被校验器判非法。
这是「判据绿 ≠ 结果绿」的一个真实反例，已如实记录。

## 三、为什么不再继续

- P1 最终满足的真正前置是 **registry 路径/编码契约修复**（让生成器写出 `<PROJ>.x` 而非
  `<ROOT>.<PROJ>.x`，并处理 history/work_items 的引用兼容），即 `registry/2` 多项目数据契约。
- `RELEASE_CHECKLIST.md:215` 明确：`registry/2` 留 **v2.0.0**，需人批准数据迁移 + 备份 +
  **双写兼容期**，且「**不得由 Agent 自动执行**」。
- 「授權下一步」是通用推进授权，未包含破坏性 registry 重构的显式批准；按纪律不越权。

## 四、写盘/回滚证据

| 项 | 写盘前 | 写盘后 | 回滚后 |
|---|---|---|---|
| 24 不变量 | 23 pass / 0 fail / 1 na | 21 pass / **3 fail** / 0 na | 23 pass / 0 fail / 1 na |
| `all_ok` | true | **false** | true |
| 账本 sha256 | `3c478d2060e2de83…` | `<ROOT>.*` 5 段码 | `3c478d2060e2de83…` |
| 看板 sha256 | `ba1b4fa28514303…` | 已改 | `ba1b4fa28514303…` |
| `test_report.json` | 不存在 | 新建 | 移除 |

备份：`P/.ledger-upgrade/backups/20261118T162441Z-p1final`（DECISION_LEDGER + index.html
+ manifest）。批准人字段（预演用）：`用户授权-2026-11-19-下一步-P1最终满足`。

## 五、下一步需人裁决（三选一）

- **A（推荐，符合既有版本经济）**：正式立项 `registry/2` v2.0.0，按 S1→S4 修生成器 code
  契约 + 双写兼容 + 重绑，一次发版；P1 随 v2.0.0 一并满足。需显式授权「扩大范围到 v2.0.0
  破坏性迁移」。
- **B（局部修复，风险中）**：仅修本账本的 registry `project.code`（<ROOT>→按模块归属）或生
  成器 code 拼接，使写出 4 段码，再做 P1 数据迁移。需证明 history/work_items 引用不破，
  且改变 `method_assets`/`ontology_digest` → 需 M4+M5+M7 重绑（一次发版）。
- **C（保持现状）**：P1 维持未满足、`test_results=null`、`activation=unbound`，如实保留。

## 六、作用域与提交

仅新增本文件（`feedback/`，`ZERO` 作用域，不在 `ASSET_GROUPS`）。**不改 ASSET 字节、
不改 `P` 权威账本、不升版本、不打 tag**；`tag v1.8.0` 的资产字节与 `aee3a13` 一致，
tag 复放结论不受影响。所有 JUnit/报告只存在于临时目录，未入库。
