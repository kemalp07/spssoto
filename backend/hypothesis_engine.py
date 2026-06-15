"""Araştırma sorusu / hipotez ayrıştırma ve test aday eşleme."""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from constants import (
    GEMINI_HYPOTHESIS_SPLIT_SYSTEM,
    _TR_ASCII,
)
from llm_router import (
    claude_decide,
    gemini_json_task,
    has_claude,
    has_gemini_enrich,
    merge_meta,
)
from schemas import Variable

MAX_HYPOTHESES = 8
MAX_HYPOTHESIS_TOKENS = 1200
MAX_REASON_TRANSLATE_TOKENS = 1500
_LABEL_MAX = 40

REASON_TRANSLATE_SYSTEM = """Sen akademik Türkçe editörüsün.
Verilen istatistik test seçim gerekçelerini akıcı, tek cümlelik onay ekranı metnine çevir.
Test seçimini, p değerlerini veya test adlarını DEĞİŞTİRME.
SADECE JSON döndür: {"reasons": ["...", "..."]}
Girdi sırasını koru; her girdi için bir çıktı üret."""

SAMPLE_SECTION_TYPES = frozenset({
    "demographics",
    "descriptive",
    "frequency",
    "cronbach",
    "normality",
})

_VALID_TYPES = frozenset({"fark", "iliski", "yordama"})


def _truncate_label(label: str) -> str:
    label = (label or "").strip()
    if len(label) <= _LABEL_MAX:
        return label
    return label[: _LABEL_MAX - 1] + "…"


def compact_labels(variables: List[Variable]) -> Dict[str, str]:
    return {
        v.name: _truncate_label(v.label or v.name)
        for v in variables if v.included
    }


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _parse_json_array(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _normalize_type(value: str) -> str:
    t = str(value or "").strip().lower()
    return t if t in _VALID_TYPES else "fark"


def _normalize_hypothesis_response(
    data: dict,
    valid_ids: set,
) -> Tuple[List[dict], List[str]]:
    hypotheses: List[dict] = []
    used_candidates: set = set()

    for idx, raw in enumerate(data.get("hypotheses") or []):
        if idx >= MAX_HYPOTHESES:
            break
        if not isinstance(raw, dict):
            continue
        candidate_ids = [
            str(cid)
            for cid in (raw.get("candidate_ids") or [])
            if str(cid) in valid_ids and str(cid) not in used_candidates
        ]
        if not candidate_ids:
            continue
        used_candidates.update(candidate_ids)
        hid = str(raw.get("id") or f"H{len(hypotheses) + 1}")
        hypotheses.append({
            "id": hid,
            "label": str(raw.get("label") or raw.get("q") or hid).strip()[:120],
            "type": _normalize_type(raw.get("type")),
            "candidate_ids": candidate_ids,
            "var_hints": [
                str(v).strip().lower()
                for v in (raw.get("var_hints") or [])[:6]
                if str(v).strip()
            ],
        })

    unmatched = [
        str(u).strip()
        for u in (data.get("unmatched") or [])
        if str(u).strip()
    ]
    return hypotheses, unmatched


def filter_ai_hypothesis_matches(
    hypotheses: List[dict],
    variables: List[Variable],
    candidates: List[dict],
) -> List[dict]:
    """
    AI'ın önerdiği hipotez-test eşleştirmelerini istatistik kurallarıyla filtrele.
    Geçersiz test önerileri reddedilir ve loglanır.
    """
    from test_planner import validate_test_selection

    vmap = {v.name: v for v in variables}
    filtered: List[dict] = []
    logger = logging.getLogger(__name__)

    for hyp in hypotheses or []:
        valid_candidates: List[str] = []
        for cid in hyp.get("candidate_ids") or []:
            cand = next((c for c in candidates if c["id"] == cid), None)
            if not cand:
                continue
            vars_ = cand.get("vars") or []
            if not vars_:
                continue

            outcome = vmap.get(vars_[-1])
            grouping = vmap.get(vars_[0]) if len(vars_) > 1 else None
            n_groups = cand.get("n_groups")

            if outcome:
                ok, reason = validate_test_selection(
                    cand["test"], grouping, outcome, n_groups,
                )
                if ok:
                    valid_candidates.append(str(cid))
                else:
                    logger.warning(
                        "[AI VALİDATOR] Geçersiz test reddedildi: "
                        f"{cand['test']} ({reason})"
                    )
            else:
                valid_candidates.append(str(cid))

        if valid_candidates:
            item = dict(hyp)
            item["candidate_ids"] = valid_candidates
            filtered.append(item)

    return filtered


def _gemini_split_questions(text: str, labels: Dict[str, str]) -> Tuple[list, dict]:
    if not has_gemini_enrich():
        return [], {}
    user = (
        f"Araştırma metni:\n{text.strip()[:2000]}\n"
        f"Değişken etiketleri: {json.dumps(labels, ensure_ascii=False)}"
    )
    raw, meta = gemini_json_task(
        GEMINI_HYPOTHESIS_SPLIT_SYSTEM, user, MAX_HYPOTHESIS_TOKENS,
    )
    items = _parse_json_array(raw)
    cleaned = []
    for item in items[:MAX_HYPOTHESES]:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or "").strip()
        if not q:
            continue
        cleaned.append({
            "q": q[:120],
            "type": _normalize_type(item.get("type")),
            "var_hints": [
                str(v).strip().lower()
                for v in (item.get("var_hints") or [])[:6]
                if str(v).strip()
            ],
        })
    return cleaned, meta


def _fallback_match_by_hints(
    split_items: list,
    uygun: List[dict],
    labels: Dict[str, str],
) -> Tuple[List[dict], List[str]]:
    """LLM yoksa basit ipucu eşlemesi."""
    label_norm = {
        name: (name + " " + label).lower().translate(_TR_ASCII).replace("_", "")
        for name, label in labels.items()
    }
    used: set = set()
    hypotheses: List[dict] = []
    unmatched: List[str] = []

    for idx, item in enumerate(split_items[:MAX_HYPOTHESES]):
        q = item.get("q") or ""
        hints = item.get("var_hints") or []
        matched: List[str] = []
        for cand in uygun:
            cid = cand["id"]
            if cid in used:
                continue
            blob = " ".join(cand.get("vars") or []).lower()
            blob += " " + " ".join(
                label_norm.get(v, v) for v in (cand.get("vars") or [])
            )
            if any(h in blob for h in hints if h):
                matched.append(cid)
        if matched:
            used.update(matched)
            hypotheses.append({
                "id": f"H{len(hypotheses) + 1}",
                "label": q[:120],
                "type": item.get("type") or "fark",
                "candidate_ids": matched[:3],
                "var_hints": hints,
            })
        else:
            unmatched.append(q)
    return hypotheses, unmatched


def _compact_candidates_for_llm(candidates: List[dict]) -> List[dict]:
    return [
        {
            "id": c["id"],
            "test": c["test"],
            "vars": c["vars"],
            "n_groups": c.get("n_groups"),
            "parametric": c.get("parametric"),
        }
        for c in candidates
    ]


async def translate_decision_reasons(
    reasons: List[str],
) -> Tuple[List[str], dict]:
    """Kural motoru reason string'lerini toplu olarak akıcı Türkçeye çevirir."""
    meta: dict = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    cleaned = [str(r or "").strip() for r in reasons]
    if not cleaned or not any(cleaned):
        return cleaned, meta
    if not has_claude() and not has_gemini_enrich():
        return cleaned, meta

    payload = json.dumps({"reasons": cleaned}, ensure_ascii=False)
    user = f"Gerekçeler:\n{payload}"
    try:
        if has_claude():
            raw, decide_meta = claude_decide(
                REASON_TRANSLATE_SYSTEM, user, max_tokens=MAX_REASON_TRANSLATE_TOKENS,
            )
            meta = merge_meta(meta, decide_meta)
        else:
            raw, decide_meta = gemini_json_task(
                REASON_TRANSLATE_SYSTEM, user, MAX_REASON_TRANSLATE_TOKENS,
            )
            meta = merge_meta(meta, decide_meta)
        data = _parse_json_object(raw)
        translated = data.get("reasons") or []
        if isinstance(translated, list) and len(translated) == len(cleaned):
            return [str(t).strip() or cleaned[i] for i, t in enumerate(translated)], meta
    except (RuntimeError, TypeError, ValueError):
        pass
    return cleaned, meta


async def parse_research_questions(
    text: str,
    variables: List[Variable],
    uygun_candidates: List[dict],
    scale_groups: Optional[Dict[str, List[str]]] = None,
    df: Optional[pd.DataFrame] = None,
    gemini_context: Optional[dict] = None,
    document_context: Optional[dict] = None,
) -> Tuple[dict, dict]:
    """Kural tabanlı puanlama + AI yalnızca gerekçe çevirisi."""
    from etik_parser import parse_etik_to_hypotheses
    from test_planner import (
        candidate_display_label,
        partition_scored_candidates,
        score_candidates_from_context,
    )

    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not uygun_candidates:
        return {"hypotheses": [], "unmatched": [], "candidates": [], "low_priority": []}, meta

    labels = compact_labels(variables)
    scored = score_candidates_from_context(uygun_candidates, text or "", labels)
    primary, accordion = partition_scored_candidates(scored)

    hypotheses: List[dict] = []
    unmatched: List[str] = []
    if document_context:
        etik = document_context.get("etik_kurul") or {}
        if not etik.get("parse_error"):
            etik_parts = etik.get("hypotheses") or []
            aim = etik.get("aim") or ""
            etik_text = "\n".join(str(h) for h in etik_parts if h)
            if aim:
                etik_text = f"{etik_text}\n{aim}".strip()
            if not etik_text.strip():
                etik_text = text or ""
            if etik_text.strip():
                raw_hyps = parse_etik_to_hypotheses(
                    etik_text, variables, uygun_candidates,
                )
                hypotheses = filter_ai_hypothesis_matches(
                    raw_hyps, variables, uygun_candidates,
                )

    reason_targets = primary + accordion
    reasons = [
        (c.get("decision_log") or {}).get("reason") or c.get("reason", "")
        for c in reason_targets
    ]
    translated, tr_meta = await translate_decision_reasons(reasons)
    meta = merge_meta(meta, tr_meta)
    meta["claude_used"] = bool(has_claude() and tr_meta.get("llm_provider") == "anthropic")
    meta["gemini_used"] = bool(
        tr_meta.get("enrich_provider") or (not has_claude() and tr_meta.get("llm_calls"))
    )
    meta["scoring_used"] = True

    for cand, tr_reason in zip(reason_targets, translated):
        if tr_reason:
            cand["reason"] = tr_reason
            if cand.get("decision_log"):
                cand["decision_log"] = {**cand["decision_log"], "reason": tr_reason}

    preview = [
        {
            "id": c["id"],
            "test": c.get("test"),
            "label": candidate_display_label(c, variables),
            "reason": c.get("reason", ""),
            "relevance_flag": c.get("relevance_flag"),
            "relevance_score": c.get("relevance_score", 0),
            "vars": c.get("vars") or [],
            "decision_log": c.get("decision_log"),
            "enabled_default": c.get("relevance_flag") == "uygun",
        }
        for c in primary
    ]
    low_priority = [
        {
            "id": c["id"],
            "test": c.get("test"),
            "label": candidate_display_label(c, variables),
            "reason": c.get("reason", ""),
            "relevance_flag": c.get("relevance_flag"),
            "relevance_score": c.get("relevance_score", 0),
            "vars": c.get("vars") or [],
            "decision_log": c.get("decision_log"),
            "enabled_default": False,
        }
        for c in accordion
    ]

    return {
        "hypotheses": hypotheses,
        "unmatched": unmatched,
        "candidates": preview,
        "low_priority": low_priority,
        "primary_count": len(preview),
        "accordion_count": len(low_priority),
    }, meta


def apply_hypothesis_to_catalog(
    catalog: List[dict],
    hypotheses: List[dict],
    core_ids: set,
) -> Dict[str, str]:
    """Hipoteze bağlı adayları kesin tier'a yükselt; hipotezsiz kesinleri düşür."""
    id_to_hyp: Dict[str, str] = {}
    for hyp in hypotheses:
        hid = str(hyp.get("id") or "")
        if not hid:
            continue
        for cid in hyp.get("candidate_ids") or []:
            cid = str(cid)
            if cid not in id_to_hyp:
                id_to_hyp[cid] = hid

    for item in catalog:
        cid = item.get("id")
        if item.get("cekirdek"):
            item.pop("hypothesis_id", None)
            continue
        if cid in id_to_hyp:
            item["tier"] = "kesin_onerilen"
            item["hypothesis_id"] = id_to_hyp[cid]
            item["selected"] = True
        elif item.get("tier") == "kesin_onerilen":
            item["tier"] = "onerilen"
            item.pop("hypothesis_id", None)

    return id_to_hyp


def build_test_hypothesis_map(catalog: List[dict]) -> Dict[str, str]:
    return {
        str(c["id"]): str(c["hypothesis_id"])
        for c in catalog
        if c.get("hypothesis_id")
    }


def _label_to_var_name(label: str, variables: List[Variable]) -> Optional[str]:
    target = str(label or "").strip().lower()
    if not target:
        return None
    for v in variables:
        if not v.included:
            continue
        if (v.label or "").strip().lower() == target:
            return v.name
        if v.name.lower() == target:
            return v.name
    return None


def result_to_candidate_id(result: dict, variables: List[Variable]) -> Optional[str]:
    from test_planner import make_candidate_id
    rtype = str(result.get("type") or "")
    if rtype == "descriptive":
        cont = [v.name for v in variables if v.included and v.type == "continuous" and v.role == "outcome"]
        return make_candidate_id("descriptive", cont) if cont else "descriptive"
    if rtype in ("frequency", "demographics"):
        var = result.get("variable")
        return f"frequency:{var}" if var else None
    if rtype in ("correlation", "correlation_matrix"):
        cont = [v.name for v in variables if v.included and v.type == "continuous" and v.role == "outcome"]
        return make_candidate_id("correlation", cont) if len(cont) >= 2 else "correlation"
    if rtype == "cronbach":
        items = sorted(result.get("items") or [])
        return make_candidate_id("cronbach", items) if items else None
    if rtype in ("ttest", "mann_whitney", "anova", "kruskal_wallis"):
        grouping = (
            result.get("grouping_name")
            or result.get("grouping_label")
            or ""
        )
        outcome = result.get("outcome_label") or ""
        if result.get("combined") and result.get("comparison_summaries"):
            for summary in result["comparison_summaries"]:
                ol = summary.get("outcome_label") or outcome
                oname = _label_to_var_name(ol, variables)
                gname = _label_to_var_name(grouping, variables) or grouping
                if gname and oname:
                    cid = make_candidate_id(rtype, [gname, oname])
                    return cid
        gname = _label_to_var_name(grouping, variables) or grouping
        oname = _label_to_var_name(outcome, variables) or outcome
        if gname and oname:
            return make_candidate_id(rtype, [gname, oname])
    if rtype == "chi_square":
        g = result.get("grouping_name") or result.get("var1")
        o = result.get("outcome_name") or result.get("var2")
        if g and o:
            return make_candidate_id("chi_square", [g, o])
    return None


def tag_results_with_hypotheses(
    results: List[dict],
    hypothesis_map: Dict[str, str],
    variables: List[Variable],
) -> List[dict]:
    if not hypothesis_map:
        return results
    tagged: List[dict] = []
    for result in results:
        item = dict(result)
        if item.get("type") in SAMPLE_SECTION_TYPES:
            tagged.append(item)
            continue
        cid = result_to_candidate_id(item, variables)
        if cid and cid in hypothesis_map:
            item["hypothesis_id"] = hypothesis_map[cid]
        tagged.append(item)
    return tagged


def compact_candidate_preview(uygun: List[dict], variables: List[Variable]) -> List[dict]:
    from test_planner import candidate_display_label
    return [
        {
            "id": c["id"],
            "test": c.get("test"),
            "label": candidate_display_label(c, variables),
        }
        for c in uygun[:40]
    ]


COMPARISON_TESTS = frozenset({
    "ttest", "mann_whitney", "anova", "chi_square", "kruskal_wallis",
})

CORE_TABLE_TESTS = frozenset({
    "descriptive", "frequency", "cronbach", "correlation", "normality",
})

_TEST_DISPLAY = {
    "ttest": "t-Testi",
    "mann_whitney": "Mann-Whitney",
    "anova": "ANOVA",
    "chi_square": "Ki-Kare",
    "kruskal_wallis": "Kruskal-Wallis",
    "correlation": "Korelasyon",
}

_CORE_UNMATCHED_RE = re.compile(
    r"tanımlayıcı|frekans|demograf|cronbach|güvenirlik|güvenilirlik|"
    r"örneklem|güvenilir|betimle|alpha",
    re.I,
)


def filter_unmatched_for_display(unmatched: List[str]) -> List[str]:
    """Çekirdek tablo sorularını unmatched uyarısından çıkar."""
    return [
        str(item).strip()
        for item in (unmatched or [])
        if str(item).strip() and not _CORE_UNMATCHED_RE.search(str(item))
    ]


def hypothesis_summary_line(
    hypothesis: dict,
    candidates_by_id: Dict[str, dict],
) -> str:
    hid = str(hypothesis.get("id") or "H?")
    parts: List[str] = []
    for cid in hypothesis.get("candidate_ids") or []:
        cand = candidates_by_id.get(str(cid), {})
        test = str(cand.get("test") or "")
        label = str(cand.get("label") or cid)
        test_name = _TEST_DISPLAY.get(test, test or "Test")
        detail = label
        for sep in ("—", "–", "-"):
            if sep in label:
                tail = label.split(sep, 1)[-1].strip()
                if tail:
                    detail = tail
                break
        parts.append(f"{test_name} ({detail})")
    if not parts:
        parts.append(str(hypothesis.get("label") or "").strip() or "—")
    return f"{hid} → {', '.join(parts)}"


def enrich_hypotheses_for_display(
    hypotheses: List[dict],
    candidates: List[dict],
) -> List[dict]:
    by_id = {str(c["id"]): c for c in candidates}
    enriched: List[dict] = []
    for hyp in hypotheses or []:
        item = dict(hyp)
        item["summary"] = hypothesis_summary_line(item, by_id)
        enriched.append(item)
    return enriched
