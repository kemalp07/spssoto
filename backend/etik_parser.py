"""
Etik kurul belgesinden doğrudan test hipotezleri çıkar.
AI kullanmaz — keyword matching + istatistik kuralları.
"""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

from constants import _TR_ASCII
from schemas import Variable

COMPARISON_KEYWORDS = frozenset({
    "karsilastir", "karsilastirma", "fark", "farklilik",
    "gruplar arasi", "gruplararas", "gruplar", "etkisi",
})
CORRELATION_KEYWORDS = frozenset({
    "iliski", "iliskisi", "korelasyon", "baglanti",
})
REGRESSION_KEYWORDS = frozenset({
    "yordama", "tahmin", "etki", "regresyon", "aciklama",
})

_COMPARISON_TESTS = frozenset({
    "ttest", "welch", "mann_whitney", "anova", "kruskal_wallis",
    "paired_ttest", "wilcoxon", "chi_square",
})
_CORRELATION_TESTS = frozenset({"correlation"})
_REGRESSION_TESTS = frozenset({"regression"})


def _norm_text(s: str) -> str:
    return (s or "").lower().translate(_TR_ASCII).replace("_", " ")


def _line_intent(line_norm: str) -> str:
    if any(k in line_norm for k in CORRELATION_KEYWORDS):
        return "iliski"
    if any(k in line_norm for k in REGRESSION_KEYWORDS):
        return "yordama"
    if any(k in line_norm for k in COMPARISON_KEYWORDS):
        return "fark"
    return "fark"


def _var_mentioned(var: Variable, line_norm: str) -> bool:
    for token in (_norm_text(var.name), _norm_text(var.label or "")):
        t = token.strip()
        if len(t) >= 2 and t in line_norm:
            return True
    return False


def _match_candidates_for_line(
    line: str,
    candidates: List[dict],
    variables: List[Variable],
    validator_fn: Callable,
) -> List[str]:
    line_norm = _norm_text(line)
    intent = _line_intent(line_norm)
    vmap: Dict[str, Variable] = {v.name: v for v in variables}
    mentioned = [
        v for v in variables
        if v.included and _var_mentioned(v, line_norm)
    ]

    matched_ids: List[str] = []
    for cand in candidates:
        test = str(cand.get("test") or "")
        if intent == "iliski" and test not in _CORRELATION_TESTS:
            continue
        if intent == "yordama" and test not in _REGRESSION_TESTS:
            continue
        if intent == "fark" and test not in _COMPARISON_TESTS:
            continue

        vars_ = cand.get("vars") or []
        if mentioned and not any(v.name in vars_ for v in mentioned):
            continue

        outcome = vmap.get(vars_[-1]) if vars_ else None
        grouping = vmap.get(vars_[0]) if len(vars_) > 1 else None
        n_groups = cand.get("n_groups")

        if outcome:
            ok, _ = validator_fn(test, grouping, outcome, n_groups)
            if ok:
                matched_ids.append(str(cand["id"]))
    return matched_ids


def parse_etik_to_hypotheses(
    etik_text: str,
    variables: List[Variable],
    candidates: List[dict],
    validator_fn: Optional[Callable] = None,
) -> List[dict]:
    """
    Etik belgeden hipotezleri çıkar ve istatistik kurallarıyla validate et.
    Geçersiz adaylar listeye alınmaz.
    """
    from test_planner import validate_test_selection

    if validator_fn is None:
        validator_fn = validate_test_selection

    lines = [ln.strip() for ln in re.split(r"[\n;]+", etik_text or "") if ln.strip()]
    if not lines and (etik_text or "").strip():
        lines = [etik_text.strip()]

    hypotheses: List[dict] = []
    for line in lines:
        if len(line) < 10:
            continue
        cids = _match_candidates_for_line(
            line, candidates, variables, validator_fn,
        )
        if not cids:
            continue
        hypotheses.append({
            "id": f"H{len(hypotheses) + 1}",
            "label": line[:120],
            "type": _line_intent(_norm_text(line)),
            "candidate_ids": cids[:3],
            "var_hints": [],
        })
    return hypotheses
