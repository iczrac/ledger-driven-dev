"""运行时风险入口：STATE 事件 → 可追溯风险信号 → next_queue 重排。

Slice 1 契约：信号必须从事件原文可复算；无法解析标 unknown 且不进排序；
重排在内存副本进行，不修改传入的 queue / model。本测试先锁契约。
"""
from __future__ import annotations

MODULE_ID = "core"
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import _base  # noqa: F401 — 触发 scripts/ 路径注入（与其他 core 测试一致）

from build_capability_model import (build_next_queue,  # noqa: E402
                                    paused_project_codes)
from runtime_signals import (  # noqa: E402
    apply_risk_signals,
    apply_risk_signals_exact,
    capability_hits,
    domain_hint,
    parse_state_events,
    project_signals,
    risk_score,
)


def _event(md: str, name: str = "2026-11-20.md") -> Path:
    td = tempfile.mkdtemp()
    p = Path(td) / name
    p.write_text(md, encoding="utf-8")
    return Path(td)


class ParseStateEventsTest(unittest.TestCase):
    def test_parses_e_block_fields(self):
        d = _event("""# P 事件日志

## E4 · 标题

- time: 2026-11-20T09:00+08:00
- boundary: read-only
- finding: (fact) 单调上升。
- confidence: fact
- action: none — 维持 P1

## Boundaries

L1 only.
""")
        signals = parse_state_events(d)
        self.assertEqual(len(signals), 1)
        s = signals[0]
        self.assertEqual(s["id"], "E4")
        self.assertEqual(s["confidence"], "fact")
        self.assertIn("单调上升", s["finding"])
        self.assertTrue(s["action"].startswith("none"))
        self.assertEqual(s["source_file"], "2026-11-20.md")

    def test_missing_confidence_is_unknown(self):
        d = _event("""## E1 · x

- finding: something
- action: none
""")
        s = parse_state_events(d)[0]
        self.assertEqual(s["confidence"], "unknown")
        self.assertEqual(risk_score(s), 0.0)

    def test_inference_is_scored_lower_than_fact(self):
        base = "- finding: (fact) 27.3% → 31.7% → 32.24% 单调上升。- action: none"
        fact = parse_state_events(_event("## E1\n- confidence: fact\n" + base))[0]
        infer = parse_state_events(_event("## E2\n- confidence: inference\n" + base))[0]
        self.assertGreater(risk_score(fact), risk_score(infer))

    def test_ignores_boundaries_section(self):
        d = _event("## E1 · x\n- confidence: fact\n- action: none\n\n## Boundaries\n\nnot a signal\n")
        self.assertEqual([s["id"] for s in parse_state_events(d)], ["E1"])


class RiskAndRankTest(unittest.TestCase):
    def setUp(self):
        self.model = {"projects": [{"code": "P", "modules": [{
            "code": "DATA", "caps": [
                {"code": "P.DATA.COV.04", "level_code": "L3", "completion": 0.6},
                {"code": "P.DATA.ADJ.03", "level_code": "L3", "completion": 0.6},
            ]}, {"code": "RS", "caps": [
                {"code": "P.RS.COV.04", "level_code": "L2", "completion": 0.4},
            ]}]}]}
        self.queue = [
            {"code": "P.RS.COV.04", "completion": 0.4, "rank": 1},
            {"code": "P.DATA.COV.04", "completion": 0.6, "rank": 2},
            {"code": "P.DATA.ADJ.03", "completion": 0.6, "rank": 3},
        ]

    def test_domain_hint_from_momentum_seam(self):
        s = {"finding": "(fact) HK momentum seam 单调上升，canonical read 固定来源", "evidence": "momentum contamination"}
        self.assertEqual(domain_hint(s), "DATA")

    def test_no_signal_preserves_order(self):
        out = apply_risk_signals(self.queue, [], self.model)
        self.assertEqual([t["code"] for t in out], [t["code"] for t in self.queue])
        self.assertEqual(self.queue[0]["rank"], 1)

    def test_seam_signal_promotes_data_domain_to_rank1(self):
        d = _event("""## E4 · seam

- time: 2026-11-20T09:00+08:00
- finding: (fact) momentum seam 27.3% → 31.7% → 32.24% 单调上升；canonical read 固定来源
- confidence: fact
- action: none — 维持 P1
""")
        signals = parse_state_events(d)
        out = apply_risk_signals(self.queue, signals, self.model)
        # 同域内仍按 completion/code 稳定排序，故 DATA 域两者皆可居首；
        # 关键契约是「带风险的 DATA 域整体压过无风险的 RS 域」。
        self.assertEqual(out[0]["code"].split(".")[1], "DATA")
        self.assertEqual(out[0]["rank"], 1)
        self.assertGreater(out[0]["risk_score"], 0)
        self.assertEqual(out[0]["risk_signal"], "E4")
        self.assertEqual(out[1]["code"].split(".")[1], "DATA")
        self.assertEqual(self.queue[0]["code"], "P.RS.COV.04")

    def test_unknown_signal_does_not_change_order(self):
        d = _event("## E1 · x\n- finding: momentum seam 单调上升\n- action: none\n")
        signals = parse_state_events(d)
        out = apply_risk_signals(self.queue, signals, self.model)
        self.assertEqual([t["code"] for t in out], [t["code"] for t in self.queue])

    def test_signal_without_domain_match_does_not_change_order(self):
        d = _event("## E5 · x\n- finding: 磁盘 92.2%\n- confidence: fact\n- action: alert-operator\n")
        signals = parse_state_events(d)
        out = apply_risk_signals(self.queue, signals, self.model)
        self.assertEqual([t["code"] for t in out], [t["code"] for t in self.queue])


class ExactMappingTest(unittest.TestCase):
    def setUp(self):
        self.model = {"projects": [{"code": "P", "modules": [{
            "code": "DATA", "caps": [
                {"code": "P.DATA.PROVIDER.05", "name": "Provider gate"},
                {"code": "P.DATA.ADJUSTED.03", "name": "Adjusted price"},
                {"code": "P.DATA.COVERAGE.04", "name": "Coverage audit"},
            ]}, {"code": "RS", "caps": [
                {"code": "P.RS.RSCOV.04", "name": "RS coverage"},
            ]}]}]}
        self.queue = [
            {"code": "P.RS.RSCOV.04", "completion": 0.4, "rank": 1},
            {"code": "P.DATA.PROVIDER.05", "completion": 0.6, "rank": 2},
            {"code": "P.DATA.ADJUSTED.03", "completion": 0.6, "rank": 3},
            {"code": "P.DATA.COVERAGE.04", "completion": 0.6, "rank": 4},
        ]

    def test_operator_action_is_not_projected_into_queue(self):
        # operator 裁决项（重启服务/修数据/改告警规则）不是 L1 可补证据的能力点，
        # 投影它只会造出「补个记录就关警报」的假绿灯。E1/E3 即属此类。
        s = {"id": "E1", "confidence": "fact",
             "finding": "RSUniverseCoverage audit failed for US, coverage audit",
             "action": "alert-operator — 修法要 operator 裁决"}
        self.assertEqual(capability_hits(s, self.model), ["P.DATA.COVERAGE.04"])
        self.assertEqual(project_signals([s], self.model), [])

    def test_bare_coverage_filename_does_not_map_to_coverage_capability(self):
        # 裸 coverage / frontier 词（来自文件名 rs_universe_coverage.py）不该命中
        # 覆盖审计能力点；只有明确的 "coverage audit" 审计语境才命中。
        s = {"confidence": "fact", "finding": "rs_universe_coverage.py frontier collapsed"}
        self.assertEqual(capability_hits(s, self.model), [])

    def test_explicit_capability_field_wins(self):
        s = {"finding": "canonical read 单调上升", "confidence": "fact",
             "capability": "P.DATA.ADJUSTED.03"}
        self.assertEqual(capability_hits(s, self.model), ["P.DATA.ADJUSTED.03"])

    def test_semantic_alias_maps_canonical_read_to_provider(self):
        s = {"finding": "(fact) canonical read 固定來源；momentum seam 单调上升",
             "evidence": "source select per symbol", "confidence": "fact"}
        # canonical read(14) 比 momentum seam(13) 更长，命中 PROVIDER 而非把全 DATA 域抬高。
        self.assertEqual(capability_hits(s, self.model), ["P.DATA.PROVIDER.05"])

    def test_unknown_capability_field_is_ignored(self):
        s = {"finding": "momentum seam", "confidence": "fact",
             "capability": "P.DATA.NOTREAL.99"}
        self.assertEqual(capability_hits(s, self.model), ["P.RS.RSCOV.04"])

    def test_ambiguous_equal_length_aliases_fail_closed(self):
        s = {"finding": "provider adjusted 单调上升", "confidence": "fact"}
        self.assertEqual(capability_hits(s, self.model), [])

    def test_project_signals_is_serializable_and_fail_closed(self):
        signals = [
            {"id": "E4", "source_file": "2026-11-20.md", "confidence": "fact",
             "finding": "canonical read source select 单调上升", "action": "none"},
            {"id": "E5", "confidence": "fact", "finding": "磁盘 92%"},
            {"id": "E6", "confidence": "unknown", "finding": "canonical read"},
            "not-a-dict",
        ]
        entries = project_signals(signals, self.model)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["capabilities"], ["P.DATA.PROVIDER.05"])
        self.assertEqual(entries[0]["risk_score"], 1.0)
        self.assertEqual(json.loads(json.dumps(entries, ensure_ascii=False)), entries)

    def test_exact_queue_only_promotes_mapped_capability(self):
        signals = [{"id": "E4", "source_file": "2026-11-20.md",
                    "confidence": "fact", "finding": "canonical read source select 单调上升",
                    "action": "none"}]
        out = apply_risk_signals_exact(self.queue, signals, self.model)
        self.assertEqual(out[0]["code"], "P.DATA.PROVIDER.05")
        self.assertEqual(out[0]["risk_signal"], "E4")
        self.assertEqual(out[0]["risk_evidence"], "2026-11-20.md#E4")
        self.assertEqual(out[1]["code"], "P.RS.RSCOV.04")
        self.assertEqual(out[1]["risk_score"], 0.0)
        self.assertEqual([t["code"] for t in self.queue][0], "P.RS.RSCOV.04")
        self.assertEqual(self.queue[1]["rank"], 2)

    def test_projected_entry_can_be_reapplied_without_rescoring(self):
        signals = [{"id": "E4", "confidence": "inference",
                    "finding": "canonical read source select 单调上升"}]
        entries = project_signals(signals, self.model)
        again = project_signals(entries, self.model)
        self.assertEqual(again, entries)
        out = apply_risk_signals_exact(self.queue, entries, self.model)
        self.assertEqual(out[0]["risk_score"], entries[0]["risk_score"])


class SignalDecayTest(unittest.TestCase):
    def setUp(self):
        self.model = {"projects": [{"code": "P", "modules": [{
            "code": "DATA", "caps": [
                {"code": "P.DATA.PROVIDER.05", "name": "Provider gate"}]}]}]}
        self.as_of = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
        self.signal = {
            "id": "E4", "source_file": "2026-11-20.md", "confidence": "fact",
            "finding": "canonical read source select 单调上升", "action": "none",
            "time": "2026-11-20T09:00+08:00",
        }

    def test_age_uses_explicit_as_of_not_system_clock(self):
        from runtime_signals import signal_age_days
        self.assertEqual(signal_age_days(self.signal, self.as_of), 1)

    def test_signal_without_time_is_dropped_when_enforced(self):
        s = dict(self.signal)
        s.pop("time")
        self.assertEqual(project_signals([s], self.model, as_of=self.as_of), [])

    def test_expired_signal_is_dropped(self):
        s = dict(self.signal)
        s["time"] = "2026-11-10T09:00+08:00"
        self.assertEqual(project_signals([s], self.model, as_of=self.as_of), [])

    def test_risk_score_decays_and_projection_is_explainable(self):
        fresh = dict(self.signal)
        fresh["time"] = "2026-11-21T11:00+08:00"
        fresh_entries = project_signals([fresh], self.model, as_of=self.as_of)
        aged_entries = project_signals([self.signal], self.model, as_of=self.as_of)
        self.assertEqual(fresh_entries[0]["risk_score"], 1.0)
        self.assertLess(aged_entries[0]["risk_score"], fresh_entries[0]["risk_score"])
        self.assertEqual(aged_entries[0]["age_days"], 1)
        self.assertEqual(aged_entries[0]["decay_factor"], 0.8571)
        self.assertEqual(aged_entries[0]["observed_at"], self.signal["time"])

    def test_same_as_of_is_deterministic(self):
        a = project_signals([self.signal], self.model, as_of=self.as_of)
        b = project_signals([self.signal], self.model, as_of=self.as_of)
        self.assertEqual(a, b)
        self.assertEqual(json.loads(json.dumps(a, ensure_ascii=False)), a)

    def test_without_as_of_keeps_legacy_shape(self):
        entries = project_signals([self.signal], self.model)
        self.assertEqual(len(entries), 1)
        self.assertNotIn("age_days", entries[0])
        self.assertEqual(entries[0]["risk_score"], 1.0)


class RiskOutcomeTest(unittest.TestCase):
    """Slice 4 风险下降判据：衰减 ≠ 风险下降（docs/36）。"""

    def setUp(self):
        self.as_of = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)

    def _sig(self, finding="", evidence="", time="2026-11-20T09:00+08:00"):
        return {"id": "E4", "source_file": "2026-11-20.md", "confidence": "fact",
                "finding": finding, "evidence": evidence, "action": "none",
                "time": time}

    def test_extracts_same_unit_arrow_sequence_with_threshold(self):
        from runtime_signals import extract_metric_trend
        s = self._sig(finding="HK 27.3% → 11-16 31.7% → 11-19 31.9% → 今天 32.24%，"
                      "單調上升；critical_ratio` 0.20")
        t = extract_metric_trend(s)
        self.assertEqual(t["values"], [27.3, 31.7, 31.9, 32.24])
        self.assertEqual(t["direction"], "rising")
        self.assertEqual(t["threshold"], 0.2)
        self.assertEqual(t["source_field"], "finding")

    def test_mixed_direction_is_reported_honestly(self):
        from runtime_signals import extract_metric_trend
        s = self._sig(evidence="80%(11-19) → 90%(11-19) → 100%(11-20) → 93% → 92%")
        t = extract_metric_trend(s)
        self.assertEqual(t["direction"], "mixed")
        self.assertEqual(t["latest"], 92.0)

    def test_heterogeneous_chain_with_pct_in_parens_is_rejected(self):
        from runtime_signals import extract_metric_trend
        # E7 形态：symbol 计数链里混入 ALEC.US 1.9% —— 异口径，必须 fail-closed
        s = self._sig(evidence="4 個 symbol → 1 個（ALEC.US 1.9%，range 8.8%）→ residual 3 個")
        self.assertIsNone(extract_metric_trend(s))

    def test_single_point_and_no_arrow_are_rejected(self):
        from runtime_signals import extract_metric_trend
        self.assertIsNone(extract_metric_trend(self._sig(finding="seam 32.24%")))
        self.assertIsNone(extract_metric_trend(self._sig(finding="覆蓋 3 個檔案")))

    def test_divergent_warning_when_score_decays_but_metric_worsens(self):
        from runtime_signals import risk_outcome
        s = self._sig(finding="seam 27.3% → 31.7% → 31.9% → 32.24%，單調上升")
        row = risk_outcome([s], self.as_of)[0]
        self.assertEqual(row["decay_vs_metric"], "divergent")
        self.assertTrue(row["score_decayed"])
        self.assertEqual(row["metric_trend"]["direction"], "rising")
        # 观察器绝不下"风险已下降"结论
        self.assertEqual(row["outcome"], "observed_only")

    def test_aligned_when_metric_improves(self):
        from runtime_signals import risk_outcome
        s = self._sig(finding="residual 32.24% → 20.65% → 8.14% → 1.02%，收斂")
        row = risk_outcome([s], self.as_of)[0]
        self.assertEqual(row["decay_vs_metric"], "aligned")

    def test_no_as_of_yields_no_outcome(self):
        from runtime_signals import risk_outcome
        s = self._sig(finding="seam 27.3% → 32.24%")
        self.assertEqual(risk_outcome([s]), [])

    def test_observation_is_read_only_on_input(self):
        from runtime_signals import risk_outcome
        s = self._sig(finding="seam 27.3% → 32.24%")
        before = json.dumps(s, ensure_ascii=False)
        risk_outcome([s], self.as_of)
        self.assertEqual(json.dumps(s, ensure_ascii=False), before)


class RiskDispositionTest(unittest.TestCase):
    """Slice 5 关闭回路：关闭须账本显式裁决，引用≠关闭（docs/36）。"""

    def setUp(self):
        self.as_of = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
        self.sig = {"id": "E4", "source_file": "2026-11-20.md",
                    "finding": "seam 27.3% → 32.24%", "confidence": "fact"}
        self.ref = "projects/sample/state/events/2026-11-20.md#E4"

    def test_decision_referencing_signal_but_not_closing_is_open(self):
        from runtime_signals import signal_disposition
        # D-023 形态：引用 E4 但明写"不关警报" → 必须判 open（防假绿灯）
        dec = [{"id": "D-023", "status": "done",
                "decision": "补齐证据，不修数据、不关警报",
                "evidence": [self.ref]}]
        self.assertEqual(signal_disposition(self.sig, dec)["status"], "open")

    def test_proposed_close_decision_is_open(self):
        from runtime_signals import signal_disposition
        dec = [{"id": "D-T", "status": "proposed", "decision": "关闭风险 E4",
                "evidence": [self.ref]}]
        self.assertEqual(signal_disposition(self.sig, dec)["status"], "open")

    def test_explicit_done_close_decision_is_adjudicated(self):
        from runtime_signals import signal_disposition
        dec = [{"id": "D-T", "status": "done", "title": "关闭风险 E4",
                "decision": "固定 canonical source 后接受残余风险并关闭",
                "evidence": [self.ref]}]
        r = signal_disposition(self.sig, dec)
        self.assertEqual(r["status"], "adjudicated_closed")
        self.assertEqual(r["decision_id"], "D-T")
        self.assertIn("关闭", r["marker"])

    def test_done_without_close_marker_is_open(self):
        from runtime_signals import signal_disposition
        dec = [{"id": "D-T", "status": "done", "decision": "补齐证据",
                "evidence": [self.ref]}]
        self.assertEqual(signal_disposition(self.sig, dec)["status"], "open")

    def test_wrong_source_or_signal_ref_is_open(self):
        from runtime_signals import signal_disposition
        dec = [{"id": "D-T", "status": "done", "decision": "关闭风险",
                "evidence": ["projects/sample/state/events/2026-11-19.md#E4"]}]
        self.assertEqual(signal_disposition(self.sig, dec)["status"], "open")
        dec[0]["evidence"] = ["projects/sample/state/events/2026-11-20.md#E9"]
        self.assertEqual(signal_disposition(self.sig, dec)["status"], "open")

    def test_no_decisions_yields_open(self):
        from runtime_signals import signal_disposition
        self.assertEqual(signal_disposition(self.sig)["status"], "open")
        self.assertEqual(signal_disposition(self.sig, [])["status"], "open")

    def test_risk_outcome_attaches_disposition_when_decisions_passed(self):
        from runtime_signals import risk_outcome
        dec = [{"id": "D-T", "status": "done", "title": "关闭风险 E4",
                "evidence": [self.ref]}]
        row = risk_outcome([self.sig], self.as_of, dec)[0]
        self.assertEqual(row["disposition"]["status"], "adjudicated_closed")
        self.assertNotIn("disposition", risk_outcome([self.sig], self.as_of)[0])


class GeneratorIntegrationTest(unittest.TestCase):
    def setUp(self):
        def cap(code, level, completion):
            return {"code": code, "name": code, "level": level,
                    "level_code": f"L{level}", "next_level": level + 1,
                    "completion": completion, "next_action": "补证据",
                    "doc_index": {}, "evidence": {}}
        self.model = {"projects": [{"code": "P", "modules": [{
            "code": "DATA", "caps": [
                cap("P.DATA.PROVIDER.05", 3, 0.6),
                cap("P.DATA.ADJUSTED.03", 3, 0.6),
                cap("P.RS.RSCOV.04", 2, 0.4),
            ]}]}]}

    def test_no_signals_preserves_generator_shape(self):
        queue = build_next_queue(self.model)
        self.assertEqual(queue[0]["code"], "P.RS.RSCOV.04")
        self.assertNotIn("risk_score", queue[0])

    def test_projected_signals_reorder_exact_capability(self):
        entries = [{"id": "E4", "source_file": "x.md", "confidence": "fact",
                    "domain": "DATA", "risk_score": 1.0,
                    "capabilities": ["P.DATA.PROVIDER.05"]}]
        queue = build_next_queue(self.model, runtime_signals=entries)
        self.assertEqual(queue[0]["code"], "P.DATA.PROVIDER.05")
        self.assertEqual(queue[0]["risk_signal"], "E4")
        self.assertEqual(queue[0]["risk_evidence"], "x.md#E4")
        self.assertEqual(queue[1]["code"], "P.RS.RSCOV.04")
        self.assertNotIn("risk_score", queue[1])

    def test_structured_pause_excludes_project_from_queue(self):
        """人工裁决的暂停必须结构化；队列不得继续给暂停范围派活。"""
        ledger = {"entries": [{
            "id": "D-X", "status": "done",
            "decision": "HELM 暂停，不补测试刷分",
            "paused_scopes": ["P"],
        }]}
        self.assertEqual(paused_project_codes(ledger), {"P"})
        self.assertEqual(build_next_queue(
            self.model, paused_projects=paused_project_codes(ledger)), [])

    def test_free_text_pause_does_not_silently_change_queue(self):
        """没有结构化字段时不得从散文猜暂停：猜错比不猜更危险。"""
        ledger = {"entries": [{
            "id": "D-X", "status": "done", "decision": "P 暂停，不补测试刷分",
        }]}
        self.assertEqual(paused_project_codes(ledger), set())
        self.assertEqual([t["code"] for t in build_next_queue(
            self.model, paused_projects=paused_project_codes(ledger))],
            ["P.RS.RSCOV.04", "P.DATA.ADJUSTED.03", "P.DATA.PROVIDER.05"])

    def test_superseded_or_proposed_pause_is_ignored(self):
        """只有生效且未被取代的裁决能暂停队列。"""
        ledger = {"entries": [
            {"id": "D-1", "status": "proposed", "paused_scopes": ["P"]},
            {"id": "D-2", "status": "done", "superseded_by": "D-3",
             "paused_scopes": ["P"]},
        ]}
        self.assertEqual(paused_project_codes(ledger), set())

    def test_malformed_entry_is_ignored(self):
        entries = [{"id": "bad", "risk_score": "n/a",
                    "capabilities": ["P.DATA.PROVIDER.05"]}, "raw"]
        queue = build_next_queue(self.model, runtime_signals=entries)
        self.assertEqual(queue[0]["code"], "P.RS.RSCOV.04")
        self.assertNotIn("risk_score", queue[0])


if __name__ == "__main__":
    unittest.main()
