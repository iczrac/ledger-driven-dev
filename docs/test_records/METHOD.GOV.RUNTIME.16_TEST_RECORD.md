# 运行时风险入口（v2.15.0）：STATE 事件 → 精确能力点映射 → next_queue 只读重排 测试记录

- schema: ledger-test-record/1
- cap_code: METHOD.GOV.RUNTIME.16
- cap_name: 运行时风险入口（v2.15.0）：STATE 事件 → 精确能力点映射 → next_queue 只读重排
- source_report: governance/test_report.json
- source_sha256: 33fba98654659756a6901ca8ff488bd10d96c7453636faf9f25c40e117f88187
- report_generated_at: 2026-11-27 11:43 HKT
- generated_at: 2026-11-27T11:43:00+08:00
- time_basis: evidence_report
- 覆盖: ["tests/core/test_runtime_signals.py"]
- 声明未覆盖: []
- 结果: 45 passed
- cases: ["_lld_test_runtime_signals_22064.ExactMappingTest.test_ambiguous_equal_length_aliases_fail_closed", "_lld_test_runtime_signals_22064.ExactMappingTest.test_bare_coverage_filename_does_not_map_to_coverage_capability", "_lld_test_runtime_signals_22064.ExactMappingTest.test_exact_queue_only_promotes_mapped_capability", "_lld_test_runtime_signals_22064.ExactMappingTest.test_explicit_capability_field_wins", "_lld_test_runtime_signals_22064.ExactMappingTest.test_operator_action_is_not_projected_into_queue", "_lld_test_runtime_signals_22064.ExactMappingTest.test_project_signals_is_serializable_and_fail_closed", "_lld_test_runtime_signals_22064.ExactMappingTest.test_projected_entry_can_be_reapplied_without_rescoring", "_lld_test_runtime_signals_22064.ExactMappingTest.test_semantic_alias_maps_canonical_read_to_provider", "_lld_test_runtime_signals_22064.ExactMappingTest.test_unknown_capability_field_is_ignored", "_lld_test_runtime_signals_22064.GeneratorIntegrationTest.test_free_text_pause_does_not_silently_change_queue", "_lld_test_runtime_signals_22064.GeneratorIntegrationTest.test_malformed_entry_is_ignored", "_lld_test_runtime_signals_22064.GeneratorIntegrationTest.test_no_signals_preserves_generator_shape", "_lld_test_runtime_signals_22064.GeneratorIntegrationTest.test_projected_signals_reorder_exact_capability", "_lld_test_runtime_signals_22064.GeneratorIntegrationTest.test_structured_pause_excludes_project_from_queue", "_lld_test_runtime_signals_22064.GeneratorIntegrationTest.test_superseded_or_proposed_pause_is_ignored", "_lld_test_runtime_signals_22064.ParseStateEventsTest.test_ignores_boundaries_section", "_lld_test_runtime_signals_22064.ParseStateEventsTest.test_inference_is_scored_lower_than_fact", "_lld_test_runtime_signals_22064.ParseStateEventsTest.test_missing_confidence_is_unknown", "_lld_test_runtime_signals_22064.ParseStateEventsTest.test_parses_e_block_fields", "_lld_test_runtime_signals_22064.RiskAndRankTest.test_domain_hint_from_momentum_seam", "_lld_test_runtime_signals_22064.RiskAndRankTest.test_no_signal_preserves_order", "_lld_test_runtime_signals_22064.RiskAndRankTest.test_seam_signal_promotes_data_domain_to_rank1", "_lld_test_runtime_signals_22064.RiskAndRankTest.test_signal_without_domain_match_does_not_change_order", "_lld_test_runtime_signals_22064.RiskAndRankTest.test_unknown_signal_does_not_change_order", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_decision_referencing_signal_but_not_closing_is_open", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_done_without_close_marker_is_open", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_explicit_done_close_decision_is_adjudicated", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_no_decisions_yields_open", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_proposed_close_decision_is_open", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_risk_outcome_attaches_disposition_when_decisions_passed", "_lld_test_runtime_signals_22064.RiskDispositionTest.test_wrong_source_or_signal_ref_is_open", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_aligned_when_metric_improves", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_divergent_warning_when_score_decays_but_metric_worsens", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_extracts_same_unit_arrow_sequence_with_threshold", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_heterogeneous_chain_with_pct_in_parens_is_rejected", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_mixed_direction_is_reported_honestly", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_no_as_of_yields_no_outcome", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_observation_is_read_only_on_input", "_lld_test_runtime_signals_22064.RiskOutcomeTest.test_single_point_and_no_arrow_are_rejected", "_lld_test_runtime_signals_22064.SignalDecayTest.test_age_uses_explicit_as_of_not_system_clock", "_lld_test_runtime_signals_22064.SignalDecayTest.test_expired_signal_is_dropped", "_lld_test_runtime_signals_22064.SignalDecayTest.test_risk_score_decays_and_projection_is_explainable", "_lld_test_runtime_signals_22064.SignalDecayTest.test_same_as_of_is_deterministic", "_lld_test_runtime_signals_22064.SignalDecayTest.test_signal_without_time_is_dropped_when_enforced", "_lld_test_runtime_signals_22064.SignalDecayTest.test_without_as_of_keeps_legacy_shape"]

## 覆盖明细

| 测试文件 | 用例数 | 通过 | 未通过 |
| --- | --- | --- | --- |
| tests/core/test_runtime_signals.py | 45 | 45 | 0 |

## 复算说明

本文件由 `scripts/gen_test_records.py` 从 `governance/test_report.json` 派生，**不要手改**。

- `source_sha256` 是证据报告的字节摘要，与磁盘上的报告对账即可确认同一份证据；
- `generated_at` 取证据报告的生成时刻（`time_basis: evidence_report`）：派生记录不自带墙钟时间，因此同一份报告重跑生成器得到逐字节相同的结果；
- `cases` 只含该能力声明的测试文件里**状态为 pass** 的真实用例，用例名逐字取自报告；
- 报告更新后重跑生成器即刷新本记录；`--check` 会在记录与证据不一致时 exit 1。

复核命令：

    python3 scripts/gen_test_records.py --check
