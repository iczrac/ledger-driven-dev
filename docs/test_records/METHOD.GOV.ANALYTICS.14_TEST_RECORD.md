# 可视化分析层（v2.11.0）：热力图 + 趋势 + 证据链 + 健康度多维 + 卡片墙 + What-if 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.ANALYTICS.14
- cap_name: 可视化分析层（v2.11.0）：热力图 + 趋势 + 证据链 + 健康度多维 + 卡片墙 + What-if
- source_report: governance/test_report.json
- source_sha256: f3220cddbeeb6502fcd1026c603b1c6b2fd6ca07ffd6eb6c875a8532fbfe3d48
- report_generated_at: 2026-11-27 13:05 HKT
- generated_at: 2026-11-27T13:05:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/core/test_maturity_analytics.py", "tests/views/test_board_views.py"]
- 声明未覆盖: []
- 结果: 18 passed
- cases: ["_lld_test_maturity_analytics_2265.HealthNaContractTest.test_empty_test_cases_mark_na_and_renormalize", "_lld_test_maturity_analytics_2265.HealthNaContractTest.test_half_up_not_bankers_rounding", "_lld_test_maturity_analytics_2265.HealthNaContractTest.test_opted_out_projection_cases_are_not_counted", "_lld_test_maturity_analytics_2265.HealthNaContractTest.test_real_cases_keep_legacy_formula", "_lld_test_maturity_analytics_2265.HealthNaContractTest.test_t4b_static_contract_python_and_js", "_lld_test_maturity_analytics_2265.HealthNaContractTest.test_zero_capabilities_marks_verified_na", "_lld_test_maturity_analytics_2265.MaturityAnalyticsTest.test_analytics_has_series_change_summary_and_actions", "_lld_test_maturity_analytics_2265.MaturityAnalyticsTest.test_d3_projection_is_tree_shaped_and_traceable", "_lld_test_maturity_analytics_2265.MaturityAnalyticsTest.test_health_dimensions_are_precomputed_and_bounded", "_lld_test_maturity_analytics_2265.MaturityAnalyticsTest.test_next_queue_carries_health_impact", "_lld_test_board_views_40063.BoardViewsTest.test_board_analytics_contract", "_lld_test_board_views_40063.BoardViewsTest.test_board_contract_and_budget_include_new_views", "_lld_test_board_views_40063.BoardViewsTest.test_board_ux_contract", "_lld_test_board_views_40063.BoardViewsTest.test_board_visual_contract", "_lld_test_board_views_40063.BoardViewsTest.test_board_workbench_contract", "_lld_test_board_views_40063.BoardViewsTest.test_local_d3_contract", "_lld_test_board_views_40063.BoardViewsTest.test_template_has_all_work_views_and_anchors", "_lld_test_board_views_40063.BoardViewsTest.test_work_views_degrade_without_data"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/core/test_maturity_analytics.py | 10 | 10 | 0 |
| tests/views/test_board_views.py | 8 | 8 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
