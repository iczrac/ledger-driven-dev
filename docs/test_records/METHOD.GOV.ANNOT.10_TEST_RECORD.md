# 来源投影（v2.6.0 补录）：AI推断/人确认分组 + 完成定义派生 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.ANNOT.10
- cap_name: 来源投影（v2.6.0 补录）：AI推断/人确认分组 + 完成定义派生
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/routing/test_provenance_view.py"]
- 声明未覆盖: []
- 结果: 10 passed
- cases: ["_lld_test_provenance_view_61838.CliTest.test_bad_ledger_path", "_lld_test_provenance_view_61838.ProjectionTest.test_decision_provenance_groups", "_lld_test_provenance_view_61838.ProjectionTest.test_definition_of_done_derived", "_lld_test_provenance_view_61838.ProjectionTest.test_deterministic_bytes", "_lld_test_provenance_view_61838.ProjectionTest.test_issue_provenance_groups", "_lld_test_provenance_view_61838.ProjectionTest.test_kind_filter", "_lld_test_provenance_view_61838.ProjectionTest.test_labels_present", "_lld_test_provenance_view_61838.ProjectionTest.test_no_mutation_of_ledger", "_lld_test_provenance_view_61838.ProjectionTest.test_no_new_fields_in_ledger", "_lld_test_provenance_view_61838.ProjectionTest.test_real_ledger_projects"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/routing/test_provenance_view.py | 10 | 10 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
