# 架构图与数据流（v2.9.0）：账本驱动 SVG + 实时计数 + 可下钻节点 + 分组导航 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.VISUAL.12
- cap_name: 架构图与数据流（v2.9.0）：账本驱动 SVG + 实时计数 + 可下钻节点 + 分组导航
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/views/test_board_views.py"]
- 声明未覆盖: []
- 结果: 8 passed
- cases: ["_lld_test_board_views_41878.BoardViewsTest.test_board_analytics_contract", "_lld_test_board_views_41878.BoardViewsTest.test_board_contract_and_budget_include_new_views", "_lld_test_board_views_41878.BoardViewsTest.test_board_ux_contract", "_lld_test_board_views_41878.BoardViewsTest.test_board_visual_contract", "_lld_test_board_views_41878.BoardViewsTest.test_board_workbench_contract", "_lld_test_board_views_41878.BoardViewsTest.test_local_d3_contract", "_lld_test_board_views_41878.BoardViewsTest.test_template_has_all_work_views_and_anchors", "_lld_test_board_views_41878.BoardViewsTest.test_work_views_degrade_without_data"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/views/test_board_views.py | 8 | 8 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
