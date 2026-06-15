"""
Gemini 2.5 Flash ile anket + etik kurul → analiz planı önerisi.
Sadece PLANLAMA yapar. Hesaplama, test seçimi, normallik kararı vermez.
"""
from __future__ import annotations

from typing import Dict, List

ONERI_SYSTEM = """Sen akademik tez analiz planlama asistanısın.

Sana şunlar verilecek:
1. Veri seti sütun adları ve etiketleri
2. Anket formu (ölçekler, maddeler)
3. Etik kurul belgesi (araştırma soruları, amaç)

Görevin:
- Hangi değişkenlerin bağımsız (gruplama), hangilerinin bağımlı (outcome) olduğunu belirle
- Hangi ölçeklerin güvenilirlik analizi yapılacağını belirle
- Hangi gruplar arası karşılaştırmaların yapılacağını belirle
- Hangi ilişkilerin inceleneceğini belirle

YAPMA:
- Hangi testin kullanılacağına karar verme (t-test mi ANOVA mı → sistem karar verir)
- p değeri, F değeri gibi istatistik hesaplama
- Normallik varsayımı hakkında karar verme

SADECE JSON döndür:
{
  "ozet": "2-3 cümle genel açıklama",
  "gerekceler": [
    {
      "analiz": "Bölüme göre ölçek karşılaştırması",
      "neden": "Etik kurulda 'bölümler arası fark araştırılacak' yazıyor",
      "degiskenler": ["bolum", "OYS_TOPLAM", "NEQ_TOPLAM", "SBITO_TOPLAM"],
      "tip": "karsilastirma"
    }
  ],
  "olcekler": [
    {
      "ad": "OYŞTÖ",
      "maddeler_prefix": "OYS",
      "neden": "Anket formunda 15 madde tespit edildi"
    }
  ],
  "gruplama_degiskenleri": ["bolum", "dbf_cinsiyet", "dbf_sk"],
  "outcome_degiskenleri": ["OYS_TOPLAM", "NEQ_TOPLAM", "SBITO_TOPLAM"]
}

ÖNEMLİ: Anket veya etik kurul metni sınırlı olsa bile,
sütun adlarından ve etiketlerden çıkarım yap.
_TOPLAM suffix'li sütunlar = ölçek toplam puanı → outcome değişkeni
dbf_ prefix'li sütunlar = demografik değişken → gruplama
Minimum bilgiyle bile makul bir plan öner.
"""


def _fallback_oneri(columns: List[str]) -> dict:
    return {
        "ozet": "Belge bağlamı sınırlı; değişken adımında sınıflandırma ile devam edin.",
        "gerekceler": [],
        "olcekler": [],
        "gruplama_degiskenleri": [],
        "outcome_degiskenleri": [],
        "columns_seen": columns[:20],
    }


async def gemini_analiz_oneri(
    columns: List[str],
    labels: Dict[str, str],
    anket_text: str,
    etik_text: str,
) -> dict:
    """Gemini ile analiz planı önerisi üret."""
    from llm_router import (
        _parse_json_object,
        gemini_json_task,
        has_gemini_enrich,
        merge_meta,
    )

    meta: dict = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not has_gemini_enrich():
        return {"oneri": _fallback_oneri(columns), "meta": meta}

    user = f"""
Sütunlar: {', '.join(columns[:60])}
Etiketler: {dict(list(labels.items())[:30])}

Anket içeriği:
{(anket_text or '')[:3000]}

Etik kurul belgesi:
{(etik_text or '')[:2000]}
"""
    raw, gem_meta = gemini_json_task(ONERI_SYSTEM, user, max_tokens=2000)
    meta = merge_meta(meta, gem_meta)
    oneri = _parse_json_object(raw) if raw else {}
    if not oneri:
        oneri = _fallback_oneri(columns)
    return {"oneri": oneri, "meta": meta}


async def haiku_gozden_gecir(oneri: dict) -> str:
    """Claude Haiku ile öneriyi gözden geçir — mantık hatası var mı?"""
    from llm_router import claude_decide, has_claude

    if not has_claude():
        return "Plan uygun görünüyor."

    system = """Sen istatistik metodoloji uzmanısın.
Verilen analiz planı önerisini gözden geçir.
Sadece şunlara bak:
- Mantıksal tutarsızlık var mı?
- Açıkça yanlış bir analiz önerilmiş mi?
- Eksik kritik bir analiz var mı?

2-3 cümle yorum yap. Kısa ve net ol.
Eğer plan mantıklıysa "Plan uygun görünüyor" de ve bitir."""

    user = f"Analiz planı: {str(oneri)[:1500]}"
    result, _ = claude_decide(system, user, max_tokens=300)
    return (result or "Plan uygun görünüyor.").strip()
