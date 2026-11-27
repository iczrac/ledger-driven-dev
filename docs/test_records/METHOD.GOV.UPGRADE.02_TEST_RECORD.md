# 升级与迁移引擎 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.UPGRADE.02
- cap_name: 升级与迁移引擎
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/meta/test_upgrade.py"]
- 声明未覆盖: []
- 结果: 19 passed
- cases: ["_lld_test_upgrade_44338.ProjectionPolicyTest.test_codec_copies_agree", "_lld_test_upgrade_44338.ProjectionPolicyTest.test_opted_out_report_does_not_trigger_m8", "_lld_test_upgrade_44338.ProjectionPolicyTest.test_policy_change_preserves_fingerprint_and_history", "_lld_test_upgrade_44338.UpgradeTest.test_apply_is_approved_backed_up_and_verifiable", "_lld_test_upgrade_44338.UpgradeTest.test_apply_is_idempotent", "_lld_test_upgrade_44338.UpgradeTest.test_apply_requires_human_approval", "_lld_test_upgrade_44338.UpgradeTest.test_cli_apply_without_approval_is_rejected", "_lld_test_upgrade_44338.UpgradeTest.test_cli_plan_json_is_deterministic_and_leak_free", "_lld_test_upgrade_44338.UpgradeTest.test_definitions_selfcheck", "_lld_test_upgrade_44338.UpgradeTest.test_plan_detects_tool_drift", "_lld_test_upgrade_44338.UpgradeTest.test_plan_is_read_only_deterministic_and_leak_free", "_lld_test_upgrade_44338.UpgradeTest.test_rollback_restores_state_and_writes_receipt", "_lld_test_upgrade_44338.UpgradeTest.test_two_digit_minor_is_semver_not_string", "_lld_test_upgrade_44338.UpgradeTest.test_unsupported_version_and_frozen_block", "_lld_test_upgrade_44338.UpgradeTest.test_verify_flags_stale_evidence", "_lld_test_upgrade_44338.UpgradeV130Test.test_m8_writes_activation_placeholder_without_report", "_lld_test_upgrade_44338.UpgradeV130Test.test_plan_converges_without_test_report", "_lld_test_upgrade_44338.UpgradeV130Test.test_post_upgrade_report_is_generated_in_target", "_lld_test_upgrade_44338.UpgradeV130Test.test_post_upgrade_steps_are_conditional"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/meta/test_upgrade.py | 19 | 19 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
