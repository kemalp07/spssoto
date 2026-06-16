"""Analiz önerisi endpoint testleri."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from analiz_oneri import gemini_analiz_oneri, haiku_incele_plan, _plan_from_belgeler


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
async def test_gemini_analiz_oneri_enriches_sparse_json():
    payload = '{"ozet":"Kısa özet","gerekceler":[],"olcekler":[],'
    payload += '"gruplama_degiskenleri":[],"outcome_degiskenleri":[]}'
    cols = ["dbf_cinsiyet", "OYS1", "OYS2", "OYS3", "OYS_TOPLAM", "NEQ_TOPLAM"]
    with patch("llm_router.has_gemini_enrich", return_value=True), patch(
        "llm_router.gemini_json_task",
        return_value=(payload, {"llm_calls": 1}),
    ):
        result = await gemini_analiz_oneri(cols, {}, "anket", "H1: fark vardır")
    oneri = result["oneri"]
    assert oneri["gruplama_degiskenleri"] == ["dbf_cinsiyet"]
    assert "OYS_TOPLAM" in oneri["outcome_degiskenleri"]
    assert oneri["olcekler"]
    assert oneri["gerekceler"]


@pytest.mark.asyncio
async def test_fallback_oneri_infers_from_columns():
    with patch("llm_router.has_gemini_enrich", return_value=False):
        result = await gemini_analiz_oneri(
            ["dbf_bolum", "SBITO_TOPLAM"],
            {"dbf_bolum": "Bölüm"},
            "",
            "H1: Bölümler arası fark vardır.",
        )
    oneri = result["oneri"]
    assert "dbf_bolum" in oneri["gruplama_degiskenleri"]
    assert "SBITO_TOPLAM" in oneri["outcome_degiskenleri"]
    assert oneri["gerekceler"]


def test_plan_from_belgeler_uses_hypotheses():
    plan = _plan_from_belgeler(
        "Anket maddeleri",
        "H1: Cinsiyet ile OYS arasinda fark vardir.\nH2: Yas ile NEQ iliskilidir.",
        ["dbf_cinsiyet", "OYS_TOPLAM", "NEQ_TOPLAM"],
    )
    assert len(plan["gerekceler"]) >= 2
    assert "Etik kurul belgesi okundu" in plan["analiz"]
    assert plan["gruplama_degiskenleri"]


@pytest.mark.asyncio
async def test_gemini_falls_back_to_belgeler_on_bad_json():
    cols = ["dbf_cinsiyet", "OYS_TOPLAM"]
    with patch("llm_router.has_gemini_enrich", return_value=True), patch(
        "llm_router.gemini_json_task",
        return_value=("not json at all", {"llm_calls": 1}),
    ):
        result = await gemini_analiz_oneri(
            cols, {}, "anket " * 20, "H1: Cinsiyet ile OYS arasinda anlamli fark vardir. " * 3, None,
        )
    assert result["meta"]["plan_source"] == "belgeler"
    assert result["oneri"]["gerekceler"]


@pytest.mark.asyncio
async def test_haiku_incele_plan_without_claude():
    with patch("llm_router.has_claude", return_value=False):
        text, meta = await haiku_incele_plan({"ozet": "x"})
    assert text == ""
    assert meta["llm_calls"] == 0


@pytest.mark.asyncio
async def test_haiku_incele_plan_with_claude():
    with patch("llm_router.has_claude", return_value=True), patch(
        "llm_router.claude_decide",
        return_value=("Plan uygun.", {"llm_calls": 1}),
    ):
        text, meta = await haiku_incele_plan({"ozet": "Plan", "gerekceler": []})
    assert "Plan uygun" in text
    assert meta["llm_calls"] == 1
