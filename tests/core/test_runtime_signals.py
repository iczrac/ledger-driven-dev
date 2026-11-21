"""运行时风险入口：STATE 事件 → 可追溯风险信号 → next_queue 重排。

Slice 1 契约：信号必须从事件原文可复算；无法解析标 unknown 且不进排序；
重排在内存副本进行，不修改传入的 queue / model。本测试先锁契约。
"""
from __future__ import annotations

MODULE_ID = "core"
import json
import tempfile
import unittest
from pathlib import Path

import _base  # noqa: F401 — 触发 scripts/ 路径注入（与其他 core 测试一致）

from build_capability_model import build_next_queue  # noqa: E402
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

    def test_malformed_entry_is_ignored(self):
        entries = [{"id": "bad", "risk_score": "n/a",
                    "capabilities": ["P.DATA.PROVIDER.05"]}, "raw"]
        queue = build_next_queue(self.model, runtime_signals=entries)
        self.assertEqual(queue[0]["code"], "P.RS.RSCOV.04")
        self.assertNotIn("risk_score", queue[0])


if __name__ == "__main__":
    unittest.main()
