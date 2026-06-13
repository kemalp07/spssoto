"""Gemini katmanı — proaktif veri analisti (tüm değişkenleri birlikte görür)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from data_profile import (
    build_spearman_summary,
    profile_from_dataframe,
    profile_from_samples,
)
from data_cleaning import apply_scale_item_resolution
from llm_router import (
    _parse_json_object,
    gemini_json_task,
    has_gemini_enrich,
    merge_meta,
)
from scale_registry import (
    compact_registry_hints,
    get_reverse_items,
    get_scale_info,
    match_scale,
    resolve_scale_id,
)
from schemas import Variable

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 1500

VERI_ANALISTI_SYSTEM = """Sen deneyimli bir tez veri analistisin. Tüm değişkenleri BİRLİKTE değerlendir.
Ham istatistik hesaplama — sadece verilen profili oku ve yapılandırılmış JSON üret.

SADECE JSON döndür:
{
  "turev_haritasi": [
    {
      "kaynak": "sürekli_kaynak_adı",
      "turev": "türev_değişken_adı",
      "confidence": "high|medium|low",
      "gerekce": "kısa Türkçe"
    }
  ],
  "rol_onerileri": [
    {
      "degisken": "sütun_adı",
      "type": "categorical|continuous|exclude",
      "rol": "gruplandirma|sonuc|exclude",
      "gerekce": "kısa Türkçe"
    }
  ],
  "olcek_gruplari": [
    {"olcek": "OYS", "maddeler": ["oys_1", "oys_2"]}
  ],
  "arastirma_baglami": {
    "konu": "araştırma konusu",
    "populasyon": "hedef popülasyon"
  }
}

Kurallar:
- turev_haritasi: isim kökü benzerliği + tip farkı (sürekli kaynak, kategorik türev) veya yüksek Spearman
- confidence high: hem isim hem korelasyon ipucu; medium: biri; low: zayıf
- Binary türev (2 kategori) → rol exclude, gerekçede kaynak değişkeni kullanın de
- Kategorik türev (≤8 kategori) → rol gruplandirma
- Ölçek maddeleri (_1, _2 …) olcek_gruplari'na; maddeler exclude
- Madde kolonları rol_onerileri'nde exclude"""


def build_compact_input(
    df: Optional[pd.DataFrame],
    columns: List[str],
    samples: Dict[str, List[Any]],
    labels: Optional[Dict[str, str]] = None,
    variable_measure: Optional[Dict[str, str]] = None,
    research_topic: str = "",
    variables: Optional[List[Variable]] = None,
    document_context: Optional[dict] = None,
) -> dict:
    """Gemini girdisi — ad, tip, unique, örnek değerler, Spearman özeti."""
    labels = labels or {}
    variable_measure = variable_measure or {}
    cols: List[dict] = []

    for col in columns:
        if df is not None and col in df.columns:
            series = df[col]
            vals = series.dropna().head(8).tolist()
            nuniq = int(series.dropna().nunique())
        else:
            vals = (samples.get(col) or [])[:8]
            series = pd.Series(vals)
            nuniq = len(set(str(v) for v in vals if v is not None and str(v) != ""))

        numeric = pd.to_numeric(series, errors="coerce")
        numeric_ratio = float(numeric.notna().sum()) / max(len(series), 1)
        type_hint = "continuous" if numeric_ratio > 0.8 and nuniq > 8 else "categorical"

        entry: dict = {
            "ad": col,
            "etiket": labels.get(col, col),
            "spss_measure": variable_measure.get(col),
            "type_hint": type_hint,
            "unique_sayisi": nuniq,
            "ornek_degerler": [str(v) for v in vals[:6]],
        }
        cols.append(entry)

    spearman: List[dict] = []
    if df is not None:
        spearman = build_spearman_summary(df, columns, min_r=0.50, max_pairs=40)

    payload: dict = {
        "arastirma_metni": (research_topic or "")[:600],
        "degisken_sayisi": len(cols),
        "degiskenler": cols,
        "spearman_yuksek": spearman,
    }
    if df is not None and variables:
        profile = profile_from_dataframe(df, variables)
        payload["gruplandirma"] = profile.get("grouping_vars", [])[:12]
        payload["sonuc"] = profile.get("outcome_vars", [])[:12]
    if document_context:
        from document_context import compact_document_context_for_gemini
        doc_block = compact_document_context_for_gemini(document_context)
        if doc_block:
            payload["belge_baglami"] = doc_block
    return payload


def _empty_analysis() -> dict:
    return {
        "turev_haritasi": [],
        "rol_onerileri": [],
        "olcek_gruplari": [],
        "arastirma_baglami": {},
    }


def run_veri_analisti(
    df: Optional[pd.DataFrame],
    columns: List[str],
    samples: Dict[str, List[Any]],
    labels: Optional[Dict[str, str]] = None,
    variable_measure: Optional[Dict[str, str]] = None,
    research_topic: str = "",
    variables: Optional[List[Variable]] = None,
    document_context: Optional[dict] = None,
) -> Tuple[dict, dict]:
    """Gemini: türev haritası, rol önerileri, ölçek grupları, araştırma bağlamı."""
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not has_gemini_enrich():
        return _empty_analysis(), meta

    compact = build_compact_input(
        df, columns, samples, labels, variable_measure, research_topic, variables,
        document_context=document_context,
    )
    user = (
        "Tüm değişkenleri birlikte analiz et. Ham veri yok — sadece profil.\n\n"
        + json.dumps(compact, ensure_ascii=False)[:12000]
    )
    try:
        raw, gem_meta = gemini_json_task(VERI_ANALISTI_SYSTEM, user, MAX_OUTPUT_TOKENS)
        meta = merge_meta(meta, gem_meta)
        parsed = _parse_json_object(raw)
        if not parsed:
            return _empty_analysis(), meta
        return {
            "turev_haritasi": list(parsed.get("turev_haritasi") or []),
            "rol_onerileri": list(parsed.get("rol_onerileri") or []),
            "olcek_gruplari": list(parsed.get("olcek_gruplari") or []),
            "arastirma_baglami": dict(parsed.get("arastirma_baglami") or {}),
        }, meta
    except Exception as exc:
        logger.warning("Veri analisti (Gemini) failed: %s", exc)
        return _empty_analysis(), meta


DETECT_SCALES_SYSTEM = """Sen akademik ölçek analizi uzmanısın. Verilen madde gruplarını ölçeklere dönüştür.

Registry eşleşmeleri önceden hesaplandı — bunları doğrula veya reddet; registry'de olmayan ölçekleri ekle.
_ters veya _T ile biten madde varsa ters versiyonu kullan, orijinalini listeye ekleme.

SADECE JSON döndür:
{
  "scales": [
    {
      "name": "OYŞTÖ",
      "id": "oysto",
      "items": ["oys_1", "oys_2"],
      "reverse_items": [4],
      "registry_confirmed": true
    }
  ]
}

registry_confirmed: registry ipucuyla uyumluysa true, değilse false veya alanı atla."""


def _registry_match_to_scale(match: dict, min_confidence: str = "high") -> Optional[dict]:
    if _CONF_RANK.get(match.get("confidence"), 0) < _CONF_RANK.get(min_confidence, 2):
        return None
    scale = match["scale"]
    cols = match.get("matched_cols") or []
    if len(cols) < 2:
        return None
    resolved = apply_scale_item_resolution(cols)
    sid = scale.get("id", "")
    return {
        "name": (scale.get("names") or [sid])[0],
        "id": sid,
        "items": resolved["items"],
        "cronbach_items": resolved["cronbach_items"],
        "item_count": resolved["item_count"],
        "registry_id": sid,
        "registry_confidence": match.get("confidence", "high"),
        "source": "registry",
        "reverse_items": get_reverse_items(sid),
        "scale_range": (get_scale_info(sid) or {}).get("scale_range") or [0, 4],
    }


_CONF_RANK = {"high": 2, "medium": 1, "low": 0}


def scales_from_registry_matches(
    registry_matches: List[dict],
    min_confidence: str = "high",
) -> List[dict]:
    """Registry eşleşmelerini detect-scales çıktı formatına çevir."""
    scales: List[dict] = []
    seen_ids: set = set()
    for m in registry_matches:
        sid = m["scale"].get("id")
        if sid in seen_ids:
            continue
        built = _registry_match_to_scale(m, min_confidence=min_confidence)
        if built:
            scales.append(built)
            seen_ids.add(sid)
    return scales


def _normalize_gemini_scales(parsed: dict, registry_matches: List[dict]) -> List[dict]:
    """Gemini ölçek listesini standart formata getir."""
    registry_ids = {m["scale"]["id"] for m in registry_matches}
    scales: List[dict] = []
    for raw in parsed.get("scales") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        items = list(raw.get("items") or [])
        if len(items) < 2 and not name:
            continue
        sid = str(raw.get("id") or resolve_scale_id(name) or "").strip() or None
        resolved = apply_scale_item_resolution(items)
        source = "registry" if sid and sid in registry_ids and raw.get("registry_confirmed") else "gemini"
        if sid and sid in registry_ids:
            source = "registry+gemini" if raw.get("registry_confirmed") else "gemini"
        entry = {
            "name": name or sid or "Ölçek",
            "id": sid,
            "items": resolved["items"],
            "cronbach_items": resolved["cronbach_items"],
            "item_count": resolved["item_count"],
            "registry_id": sid if sid in registry_ids else None,
            "registry_confidence": next(
                (m["confidence"] for m in registry_matches if m["scale"]["id"] == sid),
                None,
            ) if sid else None,
            "source": source,
            "reverse_items": raw.get("reverse_items"),
            "gemini_reverse_items": raw.get("reverse_items"),
        }
        scales.append(entry)
    return scales


def run_scale_detection(
    col_names: List[str],
    col_labels: Optional[Dict[str, str]] = None,
    prefix_groups: Optional[Dict[str, List[str]]] = None,
    document_context: Optional[dict] = None,
) -> Tuple[List[dict], List[dict], dict]:
    """
    Registry eşleştirme + (varsa) Gemini ölçek tespiti.
    Döndürür: (scales, registry_matches, meta)
    """
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    registry_matches = match_scale(col_names, col_labels)
    high_confidence = [m for m in registry_matches if m.get("confidence") == "high"]
    compact_hints = compact_registry_hints(high_confidence)

    if not has_gemini_enrich():
        return scales_from_registry_matches(registry_matches), registry_matches, meta

    hint_block = ""
    if compact_hints:
        hint_block = (
            "\n\nRegistry eşleşmeleri (doğrula): "
            + json.dumps(compact_hints, ensure_ascii=False)
        )

    from document_context import anket_section_hints

    anket_block = ""
    hints = anket_section_hints(document_context)
    if hints:
        anket_block = (
            "\n\nAnket formu bölüm başlıkları:\n"
            + json.dumps(hints, ensure_ascii=False)
        )

    user = (
        "Madde prefix grupları:\n"
        + json.dumps(prefix_groups or {}, ensure_ascii=False)
        + "\n\nSütun adları:\n"
        + json.dumps(col_names[:200], ensure_ascii=False)
        + hint_block
        + anket_block
    )
    try:
        raw, gem_meta = gemini_json_task(DETECT_SCALES_SYSTEM, user, MAX_OUTPUT_TOKENS)
        meta = merge_meta(meta, gem_meta)
        parsed = _parse_json_object(raw)
        if parsed and parsed.get("scales"):
            return _normalize_gemini_scales(parsed, registry_matches), registry_matches, meta
    except Exception as exc:
        logger.warning("Ölçek tespiti (Gemini) failed: %s", exc)

    return scales_from_registry_matches(registry_matches), registry_matches, meta


def gemini_turev_to_derived_entries(gemini: dict) -> List[dict]:
    """Gemini turev_haritasi → find_derived_variables ile uyumlu kayıt listesi."""
    entries: List[dict] = []
    for item in gemini.get("turev_haritasi") or []:
        if not isinstance(item, dict):
            continue
        turev = str(item.get("turev") or item.get("name") or "").strip()
        kaynak = str(item.get("kaynak") or item.get("source") or "").strip()
        if not turev or not kaynak:
            continue
        conf = str(item.get("confidence") or "medium").lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        entries.append({
            "name": turev,
            "source": kaynak,
            "confidence": conf,
            "kind": "binary" if "binary" in turev.lower() else "categorical",
            "action": "exclude" if "binary" in turev.lower() else "move_to_grouping",
            "recommended_role": None if "binary" in turev.lower() else "grouping",
            "source_layer": "gemini",
            "gerekce": str(item.get("gerekce") or ""),
        })
    return entries
