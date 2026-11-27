# 方法资产清单 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.ASSETS.05
- cap_name: 方法资产清单
- source_report: governance/test_report.json
- source_sha256: f3220cddbeeb6502fcd1026c603b1c6b2fd6ca07ffd6eb6c875a8532fbfe3d48
- report_generated_at: 2026-11-27 13:05 HKT
- generated_at: 2026-11-27T13:05:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/meta/test_platform_contract.py"]
- 声明未覆盖: []
- 结果: 21 passed
- cases: ["_lld_test_platform_contract_52685.AssetsTest.test_check_rejects_incomplete_asset_set", "_lld_test_platform_contract_52685.AssetsTest.test_digest_tracks_asset_content", "_lld_test_platform_contract_52685.AssetsTest.test_manifest_is_deterministic_and_grouped", "_lld_test_platform_contract_52685.AssetsTest.test_post_upgrade_covers_all_three_contracts", "_lld_test_platform_contract_52685.AssetsTest.test_upgrade_binds_assets_and_detects_drift", "_lld_test_platform_contract_52685.BoardPathTest.test_canonical_names_of_four_boards", "_lld_test_platform_contract_52685.BoardPathTest.test_cli_returns_single_line_for_shell", "_lld_test_platform_contract_52685.BoardPathTest.test_compatible_policy_falls_back_to_legacy_only_when_new_missing", "_lld_test_platform_contract_52685.BoardPathTest.test_full_path_key_prevents_same_slug_cross_talk", "_lld_test_platform_contract_52685.BoardPathTest.test_legacy_policy_keeps_behavior_unchanged", "_lld_test_platform_contract_52685.BoardTest.test_cli_check_fails_on_drift", "_lld_test_platform_contract_52685.BoardTest.test_demo_board_uses_authoritative_template", "_lld_test_platform_contract_52685.BoardTest.test_digest_ignores_embed_data_but_detects_css", "_lld_test_platform_contract_52685.BoardTest.test_drift_is_part_of_the_upgrade_plan", "_lld_test_platform_contract_52685.BoardTest.test_missing_anchor_is_reported", "_lld_test_platform_contract_52685.BoardTest.test_normalize_defaults_to_dry_run_and_requires_approval", "_lld_test_platform_contract_52685.BoardTest.test_normalize_repairs_css_drift_without_touching_data", "_lld_test_platform_contract_52685.BudgetTest.test_demo_budget_is_clean_and_layout_is_fixed", "_lld_test_platform_contract_52685.BudgetTest.test_probe_shows_file_count_stays_fixed", "_lld_test_platform_contract_52685.BudgetTest.test_render_limit_is_read_from_template", "_lld_test_platform_contract_52685.BudgetTest.test_thresholds_flag_oversized_project"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/meta/test_platform_contract.py | 21 | 21 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
