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
    GEMINI_MAX_OUTPUT_TOKENS,
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
        for k, v in p.items():
            if k in ("llm_calls", "approx_input_tokens", "approx_output_tokens"):
                out[k] = int(out.get(k, 0) or 0) + int(v or 0)
            elif v is not None and v != "":
                out[k] = v
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


def _normalize_json_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = (
        raw.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw).strip()
    return raw


def _repair_truncated_json(blob: str) -> str:
    """Kesik Gemini JSON çıktısını kapatmayı dene."""
    s = blob.rstrip()
    # Kesik string değeri (ör. ozet ortasında MAX_TOKENS)
    if s.count('"') % 2 == 1:
        s += '"'
    s = re.sub(r",\s*$", "", s)
    s = re.sub(r",\s*\"[^\"\\]*(?:\\.[^\"\\]*)*$", "", s)
    open_brackets = s.count("[") - s.count("]")
    open_braces = s.count("{") - s.count("}")
    if open_brackets > 0:
        s += "]" * open_brackets
    if open_braces > 0:
        s += "}" * open_braces
    return s


def _salvage_partial_json(text: str) -> dict:
    """MAX_TOKENS ile kesilmiş yanıttan ozet ve tam gerekce nesnelerini kurtar."""
    raw = _normalize_json_text(text)
    if not raw or not raw.lstrip().startswith("{"):
        return {}
    out: dict = {}
    ozet_m = re.search(r'"ozet"\s*:\s*"((?:[^"\\]|\\.)*)', raw)
    if ozet_m:
        out["ozet"] = ozet_m.group(1).replace('\\"', '"').replace("\\n", "\n")
    elif '"ozet"' in raw:
        tail = re.search(r'"ozet"\s*:\s*"(.*)$', raw, re.DOTALL)
        if tail:
            out["ozet"] = tail.group(1).replace("\\n", "\n").strip()
    gerekceler: list = []
    for block in re.finditer(
        r'\{\s*"analiz"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"neden"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"degiskenler"\s*:\s*\[([^\]]*)\]\s*,\s*"tip"\s*:\s*"([^"]*)"\s*\}',
        raw,
    ):
        vars_raw = block.group(3)
        degiskenler = [
            v.strip().strip('"')
            for v in vars_raw.split(",")
            if v.strip().strip('"')
        ]
        gerekceler.append({
            "analiz": block.group(1).replace('\\"', '"'),
            "neden": block.group(2).replace('\\"', '"'),
            "degiskenler": degiskenler,
            "tip": block.group(4),
        })
    if gerekceler:
        out["gerekceler"] = gerekceler
    return out


def _parse_json_object(text: str) -> dict:
    raw = _normalize_json_text(text)
    if not raw:
        return {}

    attempts = [raw]
    start = raw.find("{")
    if start > 0:
        attempts.append(raw[start:])
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        attempts.append(match.group())

    seen: set[str] = set()
    for blob in attempts:
        if not blob or blob in seen:
            continue
        seen.add(blob)
        try:
            obj, _end = json.JSONDecoder().raw_decode(blob)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        try:
            obj = json.loads(blob)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        cleaned = re.sub(r",\s*([}\]])", r"\1", blob)
        if cleaned != blob:
            try:
                obj = json.loads(cleaned)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
        repaired = _repair_truncated_json(blob)
        if repaired != blob:
            try:
                obj = json.loads(repaired)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
    salvaged = _salvage_partial_json(text)
    if salvaged:
        return salvaged
    return {}


def _gemini_json(system: str, user: str, max_tokens: int | None = None) -> Tuple[str, dict]:
    from google.genai import types

    out_limit = max_tokens if max_tokens is not None else GEMINI_MAX_OUTPUT_TOKENS
    client = _make_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=out_limit,
            temperature=0.0,
            response_mime_type="application/json",
            # 2.5 Flash: thinking + output paylaşımlı bütçe; JSON görevlerinde thinking kapat
            thinking_config=types.ThinkingConfig(thinking_budget=0),
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
        thoughts = getattr(usage, "thoughts_token_count", None)
        if thoughts is not None:
            meta["gemini_thought_tokens"] = int(thoughts or 0)
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        finish = getattr(candidates[0], "finish_reason", None)
        if finish is not None:
            meta["gemini_finish_reason"] = str(finish)
    return text, meta


def gemini_enrich_profile(
    task: str,
    profile: dict,
    research_context: str = "",
    max_tokens: int | None = None,
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


def gemini_json_task(
    system: str,
    user: str,
    max_tokens: int | None = None,
) -> Tuple[str, dict]:
    """Gemini'den ham JSON metni döndürür (enrich / hipotez ayrıştırma)."""
    if not has_gemini_enrich():
        return "", _empty_meta()
    try:
        return _gemini_json(system, user, max_tokens)
    except Exception as exc:
        logger.warning("Gemini JSON task failed: %s", exc)
        return "", _empty_meta()


def gemini_text_task(
    system: str,
    user: str,
    max_tokens: int | None = None,
) -> Tuple[str, dict]:
    """Gemini'den düz metin döndürür (plan analizi, özet yorum)."""
    if not has_gemini_enrich():
        return "", _empty_meta()
    try:
        from google.genai import types

        out_limit = max_tokens if max_tokens is not None else GEMINI_MAX_OUTPUT_TOKENS
        client = _make_gemini_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=out_limit,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
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
    except Exception as exc:
        logger.warning("Gemini text task failed: %s", exc)
        return "", _empty_meta()


def format_enrichment_block(enrichment: dict) -> str:
    if not enrichment:
        return ""
    return (
        "\n\n━━━ GEMİNİ VERİ TARAMASI (yardımcı bağlam, kesin kural değil) ━━━\n"
        + json.dumps(enrichment, ensure_ascii=False, indent=2)[:8000]
    )
