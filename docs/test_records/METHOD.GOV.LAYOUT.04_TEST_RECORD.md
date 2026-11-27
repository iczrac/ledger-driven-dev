# 文件布局契约 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.LAYOUT.04
- cap_name: 文件布局契约
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/meta/test_layout.py"]
- 声明未覆盖: []
- 结果: 14 passed
- cases: ["_lld_test_layout_59014.LayoutDefinitionTest.test_check_catches_producer_drift", "_lld_test_layout_59014.LayoutDefinitionTest.test_cli_check_and_json", "_lld_test_layout_59014.LayoutDefinitionTest.test_definition_passes_selfcheck", "_lld_test_layout_59014.LayoutDefinitionTest.test_derived_layer_is_never_manual", "_lld_test_layout_59014.LayoutDefinitionTest.test_ledger_fields_are_not_files", "_lld_test_layout_59014.LayoutDefinitionTest.test_no_absolute_paths_in_definition", "_lld_test_layout_59014.LayoutDefinitionTest.test_render_is_deterministic_and_synced", "_lld_test_layout_59014.LayoutDiffTest.test_brownfield_draft_is_detected", "_lld_test_layout_59014.LayoutDiffTest.test_demo_is_governed_and_diff_is_readonly", "_lld_test_layout_59014.LayoutDiffTest.test_empty_project_is_bootstrap", "_lld_test_layout_59014.LayoutDiffTest.test_greenfield_bootstrap_has_eight_files", "_lld_test_layout_59014.LayoutDiffTest.test_ignored_cache_is_not_unexpected", "_lld_test_layout_59014.LayoutDiffTest.test_missing_target_fails_closed", "_lld_test_layout_59014.LayoutDiffTest.test_unexpected_governance_file_is_flagged"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/meta/test_layout.py | 14 | 14 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
