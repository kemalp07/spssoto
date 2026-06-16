"""
Gemini 2.5 Flash ile anket + etik kurul → analiz planı önerisi.
Sadece PLANLAMA yapar. Hesaplama, test seçimi, normallik kararı vermez.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List

from data_cleaning import detect_scale_groups
from document_parser import anket_text_from_parse, etik_text_from_parse

_HYP_LINE = re.compile(
    r"(?:H|AS|HS|AH)\s*\d+\s*[:.)]\s*(.+?)(?=\n|$)",
    re.IGNORECASE,
)

_TOPLAM_RE = re.compile(r"_(TOPLAM|TOTAL|PUAN|SCORE|SUM)$", re.I)
_OUTCOME_HINT = re.compile(r"(toplam|total|_score|_puan|_sum)", re.I)
_DBF_RE = re.compile(r"^dbf_", re.I)
_GROUPING_NAMES = frozenset(
    {"bolum", "cinsiyet", "gender", "department", "dept", "sinif", "yas_grubu"},
)
_CONTINUOUS_NOT_GROUPING = re.compile(
    r"^(dbf_)?(boy|kilo|yas|weight|height|bmi|vki|age)$",
    re.I,
)
_MAX_GEREKCE = 6

ONERI_SYSTEM = """Sen akademik tez analiz planlama asistanısın. Türkçe yanıt ver.

Sana şunlar verilecek:
1. Veri seti sütun adları
2. Anket formu içeriği
3. Etik kurul belgesi

GÖREVIN:
- Etik kurulda açıkça bahsedilen karşılaştırmaları tespit et
- Anket formundaki ölçekleri tespit et
- Gruplama değişkenlerini belirle (sadece kategorik olanlar — boy, kilo, yaş sayısal değerleri gruplama DEĞİLDİR)
- Outcome değişkenlerini belirle (_TOPLAM suffix'li sütunlar)

KRİTİK KURALLAR:
- Sadece ETİK KURULDA bahsedilen analizleri öner
- Her analiz için ETİK KURULDAN veya ANKETTEN somut bir gerekçe yaz
- Boy, kilo, yaş gibi sürekli değişkenleri gruplama_degiskenleri'ne EKLEME
- En fazla 6 karşılaştırma öner — en önemli olanları seç
- ozet: 2-3 cümle, net ve akademik

SADECE JSON döndür, başka hiçbir şey yazma:
{
  "ozet": "...",
  "gerekceler": [
    {
      "analiz": "Bölüme göre OYŞTÖ karşılaştırması",
      "neden": "Etik kurulda 'bölümler arası online yemek siparişi tutumu karşılaştırılacak' ifadesi geçiyor",
      "degiskenler": ["bolum", "OYS_TOPLAM"],
      "tip": "karsilastirma"
    }
  ],
  "olcekler": [
    {
      "ad": "OYŞTÖ",
      "prefix": "OYS",
      "neden": "Anket formunda 15 maddelik OYŞTÖ ölçeği tespit edildi"
    }
  ],
  "gruplama_degiskenleri": ["bolum", "dbf_cinsiyet"],
  "outcome_degiskenleri": ["OYS_TOPLAM", "NEQ_TOPLAM", "SBITO_TOPLAM"]
}
"""


async def haiku_incele_plan(oneri: dict) -> tuple[str, dict]:
    """Claude Haiku ile planı arka planda değerlendir — kullanıcıya gösterilmez."""
    from llm_router import claude_decide, has_claude

    meta: dict = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not has_claude():
        return "", meta

    system = """Sen istatistik metodoloji uzmanısın.
Verilen analiz planı önerisini iç denetim için gözden geçir.
2-3 cümle kısa not yaz: mantık hatası, eksik analiz veya tutarsızlık var mı?
Plan genel olarak uygunsa "Plan uygun" de."""

    user = f"Analiz planı: {json.dumps(oneri, ensure_ascii=False)[:2000]}"
    result, cmeta = claude_decide(system, user, max_tokens=300)
    return (result or "").strip(), cmeta


def _infer_grouping_columns(columns: List[str]) -> List[str]:
    out: List[str] = []
    for col in columns:
        if _DBF_RE.match(col) or col.lower() in _GROUPING_NAMES:
            out.append(col)
    return out


def _infer_outcome_columns(columns: List[str]) -> List[str]:
    out: List[str] = []
    for col in columns:
        if _TOPLAM_RE.search(col) or _OUTCOME_HINT.search(col.lower()):
            out.append(col)
    return out


def _build_fallback_analiz(
    columns: List[str],
    anket_text: str,
    etik_text: str,
    gemini_failed: bool,
) -> str:
    parts: List[str] = []
    if gemini_failed:
        parts.append("Gemini plan üretemedi.")
    elif not columns:
        parts.append("Veri seti sütunları henüz hazır değil.")
    if (anket_text or "").strip() or (etik_text or "").strip():
        parts.append("Yüklediğiniz anket ve etik kurul belgeleri sonraki adımlarda kullanılacak.")
    if columns:
        parts.append(f"Veri setinde {len(columns)} sütun var.")
    parts.append("Değişkenler adımında sınıflandırmayla devam edebilirsiniz.")
    return " ".join(parts)


def _normalize_olcekler(olcekler: List[dict]) -> List[dict]:
    out: List[dict] = []
    for item in olcekler or []:
        row = dict(item)
        pfx = row.get("prefix") or row.get("maddeler_prefix")
        if pfx:
            row["prefix"] = pfx
            row["maddeler_prefix"] = pfx
        out.append(row)
    return out


def _filter_grouping(columns: List[str]) -> List[str]:
    return [
        c for c in columns
        if not _CONTINUOUS_NOT_GROUPING.match(c)
    ]


def _infer_olcekler(columns: List[str]) -> List[dict]:
    groups = detect_scale_groups(columns)
    olcekler: List[dict] = []
    for prefix, items in groups.items():
        if len(items) < 3:
            continue
        ad = prefix.upper()
        olcekler.append({
            "ad": ad,
            "prefix": ad,
            "maddeler_prefix": ad,
            "neden": f"Sütun adlarından {len(items)} madde tespit edildi",
        })
    return olcekler


def _build_gerekceler(
    grouping: List[str],
    outcomes: List[str],
    etik_text: str,
) -> List[dict]:
    if not grouping or not outcomes:
        return []
    gerekceler: List[dict] = []
    etik_hint = "etik kurul" if (etik_text or "").strip() else "sütun adları"
    for g in grouping[:3]:
        for o in outcomes[:4]:
            gerekceler.append({
                "analiz": f"{g} gruplarına göre {o} karşılaştırması",
                "neden": f"{etik_hint} ve veri seti yapısına göre önerildi",
                "degiskenler": [g, o],
                "tip": "karsilastirma",
            })
    return gerekceler[:_MAX_GEREKCE]


def _enrich_oneri(
    oneri: dict,
    columns: List[str],
    etik_text: str,
    anket_text: str = "",
    gemini_failed: bool = False,
) -> dict:
    """Gemini boş alan döndürdüyse sütun adlarından doldur."""
    out = dict(oneri)
    grouping = list(out.get("gruplama_degiskenleri") or [])
    outcomes = list(out.get("outcome_degiskenleri") or [])
    olcekler = list(out.get("olcekler") or [])
    gerekceler = list(out.get("gerekceler") or [])

    if not grouping:
        grouping = _filter_grouping(_infer_grouping_columns(columns))
        out["gruplama_degiskenleri"] = grouping
    else:
        out["gruplama_degiskenleri"] = _filter_grouping(grouping)
        grouping = out["gruplama_degiskenleri"]
    if not outcomes:
        outcomes = _infer_outcome_columns(columns)
        out["outcome_degiskenleri"] = outcomes
    if not olcekler:
        out["olcekler"] = _infer_olcekler(columns)
    else:
        out["olcekler"] = _normalize_olcekler(olcekler)
    if not gerekceler and grouping and outcomes:
        out["gerekceler"] = _build_gerekceler(grouping, outcomes, etik_text)
    elif gerekceler:
        out["gerekceler"] = gerekceler[:_MAX_GEREKCE]

    if not (out.get("analiz") or "").strip() and (out.get("ozet") or "").strip():
        out["analiz"] = out["ozet"]
    if not (out.get("ozet") or "").strip():
        parts = []
        if out.get("olcekler"):
            names = ", ".join(o.get("ad", "") for o in out["olcekler"][:4])
            parts.append(f"Tespit edilen ölçekler: {names}.")
        if grouping:
            parts.append(f"Gruplama: {', '.join(grouping[:5])}.")
        if outcomes:
            parts.append(f"Bağımlı değişkenler: {', '.join(outcomes[:5])}.")
        out["ozet"] = " ".join(parts) or _build_fallback_analiz(
            columns, anket_text, etik_text, gemini_failed,
        )
        if not (out.get("analiz") or "").strip():
            out["analiz"] = out["ozet"]
    return out


def _fallback_oneri(
    columns: List[str],
    etik_text: str = "",
    anket_text: str = "",
    gemini_failed: bool = True,
) -> dict:
    base = {
        "ozet": "",
        "gerekceler": [],
        "olcekler": [],
        "gruplama_degiskenleri": [],
        "outcome_degiskenleri": [],
        "columns_seen": columns[:20],
    }
    return _enrich_oneri(base, columns, etik_text, anket_text, gemini_failed)


def _resolve_belge_texts(
    anket_text: str,
    etik_text: str,
    document_context: dict | None,
) -> tuple[str, str]:
    ctx = document_context or {}
    anket = ctx.get("anket") or {}
    etik = ctx.get("etik_kurul") or {}

    resolved_anket = (anket_text or "").strip()
    resolved_etik = (etik_text or "").strip()

    if anket:
        from_parse = anket_text_from_parse(anket)
        if len(from_parse) > len(resolved_anket):
            resolved_anket = from_parse
    if etik:
        from_parse = etik_text_from_parse(etik)
        if len(from_parse) > len(resolved_etik):
            resolved_etik = from_parse

    return resolved_anket, resolved_etik


def _gemini_response_useful(parsed: dict) -> bool:
    if not parsed:
        return False
    if len((parsed.get("ozet") or "").strip()) > 30:
        return True
    if (parsed.get("gerekceler") or []):
        return True
    return not _oneri_is_sparse(parsed)


def _plan_from_belgeler(
    anket_text: str,
    etik_text: str,
    columns: List[str],
) -> dict:
    """Gemini yanıt vermezse belge metninden makul plan çıkar."""
    grouping = _infer_grouping_columns(columns)
    outcomes = _infer_outcome_columns(columns)
    olcekler = _infer_olcekler(columns)
    hyps = [h.strip() for h in _HYP_LINE.findall(etik_text or "") if h.strip()]

    gerekceler: List[dict] = []
    for hyp in hyps[:6]:
        vars_ = []
        if grouping:
            vars_.append(grouping[0])
        vars_.extend(outcomes[:2])
        gerekceler.append({
            "analiz": hyp[:200],
            "neden": "Etik kurul belgesinden",
            "degiskenler": vars_,
            "tip": "karsilastirma",
        })
    if not gerekceler:
        gerekceler = _build_gerekceler(grouping, outcomes, etik_text)

    analiz_parts: List[str] = []
    if etik_text.strip():
        analiz_parts.append(
            f"Etik kurul belgesi okundu ({len(etik_text)} karakter"
            + (f", {len(hyps)} hipotez/soru" if hyps else "")
            + ").",
        )
    if anket_text.strip():
        analiz_parts.append(f"Anket formu okundu ({len(anket_text)} karakter).")
    if olcekler:
        analiz_parts.append(
            "Tespit edilen ölçekler: "
            + ", ".join(o.get("ad", "") for o in olcekler[:6])
            + ".",
        )
    if grouping:
        analiz_parts.append(f"Gruplama değişkenleri: {', '.join(grouping[:5])}.")
    if outcomes:
        analiz_parts.append(f"Bağımlı değişkenler: {', '.join(outcomes[:5])}.")
    if not analiz_parts:
        analiz_parts.append("Yüklenen belgeler ve sütun adları planlamaya dahil edildi.")

    analiz = " ".join(analiz_parts)
    return {
        "ozet": analiz[:400],
        "analiz": analiz,
        "gerekceler": gerekceler,
        "olcekler": olcekler,
        "gruplama_degiskenleri": grouping,
        "outcome_degiskenleri": outcomes,
    }


def _oneri_is_sparse(oneri: dict) -> bool:
    return not (
        (oneri.get("gerekceler") or [])
        or (oneri.get("olcekler") or [])
        or (oneri.get("gruplama_degiskenleri") or [])
        or (oneri.get("outcome_degiskenleri") or [])
    )


async def gemini_analiz_oneri(
    columns: List[str],
    labels: Dict[str, str],
    anket_text: str,
    etik_text: str,
    document_context: dict | None = None,
) -> dict:
    """Gemini ile analiz planı önerisi üret."""
    from llm_router import (
        _parse_json_object,
        gemini_json_task,
        has_gemini_enrich,
        merge_meta,
    )

    meta: dict = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    anket_text, etik_text = _resolve_belge_texts(
        anket_text, etik_text, document_context,
    )
    meta["anket_text_len"] = len(anket_text)
    meta["etik_text_len"] = len(etik_text)
    belge_var = len(anket_text) + len(etik_text) > 100

    if not has_gemini_enrich():
        meta["gemini_ok"] = False
        meta["plan_source"] = "belgeler" if belge_var else "fallback"
        base = _plan_from_belgeler(anket_text, etik_text, columns) if belge_var else {}
        return {
            "oneri": _enrich_oneri(
                base, columns, etik_text, anket_text, gemini_failed=True,
            ),
            "meta": meta,
        }

    user = f"""
Sütunlar: {', '.join(columns[:60])}
Etiketler: {dict(list(labels.items())[:30])}

Anket içeriği:
{anket_text[:4000]}

Etik kurul belgesi:
{etik_text[:3000]}
"""
    raw, gem_meta = gemini_json_task(ONERI_SYSTEM, user, max_tokens=2500)
    meta = merge_meta(meta, gem_meta)
    parsed = _parse_json_object(raw) if raw else {}
    gemini_called = bool(meta.get("llm_calls"))
    useful = _gemini_response_useful(parsed)

    if useful:
        oneri = _enrich_oneri(
            parsed, columns, etik_text, anket_text, gemini_failed=False,
        )
        meta["gemini_ok"] = True
        meta["plan_source"] = "gemini"
    elif belge_var:
        oneri = _enrich_oneri(
            _plan_from_belgeler(anket_text, etik_text, columns),
            columns, etik_text, anket_text, gemini_failed=not gemini_called,
        )
        meta["gemini_ok"] = False
        meta["plan_source"] = "belgeler"
        if not gemini_called:
            meta["gemini_error"] = "api_yanit_vermedi"
        elif raw:
            meta["gemini_error"] = "json_parse"
    else:
        oneri = _fallback_oneri(columns, etik_text, anket_text, gemini_failed=True)
        meta["gemini_ok"] = False
        meta["plan_source"] = "fallback"

    return {"oneri": oneri, "meta": meta}


# Geriye dönük test importu
haiku_gozden_gecir = haiku_incele_plan
