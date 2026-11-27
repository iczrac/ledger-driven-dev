# 节点工作台 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.PANEL.03
- cap_name: 节点工作台
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/views/test_work_panel.py"]
- 声明未覆盖: []
- 结果: 16 passed
- cases: ["_lld_test_work_panel_34510.CloseConditionTest.test_close_requires_resolution_when_condition_present", "_lld_test_work_panel_34510.CloseConditionTest.test_declared_capability_allows_open", "_lld_test_work_panel_34510.CloseConditionTest.test_file_exists_uses_project_root", "_lld_test_work_panel_34510.CloseConditionTest.test_manual_never_auto_satisfied", "_lld_test_work_panel_34510.CloseConditionTest.test_unknown_kind_is_rejected", "_lld_test_work_panel_34510.CloseConditionTest.test_verified_capability_blocks_open", "_lld_test_work_panel_34510.ImportReportTest.test_dry_run_and_human_approval", "_lld_test_work_panel_34510.ImportReportTest.test_empty_report_never_green", "_lld_test_work_panel_34510.ImportReportTest.test_three_adapters_autodetect", "_lld_test_work_panel_34510.WorkPanelTest.test_add_and_close_require_approval_and_are_deterministic", "_lld_test_work_panel_34510.WorkPanelTest.test_node_summary_scopes_work_items", "_lld_test_work_panel_34510.WorkPanelTest.test_sync_tests_binding_and_24_invariants", "_lld_test_work_panel_34510.WorkPanelTest.test_sync_tests_respects_opt_out_declaration", "_lld_test_work_panel_34510.WorkPanelTest.test_tampered_projection_fails_verifier", "_lld_test_work_panel_34510.WorkPanelTest.test_validation_rejects_bad_scope_and_refs", "_lld_test_work_panel_34510.WorkPanelTest.test_work_panel_check_on_demo_is_clean"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/views/test_work_panel.py | 16 | 16 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
