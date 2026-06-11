"""Akademik raporlama rehberi — tek kaynak JSON yükleyici."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

_RULES_PATH = Path(__file__).resolve().parent / "raporlama_kurallari.json"


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def effect_size_label(kind: str, value: Optional[float]) -> str:
    if value is None:
        return ""
    rules = load_rules()
    tiers = rules.get("effect_sizes", {}).get(kind, {}).get("labels", [])
    v = abs(float(value))
    for tier in tiers:
        if v >= float(tier.get("min", 0)):
            return str(tier.get("label", ""))
    return ""


def posthoc_empty_phrase(posthoc_type: str) -> str:
    key_map = {
        "tukey": "tukey_no_pairs",
        "games_howell": "games_howell_no_pairs",
        "dunn": "dunn_no_pairs",
    }
    key = key_map.get(posthoc_type, "dunn_no_pairs")
    return load_rules().get("posthoc", {}).get(key, "")


def decision_phrase(key: str) -> str:
    return load_rules().get("decisions", {}).get(key, "")


def label_cleanup_patterns() -> List[tuple]:
    out = []
    for item in load_rules().get("label_cleanup", []):
        pat = item.get("pattern")
        repl = item.get("replace")
        if pat and repl is not None:
            out.append((pat, repl))
    return out


def llm_compact_rules() -> List[str]:
    return list(load_rules().get("llm_compact_rules", []))


def hypothesis_phrase(hypothesis_id: str, supported: bool) -> str:
    rules = load_rules().get("summary", {})
    tpl = rules.get("hypothesis_supported" if supported else "hypothesis_not_supported", "")
    return tpl.format(id=hypothesis_id) if tpl else ""


def vif_tier(value: Optional[float]) -> str:
    if value is None:
        return ""
    tiers = load_rules().get("vif", {}).get("tiers", [])
    v = float(value)
    for tier in sorted(tiers, key=lambda t: float(t.get("min", 0)), reverse=True):
        if v >= float(tier.get("min", 0)):
            return str(tier.get("label", ""))
    return ""


def vif_warning_text(max_vif: Optional[float]) -> str:
    if max_vif is None:
        return ""
    if float(max_vif) >= 10:
        return load_rules().get("vif", {}).get("warning_high", "")
    if float(max_vif) < 5:
        return load_rules().get("vif", {}).get("ok_range", "")
    return ""


def qc_message(key: str) -> str:
    return load_rules().get("qc_rules", {}).get(key, "")


def cronbach_tier_from_rules(alpha: Optional[float]) -> str:
    if alpha is None:
        return ""
    for tier in load_rules().get("cronbach", {}).get("tiers", []):
        if float(alpha) >= float(tier.get("min", 0)):
            return str(tier.get("label", ""))
    return ""


def cronbach_warnings_from_rules(alpha: Optional[float]) -> Optional[str]:
    cb = load_rules().get("cronbach", {})
    if alpha is None:
        return None
    a = float(alpha)
    if a < 0.60:
        return cb.get("warning_below_60")
    if a < 0.70:
        return cb.get("warning_below_70")
    return None
