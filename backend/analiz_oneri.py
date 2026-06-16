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

_HYP_LINE_MATCH = re.compile(
    r"^\s*(?:H|AS|HS|AH)\s*\d+\s*[:.)]\s*(.+)$",
    re.IGNORECASE,
)
_HYP_NUM_MATCH = re.compile(
    r"^\s*(?:Soru|Hipotez|Araştırma\s+Sorusu)\s*\d+\s*[:.)]\s*(.+)$",
    re.IGNORECASE,
)
_TOPLAM_RE = re.compile(r"_(TOPLAM|TOTAL|PUAN|SCORE|SUM)$", re.I)
_OUTCOME_HINT = re.compile(r"(toplam|total|_score|_puan|_sum)", re.I)
_GROUPING_NAMES = frozenset(
    {"bolum", "cinsiyet", "gender", "department", "dept", "sinif", "yas_grubu", "yasgrubu"},
)
_CATEGORICAL_DBF = re.compile(
    r"^dbf_(cinsiyet|gender|bolum|department|dept|sinif|sk|yas_grubu|yasgrubu)$",
    re.I,
)
_MAX_GEREKCE = 6
_ITEM_PREFIX_RE = re.compile(
    r"^(?:recoded_|rev_|inv_)?([a-zA-Z]+)[_]?(\d+)",
    re.I,
)

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

ONERI_SYSTEM_COMPACT = """Akademik tez analiz planı. Türkçe, SADECE JSON.

Kurallar: Etik kurulda geçen analizler; max 6 gerekce; boy/kilo/yaş gruplama DEĞİL.
KISA YAZ: ozet max 150 karakter; neden max 80 karakter; olcek neden max 50 karakter.

{
  "ozet": "...",
  "gerekceler": [{"analiz":"...","neden":"...","degiskenler":["bolum","OYS_TOPLAM"],"tip":"karsilastirma"}],
  "olcekler": [{"ad":"OYS","prefix":"OYS","neden":"..."}],
  "gruplama_degiskenleri": ["bolum","dbf_cinsiyet"],
  "outcome_degiskenleri": ["OYS_TOPLAM","NEQ_TOPLAM","SBITO_TOPLAM"]
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


def _is_grouping_column(col: str) -> bool:
    low = col.lower().replace("-", "_")
    if low in _GROUPING_NAMES:
        return True
    if _CATEGORICAL_DBF.match(low):
        return True
    base = low[4:] if low.startswith("dbf_") else low
    return base in {"bolum", "cinsiyet", "gender", "department", "dept", "sinif", "sk"}


def _infer_grouping_columns(columns: List[str]) -> List[str]:
    return [c for c in columns if _is_grouping_column(c)]


def _filter_grouping(columns: List[str]) -> List[str]:
    return [c for c in columns if _is_grouping_column(c)]


def _primary_grouping(grouping: List[str]) -> List[str]:
    order = ("bolum", "dbf_bolum", "cinsiyet", "dbf_cinsiyet", "sinif", "dbf_sk")
    picked: List[str] = []
    low_map = {g.lower(): g for g in grouping}
    for key in order:
        if key in low_map and low_map[key] not in picked:
            picked.append(low_map[key])
    for g in grouping:
        if g not in picked:
            picked.append(g)
    return picked[:2]


def _extract_hypotheses_from_etik(etik_text: str) -> List[str]:
    found: List[str] = []
    seen: set = set()
    for line in (etik_text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        text = None
        m = _HYP_LINE_MATCH.match(s)
        if m:
            text = m.group(1).strip()
        else:
            m = _HYP_NUM_MATCH.match(s)
            if m:
                text = m.group(1).strip()
        if text and len(text) > 15 and text not in seen:
            seen.add(text)
            found.append(text)
    return found[:_MAX_GEREKCE]


def _outcome_for_hypothesis(hyp: str, outcomes: List[str]) -> str:
    low = hyp.lower()
    aliases = (
        ("oys", "oyşt", "oyş"),
        ("neq", "gece"),
        ("sbito", "sbi"),
    )
    for keys, _ in [(a, a) for a in aliases]:
        if any(k in low for k in keys):
            for o in outcomes:
                if keys[0].upper() in o.upper():
                    return o
    return outcomes[0] if outcomes else ""


def _grouping_for_hypothesis(hyp: str, grouping: List[str]) -> str:
    low = hyp.lower()
    if "bölüm" in low or "bolum" in low:
        for g in grouping:
            if "bolum" in g.lower():
                return g
    if "cinsiyet" in low:
        for g in grouping:
            if "cinsiyet" in g.lower():
                return g
    primary = _primary_grouping(grouping)
    return primary[0] if primary else ""


def _gerekceler_from_hypotheses(
    hyps: List[str],
    grouping: List[str],
    outcomes: List[str],
) -> List[dict]:
    gerekceler: List[dict] = []
    for hyp in hyps[:_MAX_GEREKCE]:
        g = _grouping_for_hypothesis(hyp, grouping)
        o = _outcome_for_hypothesis(hyp, outcomes)
        if not o:
            continue
        title = hyp[:120]
        if g:
            title = f"{g} gruplarına göre {o} — {hyp[:80]}"
        gerekceler.append({
            "analiz": title[:200],
            "neden": f"Etik kurul: «{hyp[:200]}»",
            "degiskenler": [v for v in [g, o] if v],
            "tip": "karsilastirma",
        })
    return _fill_pair_grid(gerekceler, _primary_grouping(grouping), outcomes)


def _existing_pairs(
    gerekceler: List[dict],
    grouping: List[str],
    outcomes: List[str],
) -> set[tuple[str, str]]:
    gset = set(grouping)
    oset = set(outcomes)
    pairs: set[tuple[str, str]] = set()
    for row in gerekceler:
        vars_ = row.get("degiskenler") or []
        gs = [v for v in vars_ if v in gset]
        os_ = [v for v in vars_ if v in oset]
        if gs and os_:
            pairs.add((gs[0], os_[0]))
    return pairs


def _fill_pair_grid(
    gerekceler: List[dict],
    grouping: List[str],
    outcomes: List[str],
) -> List[dict]:
    """Eksik gruplama×outcome çiftlerini doldur (max 6)."""
    out = list(gerekceler)
    pairs = _existing_pairs(out, grouping, outcomes)
    for g in grouping:
        for o in outcomes:
            if len(out) >= _MAX_GEREKCE:
                return out
            if (g, o) in pairs:
                continue
            out.append({
                "analiz": f"{g} gruplarına göre {o} karşılaştırması",
                "neden": "Etik kurul ve veri seti yapısına göre önerildi",
                "degiskenler": [g, o],
                "tip": "karsilastirma",
            })
            pairs.add((g, o))
    return out[:_MAX_GEREKCE]


def _fill_grouping_gerekceler(
    gerekceler: List[dict],
    grouping: List[str],
    outcomes: List[str],
) -> List[dict]:
    """Hipotez gerekçelerine eksik gruplama×outcome çiftlerini ekle."""
    return _fill_pair_grid(gerekceler, grouping, outcomes)


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


def _scale_prefix_from_outcome(outcome: str) -> str:
    base = _TOPLAM_RE.sub("", outcome).strip("_")
    return (base.split("_")[0] or base).upper()


def _count_scale_items(columns: List[str], prefix: str) -> int:
    pfx = prefix.lower()
    count = 0
    for col in columns:
        m = _ITEM_PREFIX_RE.match(col)
        if m and m.group(1).lower() == pfx:
            count += 1
    return count


def _infer_olcekler(columns: List[str]) -> List[dict]:
    olcekler: List[dict] = []
    seen: set[str] = set()
    outcomes = _infer_outcome_columns(columns)
    for outcome in outcomes:
        prefix = _scale_prefix_from_outcome(outcome)
        key = prefix.lower()
        if key in seen:
            continue
        n_items = _count_scale_items(columns, prefix)
        if n_items >= 2 or outcome in columns:
            seen.add(key)
            neden = (
                f"Sütun adlarından {n_items} madde tespit edildi"
                if n_items >= 2
                else f"Veri setinde {outcome} sonuç değişkeni bulundu"
            )
            olcekler.append({
                "ad": prefix,
                "prefix": prefix,
                "maddeler_prefix": prefix,
                "neden": neden,
            })
    if olcekler:
        return olcekler
    groups = detect_scale_groups(columns)
    for prefix, items in groups.items():
        if len(items) < 2:
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
    hyps = _extract_hypotheses_from_etik(etik_text)
    primary = _primary_grouping(grouping)
    if hyps and primary:
        return _gerekceler_from_hypotheses(hyps, primary, outcomes)
    if not primary or not outcomes:
        return []
    return _fill_pair_grid([], primary, outcomes)


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
    if not gerekceler:
        hyps = _extract_hypotheses_from_etik(etik_text)
        if hyps and grouping and outcomes:
            out["gerekceler"] = _gerekceler_from_hypotheses(
                hyps, _primary_grouping(grouping), outcomes,
            )
        elif gemini_failed and grouping and outcomes:
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
    hyps = _extract_hypotheses_from_etik(etik_text)
    primary = _primary_grouping(grouping)

    gerekceler = _gerekceler_from_hypotheses(hyps, primary, outcomes)
    if not gerekceler:
        gerekceler = _build_gerekceler(grouping, outcomes, etik_text)
    else:
        gerekceler = _fill_grouping_gerekceler(gerekceler, primary, outcomes)

    if hyps:
        ozet = (
            f"Etik kurul belgesinde {len(hyps)} araştırma sorusu/hipotez belirlendi. "
            "Önerilen analizler etik kurulda tanımlanan karşılaştırmalara göre planlandı."
        )
    elif primary and outcomes:
        ozet = (
            f"Etik kurul ve anket belgelerine göre "
            f"{', '.join(primary)} grupları ile "
            f"{', '.join(outcomes[:3])} karşılaştırmaları önerildi."
        )
    else:
        ozet = "Yüklenen belgelere göre analiz planı oluşturuldu."

    return {
        "ozet": ozet,
        "gerekceler": gerekceler,
        "olcekler": olcekler,
        "gruplama_degiskenleri": primary or grouping,
        "outcome_degiskenleri": outcomes,
    }


def _compact_columns_for_prompt(columns: List[str]) -> str:
    grouping = _infer_grouping_columns(columns)
    outcomes = _infer_outcome_columns(columns)
    samples = [
        c for c in columns
        if _ITEM_PREFIX_RE.match(c) or _TOPLAM_RE.search(c)
    ][:20]
    lines = [
        f"Toplam sütun: {len(columns)}",
        f"Gruplama: {', '.join(grouping) or '—'}",
        f"Sonuç (_TOPLAM): {', '.join(outcomes) or '—'}",
    ]
    if samples:
        lines.append(f"Örnek maddeler: {', '.join(samples)}")
    return "\n".join(lines)


def _build_gemini_user_prompt(
    columns: List[str],
    labels: Dict[str, str],
    anket_text: str,
    etik_text: str,
    *,
    compact: bool = False,
) -> str:
    if compact:
        col_block = _compact_columns_for_prompt(columns)
    else:
        col_block = f"Sütunlar: {', '.join(columns)}"
    return f"""
{col_block}
Etiketler: {dict(list(labels.items())[:50])}

Anket içeriği:
{anket_text or ''}

Etik kurul belgesi:
{etik_text or ''}
"""


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

    user = _build_gemini_user_prompt(
        columns, labels, anket_text, etik_text, compact=False,
    )
    raw, gem_meta = gemini_json_task(ONERI_SYSTEM, user)
    meta = merge_meta(meta, gem_meta)
    parsed = _parse_json_object(raw) if raw else {}
    finish = str(meta.get("gemini_finish_reason") or "")

    if raw and not _gemini_response_useful(parsed):
        retry_system = (
            ONERI_SYSTEM_COMPACT
            if "MAX_TOKENS" in finish.upper()
            else ONERI_SYSTEM
        )
        retry_user = _build_gemini_user_prompt(
            columns, labels, anket_text, etik_text, compact=True,
        )
        raw2, gem_meta2 = gemini_json_task(retry_system, retry_user)
        meta = merge_meta(meta, gem_meta2)
        parsed2 = _parse_json_object(raw2) if raw2 else {}
        if _gemini_response_useful(parsed2):
            parsed = parsed2
            raw = raw2

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
            columns, etik_text, anket_text, gemini_failed=True,
        )
        meta["gemini_ok"] = False
        meta["plan_source"] = "belgeler"
        if not gemini_called:
            meta["gemini_error"] = "api_yanit_vermedi"
        elif raw:
            meta["gemini_error"] = "max_tokens" if "MAX_TOKENS" in finish.upper() else "json_parse"
            meta["gemini_raw_preview"] = (raw or "")[:400]
    else:
        oneri = _fallback_oneri(columns, etik_text, anket_text, gemini_failed=True)
        meta["gemini_ok"] = False
        meta["plan_source"] = "fallback"

    return {"oneri": oneri, "meta": meta}


# Geriye dönük test importu
haiku_gozden_gecir = haiku_incele_plan
