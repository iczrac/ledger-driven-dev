# 复述门（v2.4.0 补录）：结构化意图声明 + 机器锚定，路由前置 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.RESTATE.08
- cap_name: 复述门（v2.4.0 补录）：结构化意图声明 + 机器锚定，路由前置
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/routing/test_intent_restate.py"]
- 声明未覆盖: []
- 结果: 11 passed
- cases: ["_lld_test_intent_restate_38941.IntentRestateTest.test_collect_cap_codes_from_all_sources", "_lld_test_intent_restate_38941.IntentRestateTest.test_competing_intents_need_clarification", "_lld_test_intent_restate_38941.IntentRestateTest.test_deterministic", "_lld_test_intent_restate_38941.IntentRestateTest.test_gate_fail_closed_on_missing_inputs", "_lld_test_intent_restate_38941.IntentRestateTest.test_hallucinated_capability_is_rejected", "_lld_test_intent_restate_38941.IntentRestateTest.test_invalid_schema_and_intent", "_lld_test_intent_restate_38941.IntentRestateTest.test_meta_needs_open_questions", "_lld_test_intent_restate_38941.IntentRestateTest.test_readonly_intent_cannot_write", "_lld_test_intent_restate_38941.IntentRestateTest.test_real_project_anchors_real_capability", "_lld_test_intent_restate_38941.IntentRestateTest.test_restate_cannot_copy_raw", "_lld_test_intent_restate_38941.IntentRestateTest.test_schema_and_happy_path"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/routing/test_intent_restate.py | 11 | 11 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
