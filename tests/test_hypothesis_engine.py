"""Hipotez motoru ve plan entegrasyonu testleri (LLM mock)."""
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from hypothesis_engine import (
    apply_hypothesis_to_catalog,
    parse_research_questions,
    translate_decision_reasons,
)
from layout_config import DEFAULT_LAYOUT_CONFIG
from schemas import Variable
from table_budget import apply_table_budget, core_candidate_ids, enrich_catalog_metadata
from test_planner import TIER_KESIN, TIER_ONERILEN, build_test_catalog, pick_kesin_core_ids
from word_export import _group_results_for_export, _hypothesis_section_title

_EMPTY_LLM_META = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}


@pytest.fixture
def planner_df() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    n = 40
    return pd.DataFrame({
        "cinsiyet": [1] * 20 + [2] * 20,
        "oys": rng.integers(10, 30, n),
        "gya": rng.integers(10, 30, n),
        "sonuc": rng.normal(50, 5, n),
    })


@pytest.fixture
def planner_vars() -> list:
    return [
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
        Variable(name="oys", label="OYŞTÖ", type="continuous", role="outcome"),
        Variable(name="gya", label="GYA", type="continuous", role="outcome"),
        Variable(name="sonuc", label="Sonuç", type="continuous", role="outcome"),
    ]


@pytest.fixture
def uygun_candidates():
    return [
        {
            "id": "descriptive",
            "test": "descriptive",
            "vars": ["oys", "gya", "sonuc"],
            "auto_flag": "uygun",
            "decision_log": {"reason": "Tanımlayıcı istatistikler"},
        },
        {
            "id": "correlation",
            "test": "correlation",
            "vars": ["oys", "gya", "sonuc"],
            "auto_flag": "uygun",
            "decision_log": {"reason": "Korelasyon analizi"},
        },
        {
            "id": "ttest:cinsiyet:oys",
            "test": "ttest",
            "vars": ["cinsiyet", "oys"],
            "auto_flag": "uygun",
            "decision_log": {"reason": "t-testi seçildi"},
        },
        {
            "id": "ttest:cinsiyet:gya",
            "test": "ttest",
            "vars": ["cinsiyet", "gya"],
            "auto_flag": "uygun",
            "decision_log": {"reason": "t-testi seçildi"},
        },
        {
            "id": "ttest:cinsiyet:sonuc",
            "test": "ttest",
            "vars": ["cinsiyet", "sonuc"],
            "auto_flag": "uygun",
            "decision_log": {"reason": "t-testi seçildi"},
        },
        {
            "id": "chi_square:cinsiyet:dummy",
            "test": "chi_square",
            "vars": ["cinsiyet", "dummy"],
            "auto_flag": "uygun",
            "decision_log": {"reason": "Ki-kare seçildi"},
        },
    ]


def test_apply_hypothesis_promotes_linked_and_demotes_unlinked_kesin(
    uygun_candidates, planner_vars,
):
    selected = {c["id"] for c in uygun_candidates}
    excluded = []
    catalog = build_test_catalog(uygun_candidates, selected, excluded, planner_vars)
    core_ids = core_candidate_ids(uygun_candidates)

    hypotheses = [{
        "id": "H1",
        "label": "OYŞTÖ ile GYA ilişkisi",
        "type": "iliski",
        "candidate_ids": ["correlation"],
    }]
    apply_hypothesis_to_catalog(catalog, hypotheses, core_ids)

    corr = next(c for c in catalog if c["id"] == "correlation")
    assert corr["tier"] == TIER_KESIN
    assert corr["hypothesis_id"] == "H1"

    kesin_before = set(pick_kesin_core_ids(uygun_candidates, planner_vars))
    for cid in kesin_before:
        item = next(c for c in catalog if c["id"] == cid)
        if item.get("cekirdek"):
            continue
        if cid == "correlation":
            continue
        assert item["tier"] != TIER_KESIN or item.get("hypothesis_id")


def test_budget_prioritizes_hypothesis_linked(uygun_candidates, planner_vars):
    selected = {c["id"] for c in uygun_candidates}
    catalog = build_test_catalog(uygun_candidates, selected, [], planner_vars)
    core_ids = core_candidate_ids(uygun_candidates)
    hypotheses = [{
        "id": "H1",
        "label": "Cinsiyete göre OYŞTÖ",
        "candidate_ids": ["ttest:cinsiyet:oys"],
    }]
    apply_hypothesis_to_catalog(catalog, hypotheses, core_ids)
    enrich_catalog_metadata(catalog, DEFAULT_LAYOUT_CONFIG, core_ids)

    working = [dict(c) for c in catalog]
    apply_table_budget(working, "oz", DEFAULT_LAYOUT_CONFIG)
    linked = next(c for c in working if c["id"] == "ttest:cinsiyet:oys")
    assert linked.get("enabled_default") is True
    assert linked.get("butce_disi") is False


@pytest.mark.asyncio
async def test_parse_research_questions_scoring(uygun_candidates, planner_vars):
    parsed, meta = await parse_research_questions(
        "Cinsiyet ile OYŞTÖ arasında fark var mı?",
        planner_vars,
        uygun_candidates,
    )
    assert meta.get("scoring_used") is True
    assert parsed["candidates"]
    oys = next(
        (c for c in parsed["candidates"] if c["id"] == "ttest:cinsiyet:oys"),
        None,
    )
    assert oys is not None
    assert oys.get("relevance_flag") == "uygun"


@pytest.mark.asyncio
async def test_translate_decision_reasons_passthrough_without_llm():
    reasons = ["Normallik sağlanamadı → Mann-Whitney seçildi"]
    with patch("hypothesis_engine.has_claude", return_value=False), \
         patch("hypothesis_engine.has_gemini_enrich", return_value=False):
        translated, meta = await translate_decision_reasons(reasons)
    assert translated == reasons
    assert meta["llm_calls"] == 0


@pytest.mark.asyncio
async def test_translate_decision_reasons_claude_mock():
    with patch("hypothesis_engine.has_claude", return_value=True), \
         patch("hypothesis_engine.has_gemini_enrich", return_value=False), \
         patch(
             "hypothesis_engine.claude_decide",
             return_value=(
                 '{"reasons":["Shapiro-Wilk sonucu normallik varsayımını karşılamadığı için Mann-Whitney U testi seçilmiştir."]}',
                 {"llm_calls": 1, "llm_provider": "anthropic"},
             ),
         ):
        translated, meta = await translate_decision_reasons(
            ["Shapiro-Wilk p=0.03 → Mann-Whitney seçildi"],
        )
    assert "Mann-Whitney" in translated[0]
    assert meta.get("llm_calls", 0) >= 1


def test_word_export_grouping_sample_first():
    results = [
        {"type": "demographics", "title": "Demo"},
        {"type": "descriptive", "title": "Tanımlayıcı"},
        {"type": "ttest", "hypothesis_id": "H1", "title": "T1"},
        {"type": "correlation_matrix", "hypothesis_id": "H2", "title": "Korelasyon"},
    ]
    hypotheses = [
        {"id": "H1", "label": "Soru 1"},
        {"id": "H2", "label": "Soru 2"},
    ]
    sections = _group_results_for_export(results, hypotheses)
    titles = [s[0] for s in sections]
    assert titles[0] == "Örnekleme İlişkin Bulgular"
    assert "Araştırma Sorusu 1'e İlişkin Bulgular" in titles
    assert "Araştırma Sorusu 2'ye İlişkin Bulgular" in titles
    sample_items = sections[0][1]
    assert len(sample_items) == 2
    assert sample_items[0][1]["type"] == "demographics"


def test_hypothesis_section_title_turkish_suffixes():
    hyp = {"id": "H1", "label": "Örnek"}
    assert _hypothesis_section_title(hyp, 2) == "Araştırma Sorusu 2'ye İlişkin Bulgular"
    assert _hypothesis_section_title(hyp, 6) == "Araştırma Sorusu 6'ya İlişkin Bulgular"
    assert _hypothesis_section_title(hyp, 1) == "Araştırma Sorusu 1'e İlişkin Bulgular"
    assert _hypothesis_section_title(hyp, 9) == "Araştırma Sorusu 9'a İlişkin Bulgular"


def test_hypothesis_linked_non_core_demotes_plain_kesin(uygun_candidates, planner_vars):
    """Hipoteze bağlanmayan kesin aday önerilen'e düşer."""
    catalog = build_test_catalog(
        uygun_candidates,
        {c["id"] for c in uygun_candidates},
        [],
        planner_vars,
    )
    core_ids = core_candidate_ids(uygun_candidates)
    ttest = next(c for c in catalog if c["id"] == "ttest:cinsiyet:sonuc")
    ttest["tier"] = TIER_KESIN

    apply_hypothesis_to_catalog(catalog, [{
        "id": "H1",
        "label": "OYŞTÖ farkı",
        "candidate_ids": ["ttest:cinsiyet:oys"],
    }], core_ids)

    sonuc_item = next(c for c in catalog if c["id"] == "ttest:cinsiyet:sonuc")
    assert sonuc_item["tier"] == TIER_ONERILEN
    assert "hypothesis_id" not in sonuc_item
