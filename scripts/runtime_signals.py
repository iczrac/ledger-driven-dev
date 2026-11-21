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
