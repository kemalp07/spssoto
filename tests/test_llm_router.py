"""İki aşamalı LLM: Gemini zenginleştirme + Claude karar."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from llm_router import (
    _parse_json_object,
    claude_decide,
    gemini_api_mode,
    gemini_enrich_profile,
    has_claude,
    merge_meta,
)


def test_merge_meta_combines_enrich_and_decide():
    enrich = {
        "llm_calls": 1,
        "approx_input_tokens": 100,
        "approx_output_tokens": 50,
        "enrich_provider": "gemini",
        "enrich_model": "gemini-2.5-flash",
        "plan_source": "gemini",
        "anket_text_len": 1152,
    }
    decide = {
        "llm_calls": 1,
        "approx_input_tokens": 200,
        "approx_output_tokens": 80,
        "llm_provider": "anthropic",
        "llm_model": "claude-haiku-4-5-20251001",
    }
    merged = merge_meta(enrich, decide)
    assert merged["llm_calls"] == 2
    assert merged["enrich_provider"] == "gemini"
    assert merged["llm_provider"] == "anthropic"
    assert merged["plan_source"] == "gemini"
    assert merged["anket_text_len"] == 1152


def test_gemini_enrich_skipped_without_key():
    with patch("llm_router.has_gemini_enrich", return_value=False):
        data, meta = gemini_enrich_profile("classify", {"columns": []})
    assert data == {}
    assert meta["llm_calls"] == 0


def test_claude_decide_requires_key():
    with patch("llm_router.ANTHROPIC_API_KEY", None):
        with pytest.raises(RuntimeError):
            claude_decide("sys", "user")


def test_claude_decide_uses_anthropic_only():
    fake_meta = {
        "llm_calls": 1,
        "approx_input_tokens": 10,
        "approx_output_tokens": 5,
        "llm_provider": "anthropic",
        "llm_model": "claude-haiku-4-5-20251001",
    }
    with patch("llm_router.ANTHROPIC_API_KEY", "key"), patch(
        "llm_router._anthropic_complete" if False else "anthropic.Anthropic"
    ):
        pass
    with patch("llm_router.ANTHROPIC_API_KEY", "key"), patch(
        "llm_router.anthropic.Anthropic"
    ) as mock_cls:
        mock_cls.return_value.messages.create.return_value = type(
            "Msg", (), {
                "content": [type("Block", (), {"text": '{"ok": true}'})()],
                "usage": type("U", (), {"input_tokens": 10, "output_tokens": 5})(),
            }
        )()
        text, meta = claude_decide("sys", "user")
    assert "ok" in text
    assert meta["llm_provider"] == "anthropic"


def test_gemini_api_mode_vertex_when_enabled():
    with patch("llm_router.GEMINI_USE_VERTEX", True), patch(
        "llm_router.GEMINI_API_KEY", "vertex-express-key",
    ):
        assert gemini_api_mode() == "vertex_express"


def test_gemini_api_mode_ai_studio_for_aq_key():
    with patch("llm_router.GEMINI_USE_VERTEX", False), patch(
        "llm_router.GEMINI_API_KEY", "AQ.test-key",
    ):
        assert gemini_api_mode() == "ai_studio"


def test_gemini_api_mode_ai_studio_for_aiza():
    with patch("llm_router.GEMINI_USE_VERTEX", False), patch(
        "llm_router.GEMINI_API_KEY", "AIzaSyTest",
    ):
        assert gemini_api_mode() == "ai_studio"


def test_has_claude():
    with patch("llm_router.ANTHROPIC_API_KEY", "x"):
        assert has_claude() is True


def test_parse_json_object_trailing_garbage():
    raw = '{"ozet":"Test"} extra text'
    assert _parse_json_object(raw)["ozet"] == "Test"


def test_parse_json_object_truncated():
    raw = '{"ozet":"Uzun özet","gerekceler":[{"analiz":"x","neden":"y"}'
    parsed = _parse_json_object(raw)
    assert parsed.get("ozet") == "Uzun özet"


def test_salvage_partial_json_with_gerekce():
    from llm_router import _salvage_partial_json

    raw = (
        '{"ozet":"Kesik özet devam","gerekceler":[{"analiz":"A","neden":"B",'
        '"degiskenler":["bolum","OYS_TOPLAM"],"tip":"karsilastirma"}'
    )
    salvaged = _salvage_partial_json(raw)
    assert salvaged.get("ozet")
    assert salvaged.get("gerekceler")
