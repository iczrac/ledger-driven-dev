---
name: work-panel
description: |
  节点工作台：在模块/组件/能力点上显示 TODO、issue 与逐用例测试结果。
  Triggers: "工作台", "工作项", "TODO list", "issue", "测试结果", "节点健康度",
  "work panel", "test results", "node work", "sync-tests"
license: MIT
metadata:
  author: iczrac
  version: "1.5.0"
  risk_level: write_with_guard
  related_skills: [ledger-verify, board-layout, scale-budget, agent-gate, test-map]
---

# Work Panel

## When to Use

- 项目负责人想知道「这个模块现在有什么待办、什么缺陷、哪些测试挂了」；
- 需要把 `test_report.json` 的逐用例结果投影到账本，让看板离线可看；
- 需要给 Agent 一份可复算的节点健康度，用于决定先做哪张任务卡。

## 数据契约（都在同一份账本里）

| 字段 | 内容 | 写入者 |
|---|---|---|
| `work_items` | `id / kind(todo\|issue) / scope / status / severity / owner / detail / refs` | `work_panel.py add / close` |
| `test_results` | `test_report.json` 的只读投影：`source_sha256 / summary / cases[]` | `work_panel.py sync-tests` |

派生聚合**不落盘**：`work_panel.py nodes` 与看板 JS 用同一规则按 scope 复算，
所以不会有第三份需要同步的事实。scope 可指向 `PROJECT`、`DEMO`、`DEMO.CORE`
或四段式能力编码 `DEMO.CORE.ORDER.01`，上级作用域向下覆盖。

健康度 = `100 − 阻塞×20 − 未关闭 Issue×8 − 失败用例×15 − 证据非 fresh×15 − 含 declared 能力×10`。

## 步骤

```bash
python3 scripts/work_panel.py --target P check --json          # 只读取证
python3 scripts/work_panel.py --target P nodes --json          # 给 Agent 的节点摘要
python3 scripts/work_panel.py --target P sync-tests --apply \
    --approved-by "审批人姓名" --json                          # 投影测试报告
python3 scripts/work_panel.py --target P add --kind todo \
    --scope DEMO.CORE.ORDER.01 --title "补边界用例" --severity high \
    --refs D-001,path:tests/unit/test_order.py \
    --apply --approved-by "审批人姓名" --json
python3 scripts/work_panel.py --target P close --id W-TODO-001 \
    --apply --approved-by "审批人姓名" --json
cd P && python3 governance/verify_ledger.py --root . --strict   # 24 条不变量
```

所有写动作默认 dry-run；`--apply` 必须 `--approved-by`。写盘走
`ledger_io.write_ledger`，账本与看板 EMBED 一起同步，不允许单独改 HTML。

## 看板视图

- **工作台**：8 个指标（TODO / Issue / 阻塞 / 失败用例 / 待裁决 / 任务卡 / 绑定用例 / 健康度）、
  焦点队列（阻塞优先）、`next_queue` 任务卡、失败用例明细、证据待补能力点；
- **工作项**：全局或按节点钻取，卡片含作用域、严重度、负责人、关联决策与证据路径；
- **节点条**：模块地图 / 架构钻取 / 能力地图的每个模块与能力点都显示
  TODO / Issue / 测试通过数 / 健康度，可展开本节点明细或跳到工作项视图；
- 全部视图按 `PAGE_SIZE` 分批，规模预算新增 `work_items` 阈值。

## 禁止

- 手改 `work_items` / `test_results` 或看板 HTML 里的数值；
- 为了让徽章变绿手填 `source_sha256`（24 条不变量里 `test_results_binding_valid` 会拦）；
- 把 TODO 写进聊天记录、issue 系统或第二份 Markdown 台账；
- 删除 `history.events` 或旧工作项来「减小体积」（append-only 是历史可信前提）。

## 失败处理

| 报错 | 修复 |
|---|---|
| `scope 无法解析` | 用 `nodes --json` 查有效作用域，或先跑生成器 |
| `source_sha256 与当前报告不一致` | 重跑 `run_tests.py` 后 `sync-tests --apply` |
| `summary.total 与 cases 数量不一致` | 不要手改投影，重新同步 |
| 工作台空白 | 项目尚未 M8 初始化：跑 `upgrade.py apply --approved-by <人>` |
| 项目不是标准库测试栈 | 用 `import-report` 把 CI 报告规范化，再 `sync-tests --apply` |

## v1.3.0：导入外部 CI 报告

`test_report.json` 是开放契约，不限定测试框架。非 unittest 栈用：

```
python3 scripts/work_panel.py --target P import-report --from ci/junit.xml \
    --adapter auto --source-dir src,tests --apply --approved-by <人>
```

`--adapter` 支持 `junit`（JUnit XML）、`jest`（jest JSON）、`ledger`
（已符合 `ledger-test-report/1` 的 JSON），`auto` 自动探测。导入会重算
`evidence_binding`（项目根相对路径），空用例报告判 `overall=fail`。
默认 dry-run，写盘必须人工批准。之后照常 `sync-tests --apply` →
生成器 `--strict-evidence`。账本投影不带 `source_adapter`，避免新增事实源。
