"""Analiz önerisi endpoint testleri."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from analiz_oneri import (
    _apply_haiku_corrections,
    _infer_olcekler,
    _plan_from_belgeler,
    gemini_analiz_oneri,
    haiku_incele_plan,
)


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
        "H1: Cinsiyet ile OYS arasinda fark vardir.\nH2: Bolum ile NEQ iliskilidir.",
        ["bolum", "dbf_cinsiyet", "dbf_yas", "dbf_boy", "OYS_TOPLAM", "NEQ_TOPLAM"],
    )
    assert len(plan["gerekceler"]) >= 2
    assert "araştırma sorusu" in plan["ozet"].lower() or "hipotez" in plan["ozet"].lower()
    assert "dbf_yas" not in plan["gruplama_degiskenleri"]
    assert "dbf_boy" not in plan["gruplama_degiskenleri"]
    assert any("Etik kurul" in g["neden"] for g in plan["gerekceler"])


def test_infer_olcekler_underscore_columns():
    cols = ["OYS_TOPLAM", "NEQ_TOPLAM", "SBITO_TOPLAM"]
    cols += [f"OYS_{i}" for i in range(1, 16)]
    cols += [f"neq_{i}" for i in range(1, 17)]
    cols += [f"SBITO_{i}" for i in range(1, 22)]
    olcekler = _infer_olcekler(cols)
    names = {o["prefix"] for o in olcekler}
    assert "OYS" in names
    assert "NEQ" in names
    assert "SBITO" in names


def test_plan_from_belgeler_covers_all_outcomes():
    cols = ["bolum", "dbf_cinsiyet", "OYS_TOPLAM", "NEQ_TOPLAM", "SBITO_TOPLAM"]
    plan = _plan_from_belgeler(
        "Anket",
        "H1: Bolumler arasi OYS farki vardir.",
        cols,
    )
    pairs = {
        tuple(v for v in (g.get("degiskenler") or []) if v in cols)
        for g in plan["gerekceler"]
    }
    expected = {
        ("bolum", "OYS_TOPLAM"),
        ("bolum", "NEQ_TOPLAM"),
        ("bolum", "SBITO_TOPLAM"),
        ("dbf_cinsiyet", "OYS_TOPLAM"),
        ("dbf_cinsiyet", "NEQ_TOPLAM"),
        ("dbf_cinsiyet", "SBITO_TOPLAM"),
    }
    assert expected.issubset(pairs)
    assert plan["olcekler"]


@pytest.mark.asyncio
async def test_gemini_falls_back_to_belgeler_on_bad_json():
    cols = ["dbf_cinsiyet", "OYS_TOPLAM", "NEQ_TOPLAM", "SBITO_TOPLAM"]
    with patch("llm_router.has_gemini_enrich", return_value=True), patch(
        "llm_router.gemini_json_task",
        side_effect=[
            ("not json at all", {"llm_calls": 1}),
            ("still not json", {"llm_calls": 1}),
        ],
    ):
        result = await gemini_analiz_oneri(
            cols, {}, "anket " * 20, "H1: Cinsiyet ile OYS arasinda anlamli fark vardir. " * 3, None,
        )
    assert result["meta"]["plan_source"] == "belgeler"
    assert result["meta"]["gemini_error"] == "json_parse"
    assert result["oneri"]["gerekceler"]
    assert result["oneri"]["olcekler"]


@pytest.mark.asyncio
async def test_gemini_retries_on_bad_json_then_succeeds():
    payload = (
        '{"ozet":"Gemini planı","gerekceler":[{"analiz":"x","neden":"y",'
        '"degiskenler":["bolum","OYS_TOPLAM"],"tip":"karsilastirma"}],'
        '"olcekler":[],"gruplama_degiskenleri":["bolum"],'
        '"outcome_degiskenleri":["OYS_TOPLAM"]}'
    )
    with patch("llm_router.has_gemini_enrich", return_value=True), patch(
        "llm_router.gemini_json_task",
        side_effect=[
            ("broken json", {"llm_calls": 1}),
            (payload, {"llm_calls": 1}),
        ],
    ):
        result = await gemini_analiz_oneri(["bolum", "OYS_TOPLAM"], {}, "anket", "etik")
    assert result["meta"]["plan_source"] == "gemini"
    assert result["oneri"]["ozet"] == "Gemini planı"


@pytest.mark.asyncio
async def test_haiku_incele_plan_without_claude():
    with patch("llm_router.has_claude", return_value=False):
        text, meta = await haiku_incele_plan({"ozet": "x"})
    assert text == ""
    assert meta["llm_calls"] == 0


@pytest.mark.asyncio
async def test_haiku_incele_plan_with_claude():
    payload = '{"durum":"ok","duzeltmeler":[]}'
    with patch("llm_router.has_claude", return_value=True), patch(
        "llm_router.claude_decide",
        return_value=(payload, {"llm_calls": 1}),
    ):
        text, meta = await haiku_incele_plan({"ozet": "Plan", "gerekceler": []})
    assert '"durum":"ok"' in text or '"durum": "ok"' in text
    assert meta["llm_calls"] == 1


def test_apply_haiku_corrections_removes_invalid_grouping():
    plan = {
        "ozet": "Test",
        "gruplama_degiskenleri": ["bolum", "dbf_boy", "dbf_cinsiyet"],
        "outcome_degiskenleri": ["OYS_TOPLAM"],
        "gerekceler": [
            {
                "analiz": "dbf_boy gruplarına göre OYS",
                "neden": "x",
                "degiskenler": ["dbf_boy", "OYS_TOPLAM"],
                "tip": "karsilastirma",
            },
            {
                "analiz": "bolum gruplarına göre OYS",
                "neden": "y",
                "degiskenler": ["bolum", "OYS_TOPLAM"],
                "tip": "karsilastirma",
            },
        ],
        "olcekler": [],
    }
    haiku_json = {
        "durum": "duzelt",
        "duzeltmeler": [
            {
                "alan": "gruplama_degiskenleri",
                "deger": "dbf_boy",
                "aksiyon": "cikar",
                "sebep": "Sürekli değişken",
            },
        ],
    }
    fixed = _apply_haiku_corrections(plan, haiku_json)
    assert "dbf_boy" not in fixed["gruplama_degiskenleri"]
    assert all("dbf_boy" not in (g.get("degiskenler") or []) for g in fixed["gerekceler"])


def test_apply_haiku_corrections_trims_gerekceler():
    plan = {
        "gerekceler": [{"analiz": f"A{i}", "neden": "n", "degiskenler": [], "tip": "x"} for i in range(8)],
    }
    haiku_json = {
        "durum": "duzelt",
        "duzeltmeler": [
            {
                "alan": "gerekceler",
                "deger": "6",
                "aksiyon": "kisalt",
                "sebep": "6'dan fazla",
            },
        ],
    }
    fixed = _apply_haiku_corrections(plan, haiku_json)
    assert len(fixed["gerekceler"]) == 6


def test_apply_haiku_corrections_removes_tanim_gerekceler():
    plan = {
        "gerekceler": [
            {"analiz": "OYŞTÖ düzeyi", "neden": "n", "degiskenler": ["OYS_TOPLAM"], "tip": "tanim"},
            {"analiz": "OYŞTÖ ile GYA ilişkisi", "neden": "n", "degiskenler": ["OYS_TOPLAM", "NEQ_TOPLAM"], "tip": "iliski"},
        ],
    }
    haiku_json = {
        "durum": "duzelt",
        "duzeltmeler": [
            {
                "alan": "gerekceler",
                "deger": "tanim",
                "aksiyon": "cikar",
                "sebep": "Tanımlayıcı analiz zaten frekans tablolarında",
            },
        ],
    }
    fixed = _apply_haiku_corrections(plan, haiku_json)
    assert len(fixed["gerekceler"]) == 1
    assert fixed["gerekceler"][0]["tip"] == "iliski"


def test_apply_haiku_corrections_adds_missing_outcome():
    plan = {
        "outcome_degiskenleri": ["OYS_TOPLAM"],
        "olcekler": [],
    }
    haiku_json = {
        "durum": "duzelt",
        "duzeltmeler": [
            {
                "alan": "outcome_degiskenleri",
                "deger": "NEQ_TOPLAM",
                "aksiyon": "ekle",
                "sebep": "Eksik ölçek toplamı",
            },
        ],
    }
    cols = ["OYS_TOPLAM", "NEQ_TOPLAM", "OYS_1", "neq_1", "neq_2"]
    fixed = _apply_haiku_corrections(plan, haiku_json, cols)
    assert "NEQ_TOPLAM" in fixed["outcome_degiskenleri"]
    assert fixed["olcekler"]
