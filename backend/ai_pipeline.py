"""AI pipeline — Python hesap → Gemini analist → Claude karar verici."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from data_profile import find_derived_variables, profile_from_samples
from karar_verici import (
    merge_derivative_decisions,
    run_derivative_decisions,
    split_derivatives_by_confidence,
)
from llm_router import has_claude, has_gemini_enrich, merge_meta
from schemas import ClassifyRequest, Variable
from document_context import effective_research_text
from veri_analisti import gemini_turev_to_derived_entries, run_veri_analisti

logger = logging.getLogger(__name__)

_ROLE_MAP = {
    "gruplandirma": "grouping",
    "grouping": "grouping",
    "sonuc": "outcome",
    "outcome": "outcome",
    "exclude": "exclude",
}


def _merge_python_and_gemini_derivatives(
    python_derived: List[dict],
    gemini_derived: List[dict],
) -> List[dict]:
    """Python kural tabanlı + Gemini türev haritasını birleştir."""
    by_name: Dict[str, dict] = {}
    for d in python_derived:
        by_name[d["name"]] = {**d, "source_layer": "python"}
    for d in gemini_derived:
        name = d["name"]
        if name in by_name:
            existing = by_name[name]
            py_conf = existing.get("confidence")
            gem_conf = d.get("confidence")
            if py_conf == "high" or gem_conf == "high":
                existing["confidence"] = "high"
            existing["source_layer"] = "python+gemini"
            if d.get("gerekce"):
                existing["gerekce"] = d["gerekce"]
        else:
            by_name[name] = d
    return sorted(by_name.values(), key=lambda x: x["name"])


def _apply_binary_rules(entry: dict, df: Optional[pd.DataFrame]) -> dict:
    """Binary türev: unique=2 + kaynak geniş → exclude."""
    if df is None or entry.get("name") not in df.columns:
        return entry
    nuniq = int(df[entry["name"]].dropna().nunique())
    if nuniq == 2:
        entry["kind"] = "binary"
        entry["action"] = "exclude"
        entry["recommended_role"] = None
        entry.setdefault("ai_status", "not_recommended")
    elif entry.get("action") != "exclude":
        entry["action"] = "move_to_grouping"
        entry["recommended_role"] = "grouping"
        entry["kind"] = "categorical"
    return entry


def _build_classify_from_gemini_roles(
    columns: List[str],
    rol_onerileri: List[dict],
) -> Tuple[List[str], List[str], List[str], Dict[str, dict]]:
    """Gemini rol önerilerinden sınıflandırma (Claude yok, Gemini tek başına)."""
    by_col = {str(r.get("degisken") or r.get("name") or ""): r for r in rol_onerileri}
    categorical: List[str] = []
    continuous: List[str] = []
    exclude: List[str] = []
    recommendations: Dict[str, dict] = {}

    for col in columns:
        info = by_col.get(col, {})
        t = str(info.get("type") or "categorical").lower()
        role_raw = str(info.get("rol") or info.get("role") or "gruplandirma").lower()
        role = _ROLE_MAP.get(role_raw, "grouping")
        reason = str(info.get("gerekce") or info.get("reason") or "")

        if t == "exclude" or role == "exclude":
            exclude.append(col)
            ai_status = "not_recommended"
        elif t == "continuous":
            continuous.append(col)
            ai_status = "approved"
        else:
            categorical.append(col)
            ai_status = "approved"

        recommendations[col] = {
            "status": "recommended" if ai_status == "approved" else "skip",
            "role": role,
            "reason": reason,
            "ai_status": ai_status,
        }

    for col in columns:
        if col not in recommendations:
            exclude.append(col)
            recommendations[col] = {
                "status": "optional",
                "role": "grouping",
                "reason": "",
                "ai_status": "review",
            }

    return categorical, continuous, exclude, recommendations


def _annotate_recommendations_with_derivatives(
    recommendations: Dict[str, dict],
    derived_final: List[dict],
    suspicious: List[dict],
) -> None:
    derived_by_name = {d["name"]: d for d in derived_final + suspicious}
    for name, d in derived_by_name.items():
        rec = recommendations.setdefault(name, {
            "status": "optional",
            "role": d.get("recommended_role") or "grouping",
            "reason": d.get("gerekce", ""),
        })
        status = d.get("ai_status")
        if d.get("action") == "exclude":
            rec["ai_status"] = "not_recommended"
            rec["status"] = "skip"
            rec["role"] = "exclude"
            rec["reason"] = rec.get("reason") or f"Kaynak: {d.get('source')} — analiz dışı bırakın"
        elif status == "review":
            rec["ai_status"] = "review"
            rec["status"] = "optional"
        else:
            rec["ai_status"] = "approved"
            if d.get("action") == "move_to_grouping":
                rec["role"] = "grouping"
        rec["source"] = d.get("source")
        rec["confidence"] = d.get("confidence")
        rec["derived"] = True


def run_variable_ai_pipeline(
    req: ClassifyRequest,
    df: Optional[pd.DataFrame] = None,
    variables: Optional[List[Variable]] = None,
) -> dict:
    """
    Dosya yüklendi → Python profil+Spearman → Gemini analist → Claude karar.
    Fallback: Gemini yok → Python kuralları; Claude yok → Gemini rolleri.
    """
    meta: dict = {"llm_calls": 0, "gemini_used": False, "claude_used": False, "fallback": None}
    profile = profile_from_samples(
        req.columns,
        req.samples,
        req.labels,
        req.variable_measure,
    )

    python_derived: List[dict] = []
    if df is not None and variables:
        python_derived = find_derived_variables(df, variables)

    doc_ctx = req.document_context
    research_text = effective_research_text(doc_ctx, req.research_topic or "")

    gemini_out, gem_meta = run_veri_analisti(
        df,
        req.columns,
        req.samples,
        req.labels,
        req.variable_measure,
        research_text,
        variables,
        document_context=doc_ctx,
    )
    meta = merge_meta(meta, gem_meta)
    if gem_meta.get("llm_calls"):
        meta["gemini_used"] = True

    gemini_derived = gemini_turev_to_derived_entries(gemini_out)
    if df is not None:
        all_derived = [
            _apply_binary_rules(d, df)
            for d in _merge_python_and_gemini_derivatives(python_derived, gemini_derived)
        ]
    else:
        all_derived = _merge_python_and_gemini_derivatives(python_derived, gemini_derived)

    if not all_derived and python_derived and not has_gemini_enrich():
        meta["fallback"] = "python_rules_only"
        all_derived = python_derived

    auto_accepted, review_items = split_derivatives_by_confidence(all_derived)
    for d in auto_accepted:
        d["ai_status"] = "approved" if d.get("action") != "exclude" else "not_recommended"
        if d.get("action") == "exclude":
            d["ai_status"] = "not_recommended"

    derivative_decision = {"onaylanan_turevler": [], "reddedilen": [], "gerekce": ""}
    if review_items and (has_claude() or has_gemini_enrich()):
        derivative_decision, decide_meta = run_derivative_decisions(
            review_items,
            gemini_out,
            research_text,
        )
        meta = merge_meta(meta, decide_meta)
        if decide_meta.get("llm_calls"):
            meta["claude_used"] = bool(has_claude())
            if not has_claude():
                meta["fallback"] = "gemini_decides"

    derived_final, suspicious = merge_derivative_decisions(
        auto_accepted, derivative_decision, all_derived,
    )

    # Sınıflandırma: Claude yoksa Gemini rol önerileri; ikisi de yoksa boş (frontend pattern)
    categorical: List[str] = []
    continuous: List[str] = []
    exclude: List[str] = []
    recommendations: Dict[str, dict] = {}
    llm_classify_meta: dict = {}

    if has_claude():
        from ai_services import CLASSIFY_SYSTEM, _parse_llm_json
        from data_profile import profile_json
        from llm_router import claude_decide

        user_msg = (
            f"Sütunları sınıflandır:\n"
            f"Araştırma: {research_text[:600]}\n\n"
            f"Veri profili:\n{profile_json(profile)}\n\n"
            f"Gemini veri analizi:\n{json.dumps(gemini_out, ensure_ascii=False)[:6000]}\n\n"
            f"Türev kararları: onaylı={len(derived_final)}, inceleme={len(suspicious)}"
        )
        try:
            text, decide_meta = claude_decide(CLASSIFY_SYSTEM, str(user_msg)[:14000], max_tokens=1500)
            meta = merge_meta(meta, decide_meta)
            meta["claude_used"] = True
            llm_classify_meta = decide_meta
            parsed = _parse_llm_json(text)
            variables_map = parsed.get("variables", {})
            for col, info in variables_map.items():
                if col not in req.columns:
                    continue
                t = info.get("type", "exclude")
                role = info.get("role", "exclude")
                rec = info.get("recommended", False)
                reason = info.get("reason", "")
                if t == "exclude" or role == "exclude":
                    exclude.append(col)
                elif t == "categorical":
                    categorical.append(col)
                else:
                    continuous.append(col)
                recommendations[col] = {
                    "status": "recommended" if rec else "optional",
                    "role": role,
                    "reason": reason,
                    "ai_status": "approved",
                }
            for col in req.columns:
                if col not in recommendations:
                    exclude.append(col)
                    recommendations[col] = {
                        "status": "skip",
                        "role": "exclude",
                        "reason": "",
                        "ai_status": "review",
                    }
        except Exception as exc:
            logger.warning("Claude classify failed: %s", exc)

    elif has_gemini_enrich() and gemini_out.get("rol_onerileri"):
        meta["fallback"] = meta.get("fallback") or "gemini_classify"
        categorical, continuous, exclude, recommendations = _build_classify_from_gemini_roles(
            req.columns, gemini_out["rol_onerileri"],
        )
    else:
        meta["fallback"] = "manual"
        return {
            "categorical": [],
            "continuous": [],
            "exclude": [],
            "recommendations": {},
            "derived": derived_final + suspicious,
            "derived_approved": derived_final,
            "derived_review": suspicious,
            "scales": gemini_out.get("olcek_gruplari") or [],
            "research_context": gemini_out.get("arastirma_baglami") or {},
            "gemini_analysis": gemini_out,
            "derivative_decision": derivative_decision,
            "llm_meta": meta,
            "data_profile": profile,
            "manual_required": True,
        }

    _annotate_recommendations_with_derivatives(recommendations, derived_final, suspicious)

    return {
        "categorical": categorical,
        "continuous": continuous,
        "exclude": exclude,
        "recommendations": recommendations,
        "derived": derived_final + suspicious,
        "derived_approved": derived_final,
        "derived_review": suspicious,
        "scales": gemini_out.get("olcek_gruplari") or [],
        "research_context": gemini_out.get("arastirma_baglami") or {},
        "gemini_analysis": gemini_out,
        "derivative_decision": derivative_decision,
        "llm_meta": meta,
        "data_profile": profile,
        "manual_required": False,
    }
