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
from scale_registry import get_cutoff, get_reverse_items, resolve_scale_id, validate_turkish

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


_REVERSE_SUFFIX = re.compile(r"(?:_reversed|_recoded|_inverted|_ters|_rev|_rc|_inv|_t|_r)$", re.I)
_ITEM_NUM = re.compile(r"_(\d+)(?:_|$)")


def extract_item_number(col: str) -> Optional[int]:
    m = _ITEM_NUM.search((col or "").lower())
    return int(m.group(1)) if m else None


def infer_reverse_from_items(items: List[str]) -> List[int]:
    """Sütun adlarından ters madde numaralarını çıkar."""
    nums: List[int] = []
    for col in items or []:
        if _REVERSE_SUFFIX.search(col):
            n = extract_item_number(col)
            if n is not None:
                nums.append(n)
    return sorted(set(nums))


def evaluate_reverse_items(scale: dict) -> dict:
    """
    Gemini ters madde önerisini registry ile karşılaştır.
    Uyuşursa reverse_confidence=confirmed; uyuşmazsa conflict.
    """
    out = dict(scale)
    sid = out.get("id") or out.get("registry_id") or resolve_scale_id(out.get("name", ""))
    if not sid:
        return out

    registry_rev = get_reverse_items(sid)
    gemini_rev = out.get("gemini_reverse_items") or out.get("reverse_items")
    if isinstance(gemini_rev, list) and not gemini_rev:
        gemini_rev = infer_reverse_from_items(out.get("items") or [])

    if registry_rev is None:
        out["reverse_confidence"] = "unknown"
        return out

    if gemini_rev is None:
        out["reverse_items"] = registry_rev
        out["reverse_confidence"] = "registry"
        return out

    reg_set = set(registry_rev)
    gem_set = set()
    for x in gemini_rev:
        if x is None:
            continue
        try:
            gem_set.add(int(x))
        except (ValueError, TypeError):
            pass  # string gelirse sessizce atla

    if reg_set == gem_set:
        out["reverse_items"] = list(reg_set)
        out["reverse_confidence"] = "confirmed"
    else:
        out["reverse_conflict"] = {
            "registry": sorted(reg_set),
            "gemini": sorted(gem_set),
            "requires_user": True,
        }
        out["reverse_confidence"] = "conflict"
    return out


def apply_reverse_item_decisions(scales: List[dict]) -> List[dict]:
    return [evaluate_reverse_items(s) for s in scales]


def build_cutoff_sentence(scale_name: str, score: float, cutoff: dict) -> str:
    """Kesim noktası yorum cümlesi."""
    value = cutoff.get("value")
    interp = cutoff.get("interpretation") or ""
    if value is None:
        return ""
    name = scale_name or "Ölçek"
    try:
        val_f = float(value)
        if score >= val_f:
            relation = "üzerinde" if "≥" in interp or ">=" in interp else "üzerinde veya eşit"
        else:
            relation = "altında"
        return (
            f"{name} toplam puanı {score:.1f} olup kesim noktası olan "
            f"{val_f:g}'in {relation}dir."
        )
    except (TypeError, ValueError):
        return ""


def enrich_cronbach_bulgu(
    result: dict,
    text: str,
    all_results: Optional[List[dict]] = None,
) -> str:
    """Cronbach bulgusuna kesim noktası ve Türkçe geçerlilik notu ekle."""
    if not text:
        return text

    scale_name = result.get("scale_name") or result.get("name")
    sid = result.get("scale_id") or resolve_scale_id(scale_name or "")

    scales = result.get("merged_scales") or []
    if not sid and len(scales) == 1:
        scale_name = scales[0].get("name", scale_name)
        sid = resolve_scale_id(scale_name or "")

    if sid:
        cutoff = get_cutoff(sid)
        if cutoff:
            mean_score = result.get("mean_score") or result.get("total_mean")
            if mean_score is None and all_results:
                mean_score = _find_descriptive_mean(scale_name, all_results)
            if mean_score is not None:
                sentence = build_cutoff_sentence(scale_name or sid, float(mean_score), cutoff)
                if sentence and sentence not in text:
                    text = text.rstrip(".") + ". " + sentence
        if not validate_turkish(sid):
            note = "Bu ölçeğin Türkçe geçerlilik çalışması bulunamamıştır."
            if note not in text:
                text = text.rstrip(".") + ". " + note

    for sub in scales:
        sub_sid = resolve_scale_id(sub.get("name", ""))
        if sub_sid and not validate_turkish(sub_sid):
            note = "Bu ölçeğin Türkçe geçerlilik çalışması bulunamamıştır."
            if note not in text:
                text = text.rstrip(".") + ". " + note
                break

    return text


def _find_descriptive_mean(scale_name: str, all_results: List[dict]) -> Optional[float]:
    if not scale_name:
        return None
    key = scale_name.lower()
    for r in all_results:
        if r.get("type") != "descriptive":
            continue
        for row in r.get("rows") or []:
            label = str(row.get("label") or row.get("variable") or "").lower()
            if key in label or label in key:
                for field in ("mean", "Mean", "ortalama"):
                    if row.get(field) is not None:
                        try:
                            return float(row[field])
                        except (TypeError, ValueError):
                            pass
    return None


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
