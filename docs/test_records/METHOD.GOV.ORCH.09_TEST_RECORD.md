# 专家团编排（v2.5.0 补录）：交接链展开 + 命令分类 + 人工批准包 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.ORCH.09
- cap_name: 专家团编排（v2.5.0 补录）：交接链展开 + 命令分类 + 人工批准包
- source_report: governance/test_report.json
- source_sha256: 2ce13c8eefb45b32dd5254e9927dce3f46271caec9c0e94a1d2e926dbf26a6d1
- report_generated_at: 2026-11-27 01:35 HKT
- generated_at: 2026-11-27T01:35:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/routing/test_expert_run.py"]
- 声明未覆盖: []
- 结果: 16 passed
- cases: ["_lld_test_expert_run_61990.ClassifyCommandTest.test_approval_tokens_win", "_lld_test_expert_run_61990.ClassifyCommandTest.test_dry_run_init_project_is_readonly", "_lld_test_expert_run_61990.ClassifyCommandTest.test_readonly_commands", "_lld_test_expert_run_61990.ClassifyCommandTest.test_unknown_command_is_manual", "_lld_test_expert_run_61990.ClassifyCommandTest.test_write_commands_without_readonly_flag_are_approval", "_lld_test_expert_run_61990.OrchestrateTest.test_approval_bundle_aggregates_write_commands", "_lld_test_expert_run_61990.OrchestrateTest.test_chain_matches_route_handoff", "_lld_test_expert_run_61990.OrchestrateTest.test_deterministic_bytes", "_lld_test_expert_run_61990.OrchestrateTest.test_fail_closed_on_meta_intent", "_lld_test_expert_run_61990.OrchestrateTest.test_hardcoded_placeholder_absent", "_lld_test_expert_run_61990.OrchestrateTest.test_intent_file_only_recorded_as_source", "_lld_test_expert_run_61990.OrchestrateTest.test_no_new_judgement_authority", "_lld_test_expert_run_61990.OrchestrateTest.test_ready_intent_produces_chain", "_lld_test_expert_run_61990.OrchestrateTest.test_target_display_transmitted_to_commands", "_lld_test_expert_run_61990.RenderTest.test_render_halt", "_lld_test_expert_run_61990.RenderTest.test_render_ready"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/routing/test_expert_run.py | 16 | 16 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
