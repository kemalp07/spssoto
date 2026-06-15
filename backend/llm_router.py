"""İki aşamalı LLM: Gemini veri analisti (veri_analisti.py), Claude karar verici (karar_verici.py)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Tuple

import anthropic

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    ENABLE_GEMINI_ENRICH,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_USE_VERTEX,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_CLOUD_PROJECT,
)

logger = logging.getLogger(__name__)

GEMINI_ENRICH_SYSTEM = """Sen veri seti ön inceleme asistanısın. Ham istatistik hesaplama.
Görevin: verilen sütun profilini okuyup Claude'un karar vermesini kolaylaştıracak yapılandırılmış özet üretmek.

SADECE JSON döndür:
{
  "column_hints": {
    "col_name": {
      "suggested_type": "categorical|continuous|exclude",
      "suggested_role": "grouping|outcome|exclude",
      "note": "kısa Türkçe gerekçe"
    }
  },
  "scale_candidates": [
    {"name": "ölçek adı", "items": ["madde1", "madde2"], "confidence": "high|medium|low"}
  ],
  "warnings": ["tekrarlı değişken", "eksik veri yüksek", ...],
  "research_notes": "araştırma konusuyla ilişki, 1-3 cümle"
}"""


def _empty_meta() -> Dict[str, Any]:
    return {
        "llm_calls": 0,
        "approx_input_tokens": 0,
        "approx_output_tokens": 0,
        "llm_provider": "",
        "llm_model": "",
    }


def merge_meta(*parts: dict) -> dict:
    out = _empty_meta()
    for p in parts:
        if not p:
            continue
        out["llm_calls"] += int(p.get("llm_calls", 0) or 0)
        out["approx_input_tokens"] += int(p.get("approx_input_tokens", 0) or 0)
        out["approx_output_tokens"] += int(p.get("approx_output_tokens", 0) or 0)
        if p.get("llm_provider"):
            out["llm_provider"] = p["llm_provider"]
        if p.get("llm_model"):
            out["llm_model"] = p["llm_model"]
        if p.get("enrich_provider"):
            out["enrich_provider"] = p["enrich_provider"]
        if p.get("enrich_model"):
            out["enrich_model"] = p["enrich_model"]
    return out


def has_claude() -> bool:
    return bool(ANTHROPIC_API_KEY)


def has_gemini_enrich() -> bool:
    if not ENABLE_GEMINI_ENRICH:
        return False
    if GEMINI_API_KEY:
        return True
    return bool(GEMINI_USE_VERTEX and GOOGLE_CLOUD_PROJECT)


def gemini_api_mode() -> str:
    """vertex_express | vertex_adc | ai_studio (AQ... dahil yeni Studio anahtarlari)."""
    if not GEMINI_USE_VERTEX:
        return "ai_studio"
    if GEMINI_API_KEY:
        return "vertex_express"
    if GOOGLE_CLOUD_PROJECT:
        return "vertex_adc"
    return "ai_studio"


def _make_gemini_client():
    from google import genai

    mode = gemini_api_mode()
    if mode == "vertex_express":
        return genai.Client(vertexai=True, api_key=GEMINI_API_KEY)
    if mode == "vertex_adc":
        return genai.Client(
            vertexai=True,
            project=GOOGLE_CLOUD_PROJECT,
            location=GOOGLE_CLOUD_LOCATION,
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def _gemini_json(system: str, user: str, max_tokens: int) -> Tuple[str, dict]:
    from google.genai import types

    client = _make_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    text = (response.text or "").strip()
    meta = _empty_meta()
    meta["llm_calls"] = 1
    meta["enrich_provider"] = "vertex" if gemini_api_mode().startswith("vertex") else "gemini"
    meta["enrich_model"] = GEMINI_MODEL
    meta["enrich_api_mode"] = gemini_api_mode()
    usage = getattr(response, "usage_metadata", None)
    if usage:
        meta["approx_input_tokens"] = int(getattr(usage, "prompt_token_count", 0) or 0)
        meta["approx_output_tokens"] = int(getattr(usage, "candidates_token_count", 0) or 0)
    return text, meta


def gemini_enrich_profile(
    task: str,
    profile: dict,
    research_context: str = "",
    max_tokens: int = 2000,
) -> Tuple[dict, dict]:
    """Gemini: ayrıntılı veri taraması — karar vermez, Claude'a bağlam sağlar."""
    if not has_gemini_enrich():
        return {}, _empty_meta()

    user = (
        f"Görev: {task}\n"
        f"Araştırma: {(research_context or '').strip()[:600]}\n"
        f"Veri profili:\n{json.dumps(profile, ensure_ascii=False)[:14000]}"
    )
    try:
        text, meta = _gemini_json(GEMINI_ENRICH_SYSTEM, user, max_tokens)
        return _parse_json_object(text), meta
    except Exception as exc:
        err = str(exc)
        if "prepayment credits are depleted" in err.lower():
            logger.warning(
                "Gemini enrich atlandi: AI Studio on-odeme bakiyesi sorunu. "
                "Yeni AQ... anahtarini backend/.env'e yazin; GEMINI_USE_VERTEX=false olmali. "
                "Kontrol: scripts/check_gemini.py"
            )
        elif "401" in err and gemini_api_mode().startswith("vertex"):
            logger.warning(
                "Vertex enrich failed: GEMINI_USE_VERTEX=true iken Studio anahtari (AIza/AQ) "
                "kullaniliyor olabilir. Studio icin GEMINI_USE_VERTEX=false yapin."
            )
        elif "403" in err and "aiplatform" in err.lower():
            logger.warning(
                "Vertex enrich atlandi: Vertex AI API projede kapali veya izin yok. "
                "Google Cloud Console'da 'Vertex AI API' etkinlestirin, birkaç dakika bekleyin."
            )
        elif "prepayment credits" not in err.lower():
            logger.warning("Gemini enrich failed: %s", exc)
        return {}, _empty_meta()


def claude_decide(system: str, user: str, max_tokens: int = 1000) -> Tuple[str, dict]:
    """Claude Haiku: nihai karar (sınıflandırma, plan seçimi, ölçek)."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY ayarlanmamış")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = msg.content[0].text.strip()
    meta = _empty_meta()
    meta["llm_calls"] = 1
    meta["llm_provider"] = "anthropic"
    meta["llm_model"] = ANTHROPIC_MODEL
    if msg.usage:
        meta["approx_input_tokens"] = int(msg.usage.input_tokens or 0)
        meta["approx_output_tokens"] = int(msg.usage.output_tokens or 0)
    return text, meta


def gemini_json_task(system: str, user: str, max_tokens: int = 1200) -> Tuple[str, dict]:
    """Gemini'den ham JSON metni döndürür (enrich / hipotez ayrıştırma)."""
    if not has_gemini_enrich():
        return "", _empty_meta()
    try:
        return _gemini_json(system, user, max_tokens)
    except Exception as exc:
        logger.warning("Gemini JSON task failed: %s", exc)
        return "", _empty_meta()


def format_enrichment_block(enrichment: dict) -> str:
    if not enrichment:
        return ""
    return (
        "\n\n━━━ GEMİNİ VERİ TARAMASI (yardımcı bağlam, kesin kural değil) ━━━\n"
        + json.dumps(enrichment, ensure_ascii=False, indent=2)[:8000]
    )
