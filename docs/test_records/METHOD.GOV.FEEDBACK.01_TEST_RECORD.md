# 反向回流观察通道 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.FEEDBACK.01
- cap_name: 反向回流观察通道
- source_report: governance/test_report.json
- source_sha256: 33fba98654659756a6901ca8ff488bd10d96c7453636faf9f25c40e117f88187
- report_generated_at: 2026-11-27 11:43 HKT
- generated_at: 2026-11-27T11:43:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/meta/test_feedback.py"]
- 声明未覆盖: []
- 结果: 13 passed
- cases: ["_lld_test_feedback_28909.AppendOnlyTest.test_existing_row_wins_over_fresh_open_row", "_lld_test_feedback_28909.AppendOnlyTest.test_export_creates_file_when_absent", "_lld_test_feedback_28909.AppendOnlyTest.test_export_preserves_closed_evidence_and_is_idempotent", "_lld_test_feedback_28909.AppendOnlyTest.test_merge_is_idempotent_and_order_stable", "_lld_test_feedback_28909.ClosureTest.test_artifact_ref_must_exist", "_lld_test_feedback_28909.ClosureTest.test_closed_without_disposition_fails_then_passes", "_lld_test_feedback_28909.ClosureTest.test_fingerprint_blocks_manual_edit", "_lld_test_feedback_28909.ClosureTest.test_triage_requires_artifact_for_four_products", "_lld_test_feedback_28909.ClosureTest.test_wontfix_needs_reason_but_no_artifact", "_lld_test_feedback_28909.ExportTest.test_read_only_and_idempotent", "_lld_test_feedback_28909.ExportTest.test_redact_is_data_driven_not_hardcoded", "_lld_test_feedback_28909.ExportTest.test_version_gap_and_legacy_verifier_are_observations", "_lld_test_feedback_28909.ExportTest.test_write_requires_human_approval"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/meta/test_feedback.py | 13 | 13 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
