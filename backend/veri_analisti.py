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
from llm_router import (
    _parse_json_object,
    gemini_json_task,
    has_gemini_enrich,
    merge_meta,
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
