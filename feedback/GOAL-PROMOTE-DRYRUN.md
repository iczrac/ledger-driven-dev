# 推广目标 dry-run 取证（v2.13.0 → 主仓）

> 一次性**取证报告**，不是状态清单、更不是第二事实源。
> 观察的权威源是 `feedback/observations.jsonl`；发布状态的权威源是
> `DECISION_LEDGER.json`；主仓真实状态的权威源是主仓治理目录。
> 本文只回答一件事：**v2.13.0 的目标编排能否在主仓真实复杂度上驱动推广，卡在哪。**
> 全程只读主仓 git 对象导出干净快照，未触碰主仓工作区 105 处既有改动。

## 一、方法

1. `git -C <main-repo> archive HEAD | tar -x` 导出干净快照（v2.1.2、47 能力点、10 条 next_queue）。
2. 在快照治理账本注入真实目标 `G-PROMOTE-01`：
   - 描述：「将 目标项目 P治理从 v2.1.2 推进到 v2.13.0；以真实队列能力点
     `P.DATA.READY.01` 达 L5 作为可机读达成信号」
   - 判据：`cap_level(P.DATA.READY.01) >= 5`；预算 `max_loops=3`
3. `python3 scripts/goal_loop.py --target <snapshot> --goal-id G-PROMOTE-01 --json`
4. 逐条核对 `observations.jsonl` 的 6 条 open 在主仓当前状态的实际落点。

## 二、循环结果

| 项 | 值 |
|---|---|
| verdict | `deactivated` |
| stop_reason | 循环预算用尽，目标失活 |
| rounds | 3（每轮路由 `goal-orchestrator`，`verify failed=0 / na=0`） |
| 待批准命令 | 4 条：`goal-advance` ×3 + `goal-deactivate` ×1 |
| 判据达成 | 0 / 1（三轮均未满足） |

**结论：循环骨架在真实主仓账本上跑通了**——路由、验证、预算、失活全链路无异常，
每轮都过主仓自己的 `verify_ledger.py`，没有 fail-closed 误伤。

## 三、暴露的四个 blocker

这些不是脚本崩溃，而是「能跑完但推不动目标」的结构性问题：

1. **判据表达力不足**：`goal_ledger.evaluate_criteria` 只支持 `cap_level /
   invariant_all / queue_empty`，无法表达 `method_version >= 2.13.0`。
   推广这种治理目标只能借用一个代理能力点，达成信号不直接。
2. **无进展检测**：三轮取到的都是同一条 `next_queue`（`P.DATA.READY.01`，
   action「tests/unit/ 有对应测试」）。`goal-advance` 只改 `current_loop`，
   不改队列、不改能力等级，所以循环在原地打转。
3. **达成判定与实际工作脱节**：dry-run 只做只读计划；真实 apply 时仍需人/专家
   真的完成队列任务并重算能力模型，判据才可能满足。当前循环把「推进预算」
   和「推进工作」混成一件事。
4. **旧验证器不护新目标**：主仓 `verify_ledger.py` 是 v2.1.2 副本，不含第 30 条
   `goal_loop_valid`。因此本轮验证 `failed=0` **并不证明注入的目标结构合规**——
   推广时若不同步验证器，新目标事实上处于无守护状态。

## 四、准入检查：6 条 open 观察的落点

| obs_id | 症状（v1.2.1 时点） | 主仓当前 | 判定 |
|---|---|---|---|
| `OBS-398702b044d3` | 实测报告未绑定，L5 能力无法 verified | `work_items` open=0；`P.DATA.READY.01` 仍 L2/declared | 部分：TODO 已关，证据仍未绑定 |
| `OBS-3e1dc0bf5d08` | E7 单项目 registry，4 项目被压成 1 | registry 已有 4 个 `projects`；方法仓 `registry/2` + 唯一 codec 已支持多项目 | **已解决**（v2.0.0/v2.0.1） |
| `OBS-4a5df8fa3375` | access 名册为空，默认拒绝无激活路径 | `access.agents = 0` | 未解决（需人批准注册最小名册） |
| `OBS-6d8fd8882341` | lifecycle 未登记，缺失即放行 | `lifecycle = null` | 未解决 |
| `OBS-8e793c179a37` | 节点测试结果投影未绑定 | `test_results` 字段存在，能力仍 declared | 部分：字段有，绑定未生效 |
| `OBS-ae2cdd6e8130` | 经验候选未确认 | `lessons.candidates` 28 条全 open | 未解决（规模扩大） |

**关键判断**：这 6 条都是 `source_ref=project:` 的目标项目观察，**不是方法仓待办**。
其中 E7 已被后续版本解决；其余是「主仓推广待办」，恰好构成推广目标的成功判据来源。
这印证了主线 A 与准入检查 B 是同一条线。

## 五、v2.14.0 复跑：两个 blocker 已修，暴露出更前置的真摩擦

针对第三节的 blocker 1/2/3，方法仓已补：
- `goal_ledger` 新增 `method_version`（语义版本比较，修 2.9/2.10 排序坑）与
  `level_progress`（等级相对 baseline 的提升）两个 metric，含参数校验与 fail-closed；
- `goal_loop` 新增 `progress_fingerprint`（任务 + 相关能力等级 + 方法版本）与
  `stall_limit`（默认 2）：连续无进展即 `stagnated` 暂停并给四要素结构化提议，
  不再烧满预算后 `deactivated`；新增 `--stall-limit` CLI。
- 第 30 条不变量扩展：账本侧拒绝非法新判据；单测 29/29 通过。

**在同步 v2.13 验证器 + `derived_issues.py` 的干净 clone 上复跑**（目标 `G-PROMOTE-02`，
判据 = 版本达标 ∧ `P.DATA.READY.01` 由 L2 升 L5）：

| 轮次 | 路由 | 验证 | 判据 | 结论 |
|---|---|---|---|---|
| 1 | goal-orchestrator | **fail**：`verified_tier_traceable` | 未评估 | `verify_failed`，立即停 |

失败详情：`P.DATA.*` 命名空间下 5 个能力点标 `verified` 但证据分层 `unbound`。
这正是 v2.2 `verified⟺bound` 不变量要抓的历史脏数据。

**结论修正**：推广的第一道门不是目标循环，而是**账本本身不合规**。旧账本带着
5 处 `unbound_verified`，任何新验证器都会在第 1 轮 fail-closed 停住——这是正确行为，
不是循环缺陷。目标循环的新能力（停滞检测、版本判据）尚未被触发，因为验证门先行拦下。

### 修订后的下一步顺序

1. **先修账本证据分层**：把 5 处 `unbound_verified` 降级为 `declared` 或补齐绑定证据；
   属主仓真实工作，须人批准，不能由目标循环代劳。
2. 账本过验证后重跑 dry-run，此时才会进入停滞检测与判据评估路径。
3. 确认 verdict 为可判定结果后，再申请把网关命令逐条人批准回流。

> 本轮仍未写主仓、未执行任何网关命令。方法仓代码变更见 v2.14.0；
> 本报告与复跑 JSON（`/tmp/promote-dryrun-v5.json` 为临时取证，不入库）为证据。

## 六、修账本后复跑（人批准 · 干净 clone）

接第五节的顺序第 1 步。人批准后，在**干净 clone**（`git archive` 快照，未写主仓工作区）
上按"可复算、不伪造"的路径修复账本证据分层：

1. **纠正数量口径**：报告前文的"5 处"是验证器只打印 `bad_verified[:5]` 造成的错觉。
   实测旧账本标 `verified` 却缺 `binding_status=bound` 的能力点共 **43 个**
   （`P.DATA.*` 只是前 5 个）。只修 5 处验证门仍会因其余 38 处 fail。
2. **同步权威工具**：把方法仓 5 个治理工具副本（`build_capability_model.py` /
   `binding_advisory.py` / `derived_issues.py` / `verify_ledger.py`）下发给 clone，
   替换其 v2.1.2 旧副本（旧 generator 的 `judge_tier` 无绑定参数）。
3. **可复算重算**：`build_capability_model.py --strict-evidence` 内部用
   `SymbolIndex` 做符号级绑定判定（AST 解析测试的 import，沿再导出链追到
   `evidence.impl`），据此自动定 tier——**非人工填写**：

   | 绑定判定 | 数量 | 处理（verified⟺bound） |
   |---|---|---|
   | bound | 29 | 补 `binding_status=bound`，保住 `verified` |
   | via1 / unbound / no_impl / no_tests | 14 | 降 `declared`，配 `binding_status` + 派生 issue |

   结果：`verified 43→29`、`declared 4→18`，`unbound_verified=0`；18 条非 bound
   能力各生成一条 `source=derived` 的 open issue（`derived_issues.sync_derived_issues`）。
   这与方法仓 v2.2.0 升级时"verified 43→29"的历史口径一致。
4. **验证门激活**：`verify_ledger.py --strict` 从 `26/30 + 3 na` 变为
   **30/30 全绿**——先前 na 的 `binding_issues_derived` / `analytics_maturity_valid` /
   `analytics_d3_projection_valid` 全部由旧账本升级后激活并通过。
   注入目标 `G-PROMOTE-02` 与其他人工字段在重算中原样保留。

**复跑结果**（同一 `G-PROMOTE-02`，`--stall-limit 2`）：

| 项 | 值 |
|---|---|
| verdict | `stagnated`（目标 `paused`） |
| stop_reason | 连续 2 轮无进展，已暂停待真实工作推进 |
| rounds | 2（每轮 `verify.failed=0 / na=0`，30/30 全绿） |
| 待批准命令 | 3 条（停滞提议的四要素网关命令） |

**结论**：账本合规后，循环不再第 1 轮 `verify_failed` 硬停，而是真正进入判据评估
与停滞检测路径；连续取同一队列任务（`P.RS.RSCOV.04`）且进展指纹不变时，
v2.14 的停滞检测正确触发 `stagnated` 并给出结构化提议，而非烧满预算后失活。
这印证了报告的修正判断：**推广第一道门是账本合规，第二道门才是循环本身**——
两者现已各自验证通过。

> 六、七节复跑均在干净 clone 上完成，未写主仓工作区、未执行任何网关回流命令。
> 复跑 JSON（`/tmp/promote-dryrun-v6.json`）与绑定重算明细为临时取证，不入库。
