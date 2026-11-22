"""运行时风险入口：把 STATE 事件日志投影成可追溯的风险信号，并在内存副本中
按风险重排 next_queue。Slice 1 = 域级重排；Slice 2 = 精确能力点映射 + 生成器接入；
Slice 3 = 显式 as_of 下的时间衰减与过期。

设计纪律（不可协商）：
  - 只读：解析事件、投影信号、重排副本；绝不写盘、绝不改账本或队列入参。
  - 可复算：每个信号带 source_file / id，字段来自事件原文，不推断不补全。
  - fail-closed：缺 confidence / 无法判域 / 能力点映射歧义 → 不进精确排序。
  - 向后兼容：Slice 1 的 apply_risk_signals 行为不变；精确入口独立提供。
  - 不造第二事实源：project_signals 只产出可序列化的投影，供生成器显式消费。
  - 时间显式：只有调用方传入 as_of 才启用衰减；无 time 或过期信号 fail-closed。
    隐式读系统时钟会让同一批事件在不同日期产出不同账本，破坏可复算性。

本模块不依赖任何第三方库；不 import build_capability_model，避免副本漂移。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

# 域关键词：只在本表内的词才参与域判定，表外一律 unknown（fail-closed）。
# 顺序即优先级：命中多个时取表中靠前者，保证可复算。
DOMAIN_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("DATA", ("momentum", "seam", "canonical read", "adjusted", "universe",
              "coverage", "freshness", "provider", "ingest", "frontier")),
    ("RS", ("relative strength", "rs core", "sector strength")),
    ("RESEARCH", ("factor", "candidate", "pattern", "catalyst")),
    ("RISK", ("exposure", "risk plane", "barra", "concentration")),
    ("PORTFOLIO", ("portfolio", "optimizer", "allocation")),
    ("EXECUTION", ("broker", "order", "pretrade", "execution")),
    ("GOV", ("registry", "promotion", "rollback", "validation")),
)

_E_HEADING = re.compile(r"^##\s+(E\d+)\b[·\s]*(.*)$")
_FIELD = re.compile(r"^-\s+([a-z_]+):\s*(.*)$")
_TREND = re.compile(r"\d+(?:\.\d+)?\s*%?\s*(?:→|->|至)\s*\d+(?:\.\d+)?")
_NONE_ACTION = re.compile(r"\bnone\b", re.IGNORECASE)
_OPERATOR_ACTION = re.compile(r"alert-operator|operator", re.IGNORECASE)
_CAP_CODE = re.compile(r"[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.[A-Z][A-Z0-9]*\.\d{2}")

# Slice 3：事件超过该天数不再进入风险排序（线性衰减到 0 后即过期）。
DEFAULT_MAX_AGE_DAYS = 7

# Slice 2 精确映射：把事件原文里的语义锚点映射到能力码第三段（cap token）。
# 规则是投影层的可审计词表，不是事实源；命中歧义时按“更长关键词优先”，
# 同长多 token 命中则判歧义并 fail-closed。表外文本不会被硬塞进任何能力点。
CAPABILITY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("PROVIDER", ("canonical read", "source select", "fixed source",
                  "固定來源", "固定来源", "upstream source", "provider")),
    ("ADJUSTED", ("price basis", "close_adj", "adjusted", "复权", "復權")),
    # 裸「覆蓋/覆盖」太泛（例如「只覆蓋 3 個檔案」会误伤），只保留审计语境。
    # 移除裸 coverage / frontier：文件名（rs_universe_coverage.py）与 frontier
    # 快照词会让运行时事件被误挂到本能力点；只保留覆盖审计的明确语境。
    ("COVERAGE", ("coverage audit", "覆盖审计", "覆蓋審計", "gap fill")),
    ("RSCOV", ("momentum seam", "contamination", "污染", "rs coverage")),
    ("CORE", ("rs core", "core calc", "分母口径")),
    ("SECTOR", ("sector", "行业强度", "行業強度")),
)


def parse_state_events(state_dir: str | Path) -> list[dict]:
    """解析目录下 *.md 的 `## E<n>` 块。返回信号列表，顺序＝文件排序×块序。"""
    root = Path(state_dir)
    signals: list[dict] = []
    for path in sorted(root.glob("*.md")):
        current: dict | None = None
        last_field: str | None = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            m = _E_HEADING.match(raw)
            if m:
                if current is not None:
                    signals.append(current)
                current = {
                    "id": m.group(1),
                    "title": m.group(2).strip(),
                    "source_file": path.name,
                    "confidence": "unknown",
                }
                last_field = None
                continue
            if raw.startswith("## "):
                if current is not None:
                    signals.append(current)
                    current = None
                last_field = None
                continue
            if current is None:
                continue
            fm = _FIELD.match(raw)
            if fm:
                last_field = fm.group(1)
                current[last_field] = fm.group(2).strip()
            elif raw.startswith("    ") and last_field:
                current[last_field] += " " + raw.strip()
        if current is not None:
            signals.append(current)
    for s in signals:
        s.setdefault("finding", "")
        s.setdefault("action", "")
        s.setdefault("evidence", "")
        if s.get("confidence") not in ("fact", "inference", "unknown"):
            s["confidence"] = "unknown"
    return signals


def signal_age_days(signal: dict, as_of: datetime | None = None) -> int | None:
    """事件年龄（整天）；time 缺失或不可解析返回 None（fail-closed）。

    as_of 由调用方显式提供；不传时按当前 UTC 计算，仅供一次性诊断，
    不应作为可复算投影的基准。
    """
    raw = signal.get("time")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        observed = datetime.fromisoformat(raw.strip())
    except ValueError:
        return None
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    ref = as_of or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return max(0, (ref - observed).days)


def decay_factor(age_days: int | None,
                 max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> float | None:
    """线性衰减系数；年龄不可判定返回 None，达到上限返回 0（过期）。"""
    if age_days is None or max_age_days <= 0:
        return None
    if age_days >= max_age_days:
        return 0.0
    return round(1.0 - age_days / max_age_days, 4)


def domain_hint(signal: dict) -> str:
    """从 finding + evidence 文本判域；无命中返回空串（不进排序）。"""
    text = f"{signal.get('finding', '')} {signal.get('evidence', '')}".lower()
    for domain, keywords in DOMAIN_KEYWORDS:
        if any(kw in text for kw in keywords):
            return domain
    return ""


def risk_score(signal: dict) -> float:
    """风险分：fact 才高分，inference 折半，unknown 为零；单调上升/none 加权。"""
    conf = signal.get("confidence")
    if conf == "unknown":
        return 0.0
    text = f"{signal.get('finding', '')} {signal.get('evidence', '')}"
    score = 0.5 if conf == "fact" else 0.25
    if _TREND.search(text) or "单调上升" in text or "monoton" in text.lower():
        score += 0.3
    if _NONE_ACTION.search(signal.get("action", "")):
        score += 0.2
    return round(min(score, 1.0), 2)


def _domain_of_code(code: str) -> str:
    parts = code.split(".")
    return parts[1] if len(parts) >= 2 else ""


# Slice 4（风险下降判据）：只读观察器。判据见 docs/36。
# 严格的「同口径序列」= 一条句子内，用箭头连接的每一段都以「数字%」结尾，
# 段内不得含括号（括号常插入异口径数字，如 E7 的 symbol 计数链混入百分比）。
# 这样：E4「27.3% → 31.7% → 31.9% → 32.24%」命中；E2 命中(mixed)；
# E7「4 個 symbol → 1 個 (1.9%…) → residual 3 個」因段内有括号/段尾非 % 被排除。
_SENTENCE = re.compile(r"[^。；;\n]+")
_SEGMENT = re.compile(r"(?:\d+(?:\.\d+)?)\s*%")
_THRESHOLD = re.compile(r"critical_ratio\s*[`']?\s*(0?\.\d+)", re.IGNORECASE)


def _trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "n/a"
    if all(v >= values[i - 1] for i, v in enumerate(values) if i > 0) \
            and values[-1] > values[0]:
        return "rising"
    if all(v <= values[i - 1] for i, v in enumerate(values) if i > 0) \
            and values[-1] < values[0]:
        return "falling"
    return "flat" if values[-1] == values[0] else "mixed"


def extract_metric_trend(signal: dict) -> dict | None:
    """从 finding/evidence 抽取同口径箭头序列；只读、不推断，抽不出返回 None。

    判据（见 docs/36）：同一句子内用箭头连接 >=2 段，每段含「数字%」，
    且括号内不得含 %（防异口径插入）。不满足即返回 None——宁可不观察，
    也不把异口径数字拼成趋势。
    返回 {values, unit, direction, first, latest, delta, threshold, source_field}。
    """
    if not isinstance(signal, dict):
        return None
    for field in ("finding", "evidence"):
        text = str(signal.get(field, "") or "")
        for sentence in _SENTENCE.findall(text):
            if "→" not in sentence and "->" not in sentence:
                continue
            parts = re.split(r"→|->", sentence)
            if len(parts) < 2:
                continue
            # 每段必须干净地以「数字%」结尾，且段内无括号插入（防跨口径混拼）。
            values: list[float] = []
            valid = True
            for part in parts:
                seg = part.strip()
                # 括号内若含 % 数值 = 异口径插入（如 E7 symbol 计数链混入 1.9%/8.8%），
                # 拒绝；纯标签括号（如 (fact)）不含 %，允许。
                for inside in re.findall(r"\([^)]*\)|（[^）]*）", seg):
                    if _SEGMENT.search(inside):
                        valid = False
                        break
                if not valid:
                    break
                tail = list(_SEGMENT.finditer(seg))
                if not tail:
                    valid = False
                    break
                values.append(float(tail[-1].group(0).rstrip("%").strip()))
            if not valid or len(values) < 2:
                continue
            tm = _THRESHOLD.search(text)
            return {
                "values": values,
                "unit": "%",
                "direction": _trend_direction(values),
                "first": values[0],
                "latest": values[-1],
                "delta": round(values[-1] - values[0], 4),
                "threshold": float(tm.group(1)) if tm else None,
                "source_field": field,
            }
    return None


# Slice 5（关闭回路）：风险关闭必须由账本决策显式表达，不靠"有引用"推断。
# fail-closed：只有 status ∈ EFFECTIVE_STATUS 且 decision/title 含显式关闭意图标记，
# 才认定信号已裁决关闭。D-023 引用 E4 但写"不关警报" → 判 open（正确）。
_EFFECTIVE_STATUS = {"done", "decided", "approved"}
_CLOSE_MARKERS = (
    "关闭风险", "關閉風險", "风险关闭", "風險關閉", "接受残余风险", "接受殘餘風險",
    "close risk", "risk closed", "risk disposition", "accept residual risk",
    "关闭信号", "關閉信號", "close signal",
)
_REF_SUFFIX = re.compile(r"#(E\d+)\b")


def signal_disposition(signal: dict, decisions: list[dict] | None = None) -> dict:
    """从账本决策判定信号是否已裁决关闭；只读、fail-closed、不推断。

    判据（见 docs/36）：
      1. 决策 evidence 含指向本信号的 `*.md#E<n>` 引用（source_file + id 双匹配）；
      2. 决策 status ∈ {done, decided, approved}（proposed/deferred/superseded 不算）；
      3. decision/title 含显式关闭意图标记——"有引用但不关警报"（如 D-023）判 open。
    无匹配 / 猜不出 → open。返回 {status, decision_id, marker, note}。
    """
    result = {"status": "open", "decision_id": None, "marker": None,
              "note": "无显式关闭决策（fail-closed）"}
    if not isinstance(signal, dict):
        return result
    sid = str(signal.get("id", ""))
    src = str(signal.get("source_file", ""))
    if not sid or not src:
        return result
    for dec in decisions or []:
        if not isinstance(dec, dict):
            continue
        if dec.get("status") not in _EFFECTIVE_STATUS:
            continue
        refs = [r for r in (dec.get("evidence") or []) if isinstance(r, str)]
        linked = False
        for ref in refs:
            m = _REF_SUFFIX.search(ref)
            # ref 形如 ".../2026-11-20.md#E4"：先按 # 去掉锚点，再取文件名比对。
            if m and m.group(1) == sid and Path(ref.split("#")[0]).name == src:
                linked = True
                break
        if not linked:
            continue
        text = f"{dec.get('decision', '')} {dec.get('title', '')}"
        marker = next((k for k in _CLOSE_MARKERS if k.lower() in text.lower()), None)
        if marker:
            return {"status": "adjudicated_closed", "decision_id": dec.get("id"),
                    "marker": marker, "note": "账本决策显式关闭（operator 裁决）"}
    return result


def risk_outcome(signals: list[dict], as_of: datetime | None = None,
                 decisions: list[dict] | None = None) -> list[dict]:
    """只读对照：把指标方向与衰减方向并列，不下"风险已下降"结论。

    每条输出固定 outcome='observed_only'：观察器只提供证据，关闭必须走账本决策。
    decisions 可选：传入时附加 disposition（信号是否已被账本决策显式关闭）。
    decay_vs_metric:
      divergent = 指标恶化(rising) 但分数因衰减下降 → 最需警惕的假绿灯形态
      aligned    = 指标改善(falling) 且分数下降 → 方向一致，但仍不构成关闭
      n/a        = 无可抽取序列 / 未启用衰减
    """
    if as_of is None:
        return []
    rows: list[dict] = []
    for s in signals or []:
        if not isinstance(s, dict):
            continue
        trend = extract_metric_trend(s)
        age = signal_age_days(s, as_of)
        factor = decay_factor(age, DEFAULT_MAX_AGE_DAYS) if age is not None else None
        decayed = factor is not None and factor < 1
        if trend is None:
            relation = "n/a"
        elif trend["direction"] == "rising" and decayed:
            relation = "divergent"
        elif trend["direction"] == "falling" and decayed:
            relation = "aligned"
        else:
            relation = "n/a"
        row = {
            "id": str(s.get("id", "")),
            "source_file": str(s.get("source_file", "")),
            "metric_trend": trend,
            "age_days": age,
            "decay_factor": factor,
            "score_decayed": decayed,
            "decay_vs_metric": relation,
            "outcome": "observed_only",
        }
        if decisions is not None:
            row["disposition"] = signal_disposition(s, decisions)
        rows.append(row)
    return rows


def apply_risk_signals(queue: list[dict], signals: list[dict], model: dict) -> list[dict]:
    """返回重排后的新列表；不入参不变。命中风险信号的域提升到低 completion 之前。"""
    by_domain: dict[str, tuple[float, str]] = {}
    for s in signals:
        domain = domain_hint(s)
        score = risk_score(s)
        if not domain or score <= 0:
            continue
        prev = by_domain.get(domain)
        if prev is None or score > prev[0]:
            by_domain[domain] = (score, s["id"])

    if not by_domain:
        return [dict(t) for t in queue]

    # 域内也按 completion 升序，保证同域多任务稳定可复现。
    def key(t: dict) -> tuple:
        domain = _domain_of_code(t["code"])
        hit = by_domain.get(domain)
        return (-(hit[0] if hit else 0.0), t.get("completion", 0.0), t["code"])

    ordered = sorted(queue, key=key)
    out = []
    for i, t in enumerate(ordered, 1):
        row = dict(t)
        row["rank"] = i
        domain = _domain_of_code(t["code"])
        hit = by_domain.get(domain)
        row["risk_score"] = hit[0] if hit else 0.0
        row["risk_signal"] = hit[1] if hit else None
        out.append(row)
    return out


# ------------------------- Slice 2：精确能力点映射 -------------------------

def _cap_token(code: str) -> str:
    """能力码第三段是能力点 token：P.DATA.PROVIDER.05 → PROVIDER。"""
    parts = str(code).split(".")
    return parts[2] if len(parts) >= 3 else ""


def _model_codes(model: dict) -> list[str]:
    codes: list[str] = []
    for p in (model or {}).get("projects", []):
        for m in p.get("modules", []):
            for c in m.get("caps", []):
                if isinstance(c, dict) and c.get("code"):
                    codes.append(str(c["code"]))
    return codes


def _signal_score(signal: dict) -> float:
    """已投影条目带 risk_score 时沿用，避免二次评分漂移；否则按事件原文评分。"""
    if "risk_score" in signal:
        try:
            return round(min(max(float(signal["risk_score"]), 0.0), 1.0), 2)
        except (TypeError, ValueError):
            return 0.0
    return risk_score(signal)


def capability_hits(signal: dict, model: dict) -> list[str]:
    """把一条信号映射到精确能力码；无法唯一确定时返回空列表（fail-closed）。

    优先级：事件显式字段 > 原文完整能力码 > 语义词表。语义词表按“更长关键词
    优先”，同长跨 token 命中视为歧义。任何结果必须存在于 model 的能力码全集。
    """
    codes = _model_codes(model)
    known = set(codes)
    hits: list[str] = []

    for key in ("capability", "capabilities", "target"):
        value = signal.get(key)
        values = value if isinstance(value, list) else [value]
        for raw in values:
            if not isinstance(raw, str):
                continue
            code = raw.strip()
            if code in known and code not in hits:
                hits.append(code)
    if hits:
        return sorted(hits)

    text = " ".join(str(signal.get(k, "")) for k in
                    ("title", "finding", "evidence", "action")).lower()
    for code in _CAP_CODE.findall(text):
        if code in known and code not in hits:
            hits.append(code)
    if hits:
        return sorted(hits)

    best_len, tokens = -1, []
    for token, keywords in CAPABILITY_ALIASES:
        for kw in keywords:
            if kw.lower() in text and len(kw) > best_len:
                best_len, tokens = len(kw), [token]
            elif kw.lower() in text and len(kw) == best_len and token not in tokens:
                tokens.append(token)
    if not tokens:
        return []
    # 只用显式 domain 收窄（已投影条目）；原文关键词可能跨域（momentum 判 DATA，
    # 但 RSCOV 能力在 RS 域），此时语义词表已足够精确，不再用启发式域过滤。
    explicit_domain = signal.get("domain")
    matched = [c for c in codes
               if _cap_token(c) in tokens
               and (not explicit_domain or _domain_of_code(c) == explicit_domain)]
    if len(tokens) > 1 and len({_cap_token(c) for c in matched}) > 1:
        return []
    return sorted(set(matched))


def project_signals(signals: list[dict], model: dict,
                    as_of: datetime | None = None,
                    max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> list[dict]:
    """产出可序列化给生成器的精确投影；只含可追溯字段，绝不写盘。

    只有显式传入 as_of 才启用时间衰减；不传则保持无时间字段的既有行为。
    启用时无 time / 不可解析 / 达到 max_age_days 的信号一律 fail-closed
    不进投影；同时输出 observed_at / age_days / decay_factor，使投影可复算。
    """
    enforce = as_of is not None
    entries: list[dict] = []
    for s in signals or []:
        if not isinstance(s, dict):
            continue
        # operator 裁决项（服务重启/数据修复/告警规则）不属于 L1 自动队列的
        # 可补证据能力点；投影它只会造出「补个测试记录就关警报」的假任务。
        # 这类信号应如实记录为 operator 警报，不进 next_queue 风险排序。
        if _OPERATOR_ACTION.search(str(s.get("action", ""))):
            continue
        age = signal_age_days(s, as_of) if enforce else None
        factor = decay_factor(age, max_age_days) if enforce else None
        if enforce and (factor is None or factor <= 0):
            continue
        score = _signal_score(s)
        if enforce:
            score = round(score * factor, 4)
        if score <= 0:
            continue
        caps = capability_hits(s, model)
        if not caps:
            continue
        entry = {
            "id": str(s.get("id", "")),
            "source_file": str(s.get("source_file", "")),
            "confidence": s.get("confidence", "unknown"),
            "domain": s.get("domain") or domain_hint(s),
            "risk_score": score,
            "capabilities": caps,
        }
        if enforce:
            entry["observed_at"] = str(s.get("time", ""))
            entry["age_days"] = age
            entry["decay_factor"] = factor
        entries.append(entry)
    return entries


def _apply_projected(queue: list[dict], entries: list[dict]) -> list[dict]:
    by_code: dict[str, tuple[float, str, str]] = {}
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        score = _signal_score(e)
        if score <= 0:
            continue
        sid, src = str(e.get("id", "")), str(e.get("source_file", ""))
        caps = e.get("capabilities") or []
        if isinstance(caps, str):
            caps = [caps]
        for code in caps:
            if not isinstance(code, str):
                continue
            prev = by_code.get(code)
            evidence = f"{src}#{sid}" if src or sid else ""
            if prev is None or score > prev[0]:
                by_code[code] = (score, sid, evidence)

    def key(t: dict) -> tuple:
        hit = by_code.get(str(t.get("code", "")))
        return (-(hit[0] if hit else 0.0), t.get("completion", 0.0), str(t.get("code", "")))

    out = []
    for i, t in enumerate(sorted(queue, key=key), 1):
        row = dict(t)
        row["rank"] = i
        hit = by_code.get(str(t.get("code", "")))
        row["risk_score"] = hit[0] if hit else 0.0
        row["risk_signal"] = hit[1] if hit else None
        row["risk_evidence"] = hit[2] if hit else None
        out.append(row)
    return out


def apply_risk_signals_exact(queue: list[dict], signals: list[dict],
                             model: dict) -> list[dict]:
    """Slice 2 入口：只按精确能力点命中重排；歧义信号不参与，入参不变。"""
    return _apply_projected(queue, project_signals(signals, model))
