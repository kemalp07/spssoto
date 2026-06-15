"""Analiz önerisi endpoint testleri."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from analiz_oneri import gemini_analiz_oneri, haiku_gozden_gecir


@pytest.mark.asyncio
async def test_gemini_analiz_oneri_fallback_without_gemini():
    with patch("llm_router.has_gemini_enrich", return_value=False):
        result = await gemini_analiz_oneri(
            ["bolum", "OYS_TOPLAM"],
            {"bolum": "Bölüm"},
            "",
            "",
        )
    assert "oneri" in result
    assert result["oneri"]["ozet"]


@pytest.mark.asyncio
async def test_gemini_analiz_oneri_parses_json():
    payload = (
        '{"ozet":"Test özeti","gerekceler":[],"olcekler":[],'
        '"gruplama_degiskenleri":["bolum"],"outcome_degiskenleri":["OYS_TOPLAM"]}'
    )
    with patch("llm_router.has_gemini_enrich", return_value=True), patch(
        "llm_router.gemini_json_task",
        return_value=(payload, {"llm_calls": 1}),
    ):
        result = await gemini_analiz_oneri([], {}, "", "")
    assert result["oneri"]["ozet"] == "Test özeti"


@pytest.mark.asyncio
async def test_haiku_gozden_gecir_without_claude():
    with patch("llm_router.has_claude", return_value=False):
        text = await haiku_gozden_gecir({"ozet": "x"})
    assert "Plan uygun" in text
