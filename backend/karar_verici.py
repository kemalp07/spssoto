"""Claude katmanı — stratejik karar verici (türev onayı, hipotez eşleşmesi, plan uyarıları)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from llm_router import (
    _parse_json_object,
    claude_decide,
    gemini_json_task,
    has_claude,
    has_gemini_enrich,
    merge_meta,
)

logger = logging.getLogger(__name__)

MAX_DECIDE_TOKENS = 1200

KARAR_TUREV_SYSTEM = """Sen tez istatistik danışmanısın. Türev değişken tespitlerini değerlendir.

HIGH confidence türevler zaten otomatik kabul edildi — onlara dokunma.
Sadece medium ve low confidence olanları incele.

SADECE JSON döndür:
{
  "onaylanan_turevler": [
    {"name": "türev_ad", "source": "kaynak_ad", "action": "move_to_grouping|exclude", "confidence": "medium|low"}
  ],
  "reddedilen": [
    {"name": "türev_ad", "gerekce": "kısa Türkçe"}
  ],
  "gerekce": "genel değerlendirme, 1-2 cümle"
}

Binary türev (2 kategori, kaynak çok değerli) → action exclude öner.
Kategorik türev → move_to_grouping."""

KARAR_HIPOTEZ_SYSTEM = """Sen tez istatistik danışmanısın. Araştırma metnini test adaylarıyla eşle.

SADECE JSON döndür:
{
  "hypotheses": [
    {
      "id": "H1",
      "label": "soru metni",
      "type": "fark|iliski|yordama",
      "candidate_ids": ["test_aday_id"],
      "var_hints": ["değişken ipucu"]
    }
  ],
  "unmatched": ["eşleşmeyen soru metni"]
}

Her hipoteze en az bir geçerli candidate_id. Aynı candidate_id iki hipoteze atanmasın.
Çekirdek tablolar (descriptive, frequency, cronbach) hipoteze bağlanmasın — otomatik eklenir."""

KARAR_PLAN_SYSTEM = """Sen tez istatistik danışmanısın. Seçilen testlerde mantıksal tutarsızlık var mı?

SADECE JSON döndür:
{
  "uyarilar": ["H1 ilişki hipotezi ama korelasyon seçilmemiş", ...]
}"""


def _decide_json(system: str, user: str, max_tokens: int = MAX_DECIDE_TOKENS) -> Tuple[dict, dict]:
    """Claude karar; yoksa Gemini fallback."""
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if has_claude():
        try:
            raw, decide_meta = claude_decide(system, user, max_tokens=max_tokens)
            meta = merge_meta(meta, decide_meta)
            return _parse_json_object(raw), meta
        except RuntimeError:
            pass

    if has_gemini_enrich():
        raw, gem_meta = gemini_json_task(system, user, max_tokens)
        meta = merge_meta(meta, gem_meta)
        return _parse_json_object(raw), meta

    return {}, meta


def split_derivatives_by_confidence(derived_list: List[dict]) -> Tuple[List[dict], List[dict]]:
    """High → otomatik; medium/low → Claude incelemesi."""
    auto: List[dict] = []
    review: List[dict] = []
    for d in derived_list:
        conf = str(d.get("confidence") or "medium").lower()
        if conf == "high":
            auto.append(d)
        else:
            review.append(d)
    return auto, review


def run_derivative_decisions(
    review_items: List[dict],
    gemini_context: dict,
    research_text: str = "",
) -> Tuple[dict, dict]:
    """Medium/low türevleri Claude (veya Gemini fallback) ile değerlendir."""
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not review_items:
        return {"onaylanan_turevler": [], "reddedilen": [], "gerekce": ""}, meta

    user = (
        f"Araştırma: {(research_text or '')[:800]}\n\n"
        f"Gemini bağlamı:\n{json.dumps(gemini_context, ensure_ascii=False)[:4000]}\n\n"
        f"İncelenecek türevler (medium/low):\n"
        f"{json.dumps(review_items, ensure_ascii=False)[:4000]}"
    )
    parsed, decide_meta = _decide_json(KARAR_TUREV_SYSTEM, user)
    meta = merge_meta(meta, decide_meta)
    return {
        "onaylanan_turevler": list(parsed.get("onaylanan_turevler") or []),
        "reddedilen": list(parsed.get("reddedilen") or []),
        "gerekce": str(parsed.get("gerekce") or ""),
    }, meta


def merge_derivative_decisions(
    auto_accepted: List[dict],
    decision: dict,
    all_derived: List[dict],
) -> Tuple[List[dict], List[dict]]:
    """Otomatik + Claude onaylı türevler; reddedilenler çıkarılır."""
    rejected = {str(r.get("name") or "") for r in (decision.get("reddedilen") or [])}
    approved_names = {str(d.get("name") or "") for d in auto_accepted}
    final: List[dict] = [d for d in auto_accepted if d.get("name")]

    for item in decision.get("onaylanan_turevler") or []:
        name = str(item.get("name") or "").strip()
        if not name or name in rejected:
            continue
        base = next((d for d in all_derived if d.get("name") == name), {})
        merged = dict(base)
        merged.update({
            "name": name,
            "source": item.get("source") or base.get("source"),
            "action": item.get("action") or base.get("action"),
            "confidence": item.get("confidence") or base.get("confidence", "medium"),
            "ai_status": "approved",
        })
        final.append(merged)
        approved_names.add(name)

    suspicious: List[dict] = []
    for d in all_derived:
        name = str(d.get("name") or "")
        if name in approved_names or name in rejected:
            continue
        if str(d.get("confidence") or "").lower() != "high":
            item = dict(d)
            item["ai_status"] = "review"
            suspicious.append(item)

    for d in final:
        d.setdefault("ai_status", "approved")

    return final, suspicious


def run_hypothesis_matching(
    research_text: str,
    candidates_compact: List[dict],
    gemini_context: dict,
    labels: Optional[Dict[str, str]] = None,
) -> Tuple[dict, dict]:
    """Hipotez-test eşleşmesi — Claude karar, Gemini fallback."""
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    text = (research_text or "").strip()
    if not text or not candidates_compact:
        return {"hypotheses": [], "unmatched": []}, meta

    user = (
        f"Araştırma metni:\n{text[:2000]}\n\n"
        f"Etiketler: {json.dumps(labels or {}, ensure_ascii=False)[:2000]}\n\n"
        f"Gemini veri analizi:\n{json.dumps(gemini_context, ensure_ascii=False)[:4000]}\n\n"
        f"Test adayları:\n{json.dumps(candidates_compact, ensure_ascii=False)[:6000]}"
    )
    parsed, decide_meta = _decide_json(KARAR_HIPOTEZ_SYSTEM, user)
    meta = merge_meta(meta, decide_meta)
    return {
        "hypotheses": list(parsed.get("hypotheses") or []),
        "unmatched": list(parsed.get("unmatched") or []),
    }, meta


def run_plan_evaluation(
    hypotheses: List[dict],
    selected_candidate_ids: List[str],
    candidates_by_id: Dict[str, dict],
) -> Tuple[dict, dict]:
    """Plan mantıksal tutarsızlık kontrolü."""
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not hypotheses:
        return {"uyarilar": []}, meta

    compact = []
    for h in hypotheses:
        cids = h.get("candidate_ids") or []
        tests = [
            candidates_by_id.get(str(cid), {}).get("test", "?")
            for cid in cids
        ]
        compact.append({
            "id": h.get("id"),
            "type": h.get("type"),
            "label": h.get("label"),
            "tests": tests,
            "candidate_ids": cids,
        })

    user = (
        f"Hipotezler:\n{json.dumps(compact, ensure_ascii=False)[:4000]}\n\n"
        f"Seçili testler:\n{json.dumps(selected_candidate_ids[:40], ensure_ascii=False)}"
    )
    parsed, decide_meta = _decide_json(KARAR_PLAN_SYSTEM, user, max_tokens=600)
    meta = merge_meta(meta, decide_meta)
    return {"uyarilar": list(parsed.get("uyarilar") or [])}, meta
