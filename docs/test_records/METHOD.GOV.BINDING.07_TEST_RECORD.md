# 符号绑定判据（dogfood 负向探针：测试用动态加载，绑定判据应抓不到） 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.BINDING.07
- cap_name: 符号绑定判据（dogfood 负向探针：测试用动态加载，绑定判据应抓不到）
- source_report: governance/test_report.json
- source_sha256: 33fba98654659756a6901ca8ff488bd10d96c7453636faf9f25c40e117f88187
- report_generated_at: 2026-11-27 11:43 HKT
- generated_at: 2026-11-27T11:43:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/core/test_binding_advisory.py"]
- 声明未覆盖: []
- 结果: 5 passed
- cases: ["_lld_test_binding_advisory_13416.BindingAdvisoryTest.test_direct_import_is_bound", "_lld_test_binding_advisory_13416.BindingAdvisoryTest.test_missing_impl_and_missing_tests_are_classified", "_lld_test_binding_advisory_13416.BindingAdvisoryTest.test_reexport_chain_is_bound", "_lld_test_binding_advisory_13416.BindingAdvisoryTest.test_unrelated_test_is_unbound_and_tier_untouched", "_lld_test_binding_advisory_13416.BindingAdvisoryTest.test_via_one_hop_is_reported_with_bridge"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/core/test_binding_advisory.py | 5 | 5 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
