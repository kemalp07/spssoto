"""Wizard adım atlama kuralları — test edilebilir saf fonksiyonlar."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def should_skip_scales_step(
    registry_matched: List[dict],
    detected_scales: List[dict],
) -> bool:
    """En az bir high-confidence registry eşleşmesi ve tespit edilmiş ölçek."""
    high = [m for m in (registry_matched or []) if m.get("confidence") == "high"]
    if len(high) < 1:
        return False
    return len(detected_scales or []) >= 1


def scales_from_detection(detected_scales: List[dict]) -> str:
    names = [str(s.get("name") or "").strip() for s in (detected_scales or [])]
    names = [n for n in names if n]
    return ", ".join(dict.fromkeys(names))


def should_skip_topic_step(etik_kurul: Optional[dict]) -> bool:
    if not etik_kurul or etik_kurul.get("parse_error"):
        return False
    hyps = etik_kurul.get("hypotheses") or []
    return len(hyps) >= 1


def topic_from_etik_kurul(etik_kurul: Optional[dict]) -> str:
    if not etik_kurul:
        return ""
    hyps = etik_kurul.get("hypotheses") or []
    if hyps:
        return "\n".join(str(h).strip() for h in hyps if str(h).strip())
    aim = (etik_kurul.get("aim") or "").strip()
    return aim


def is_label_complete(col: str, labels: Dict[str, str]) -> bool:
    label = (labels.get(col) or "").strip()
    if not label:
        return False
    if label == col:
        return False
    return True


def should_skip_labels_phase(
    columns: List[str],
    labels: Dict[str, str],
    item_pattern_match=None,
    exclude_patterns=None,
) -> bool:
    """Tüm analiz sütunları SPSS/Excel etiketi ile doluysa etiket adımı atlanır."""
    cols = list(columns or [])
    if item_pattern_match:
        cols = [c for c in cols if not item_pattern_match(c)]
    if exclude_patterns:
        cols = [c for c in cols if not any(p.search(c) for p in exclude_patterns)]
    if not cols:
        return False
    return all(is_label_complete(c, labels) for c in cols)


def topic_step_optional(etik_kurul_loaded: bool) -> bool:
    return not etik_kurul_loaded
