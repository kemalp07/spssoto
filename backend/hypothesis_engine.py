"""Araştırma sorusu / hipotez ayrıştırma ve test aday eşleme."""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from constants import (
    GEMINI_HYPOTHESIS_SPLIT_SYSTEM,
    HYPOTHESIS_DECIDE_SYSTEM,
    HYPOTHESIS_SINGLE_STAGE_SYSTEM,
    _TR_ASCII,
)
from data_cleaning import detect_scale_groups
from llm_router import (
    claude_decide,
    format_enrichment_block,
    gemini_enrich_profile,
    gemini_json_task,
    has_claude,
    has_gemini_enrich,
    merge_meta,
)
from schemas import Variable

MAX_HYPOTHESES = 8
MAX_HYPOTHESIS_TOKENS = 1200
_LABEL_MAX = 40

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


async def parse_research_questions(
    text: str,
    variables: List[Variable],
    uygun_candidates: List[dict],
    scale_groups: Optional[Dict[str, List[str]]] = None,
    df: Optional[pd.DataFrame] = None,
) -> Tuple[dict, dict]:
    """Gemini enrich → Claude decide (veya tek aşama fallback)."""
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    text = (text or "").strip()
    if not text or not uygun_candidates:
        return {"hypotheses": [], "unmatched": []}, meta

    labels = compact_labels(variables)
    valid_ids = {c["id"] for c in uygun_candidates}
    compact = _compact_candidates_for_llm(uygun_candidates)
    scale_groups = scale_groups or detect_scale_groups(
        [v.name for v in variables if v.included],
    )

    split_items: list = []
    enrich_meta: dict = {}
    gemini_block = ""

    if has_gemini_enrich():
        split_items, enrich_meta = _gemini_split_questions(text, labels)
        if split_items:
            gemini_block = (
                "\n\nGemini aday sorular:\n"
                + json.dumps(split_items, ensure_ascii=False)[:4000]
            )

    if has_claude():
        if split_items:
            user_msg = (
                f"Araştırma metni:\n{text[:2000]}\n"
                f"Etiketler: {json.dumps(labels, ensure_ascii=False)}\n"
                f"Ölçek grupları: {json.dumps(list(scale_groups.keys())[:12], ensure_ascii=False)}\n"
                f"{gemini_block}\n"
                f"Test adayları: {json.dumps(compact, ensure_ascii=False)}"
            )
            system = HYPOTHESIS_DECIDE_SYSTEM
        else:
            user_msg = (
                f"Araştırma metni:\n{text[:2000]}\n"
                f"Etiketler: {json.dumps(labels, ensure_ascii=False)}\n"
                f"Test adayları: {json.dumps(compact, ensure_ascii=False)}"
            )
            system = HYPOTHESIS_SINGLE_STAGE_SYSTEM

        if df is not None and variables and has_gemini_enrich():
            from data_profile import profile_from_dataframe, profile_json
            profile = profile_from_dataframe(df, variables)
            enrichment, profile_meta = gemini_enrich_profile(
                "hypotheses", profile, text,
            )
            enrich_meta = merge_meta(enrich_meta, profile_meta)
            user_msg += (
                f"\nVeri profili:\n{profile_json(profile)[:6000]}"
                f"{format_enrichment_block(enrichment)}"
            )

        try:
            raw, decide_meta = claude_decide(
                system, user_msg, max_tokens=MAX_HYPOTHESIS_TOKENS,
            )
            meta = merge_meta(enrich_meta, decide_meta)
            parsed = _parse_json_object(raw)
            hypotheses, unmatched = _normalize_hypothesis_response(parsed, valid_ids)
            return {"hypotheses": hypotheses, "unmatched": unmatched}, meta
        except RuntimeError:
            pass

    if split_items:
        hypotheses, unmatched = _fallback_match_by_hints(split_items, uygun_candidates, labels)
        meta = merge_meta(enrich_meta, meta)
        return {"hypotheses": hypotheses, "unmatched": unmatched}, meta

    return {"hypotheses": [], "unmatched": [text[:200]]}, meta


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
