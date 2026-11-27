# 本地 D3 离线交互层（v2.12.0）：追溯树 + D3 热力图 + 趋势图 + What-if 联动 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.D3.15
- cap_name: 本地 D3 离线交互层（v2.12.0）：追溯树 + D3 热力图 + 趋势图 + What-if 联动
- source_report: governance/test_report.json
- source_sha256: 33fba98654659756a6901ca8ff488bd10d96c7453636faf9f25c40e117f88187
- report_generated_at: 2026-11-27 11:43 HKT
- generated_at: 2026-11-27T11:43:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/core/test_maturity_analytics.py", "tests/views/test_board_views.py", "tests/core/test_verify.py", "tests/meta/test_upgrade.py"]
- 声明未覆盖: []
- 结果: 60 passed
- cases: ["_lld_test_maturity_analytics_17046.HealthNaContractTest.test_empty_test_cases_mark_na_and_renormalize", "_lld_test_maturity_analytics_17046.HealthNaContractTest.test_half_up_not_bankers_rounding", "_lld_test_maturity_analytics_17046.HealthNaContractTest.test_opted_out_projection_cases_are_not_counted", "_lld_test_maturity_analytics_17046.HealthNaContractTest.test_real_cases_keep_legacy_formula", "_lld_test_maturity_analytics_17046.HealthNaContractTest.test_t4b_static_contract_python_and_js", "_lld_test_maturity_analytics_17046.HealthNaContractTest.test_zero_capabilities_marks_verified_na", "_lld_test_maturity_analytics_17046.MaturityAnalyticsTest.test_analytics_has_series_change_summary_and_actions", "_lld_test_maturity_analytics_17046.MaturityAnalyticsTest.test_d3_projection_is_tree_shaped_and_traceable", "_lld_test_maturity_analytics_17046.MaturityAnalyticsTest.test_health_dimensions_are_precomputed_and_bounded", "_lld_test_maturity_analytics_17046.MaturityAnalyticsTest.test_next_queue_carries_health_impact", "_lld_test_board_views_34910.BoardViewsTest.test_board_analytics_contract", "_lld_test_board_views_34910.BoardViewsTest.test_board_contract_and_budget_include_new_views", "_lld_test_board_views_34910.BoardViewsTest.test_board_ux_contract", "_lld_test_board_views_34910.BoardViewsTest.test_board_visual_contract", "_lld_test_board_views_34910.BoardViewsTest.test_board_workbench_contract", "_lld_test_board_views_34910.BoardViewsTest.test_local_d3_contract", "_lld_test_board_views_34910.BoardViewsTest.test_template_has_all_work_views_and_anchors", "_lld_test_board_views_34910.BoardViewsTest.test_work_views_degrade_without_data", "_lld_test_verify_17298.TristateTest.test_missing_projection_is_na_not_pass", "_lld_test_verify_17298.TristateTest.test_strict_ignores_na_but_require_active_does_not", "_lld_test_verify_17298.VerifyTest.test_clean_ledger_passes_all_checks", "_lld_test_verify_17298.VerifyTest.test_detects_broken_history_chain", "_lld_test_verify_17298.VerifyTest.test_detects_forged_analytics_health", "_lld_test_verify_17298.VerifyTest.test_detects_forged_d3_lineage", "_lld_test_verify_17298.VerifyTest.test_detects_forged_na_despite_real_cases", "_lld_test_verify_17298.VerifyTest.test_detects_hand_written_completion", "_lld_test_verify_17298.VerifyTest.test_detects_lesson_without_action", "_lld_test_verify_17298.VerifyTest.test_detects_missing_document", "_lld_test_verify_17298.VerifyTest.test_detects_non_bound_cap_without_derived_issue", "_lld_test_verify_17298.VerifyTest.test_detects_open_item_with_satisfied_close_condition", "_lld_test_verify_17298.VerifyTest.test_detects_satisfied_derived_issue_still_open", "_lld_test_verify_17298.VerifyTest.test_detects_stale_analytics_test_detail", "_lld_test_verify_17298.VerifyTest.test_detects_tampered_event_state", "_lld_test_verify_17298.VerifyTest.test_detects_tampered_installed_asset", "_lld_test_verify_17298.VerifyTest.test_detects_unowned_open_work_item", "_lld_test_verify_17298.VerifyTest.test_detects_verified_with_missing_binding_field", "_lld_test_verify_17298.VerifyTest.test_detects_verified_without_bound_binding", "_lld_test_verify_17298.VerifyTest.test_open_item_with_unmet_condition_still_passes", "_lld_test_verify_17298.VerifyTest.test_opt_out_with_self_consistent_projection_is_fail_not_na", "_lld_test_verify_17298.VerifyTest.test_owner_note_satisfies_ownership_rule", "_lld_test_verify_17298.VerifyTest.test_rejects_stale_zero_when_unprojected", "_lld_test_upgrade_54461.ProjectionPolicyTest.test_codec_copies_agree", "_lld_test_upgrade_54461.ProjectionPolicyTest.test_opted_out_report_does_not_trigger_m8", "_lld_test_upgrade_54461.ProjectionPolicyTest.test_policy_change_preserves_fingerprint_and_history", "_lld_test_upgrade_54461.UpgradeTest.test_apply_is_approved_backed_up_and_verifiable", "_lld_test_upgrade_54461.UpgradeTest.test_apply_is_idempotent", "_lld_test_upgrade_54461.UpgradeTest.test_apply_requires_human_approval", "_lld_test_upgrade_54461.UpgradeTest.test_cli_apply_without_approval_is_rejected", "_lld_test_upgrade_54461.UpgradeTest.test_cli_plan_json_is_deterministic_and_leak_free", "_lld_test_upgrade_54461.UpgradeTest.test_definitions_selfcheck", "_lld_test_upgrade_54461.UpgradeTest.test_plan_detects_tool_drift", "_lld_test_upgrade_54461.UpgradeTest.test_plan_is_read_only_deterministic_and_leak_free", "_lld_test_upgrade_54461.UpgradeTest.test_rollback_restores_state_and_writes_receipt", "_lld_test_upgrade_54461.UpgradeTest.test_two_digit_minor_is_semver_not_string", "_lld_test_upgrade_54461.UpgradeTest.test_unsupported_version_and_frozen_block", "_lld_test_upgrade_54461.UpgradeTest.test_verify_flags_stale_evidence", "_lld_test_upgrade_54461.UpgradeV130Test.test_m8_writes_activation_placeholder_without_report", "_lld_test_upgrade_54461.UpgradeV130Test.test_plan_converges_without_test_report", "_lld_test_upgrade_54461.UpgradeV130Test.test_post_upgrade_report_is_generated_in_target", "_lld_test_upgrade_54461.UpgradeV130Test.test_post_upgrade_steps_are_conditional"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/core/test_maturity_analytics.py | 10 | 10 | 0 |
| tests/views/test_board_views.py | 8 | 8 | 0 |
| tests/core/test_verify.py | 23 | 23 | 0 |
| tests/meta/test_upgrade.py | 19 | 19 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
