"""Türev değişken tespiti ve hipotez özet satırı testleri."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from data_profile import find_derived_variables
from hypothesis_engine import (
    enrich_hypotheses_for_display,
    filter_unmatched_for_display,
    hypothesis_summary_line,
)
from schemas import Variable


@pytest.fixture
def yas_df() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 50
    yas = rng.integers(18, 65, n)
    yas_grubu = pd.cut(yas, bins=[0, 30, 45, 100], labels=[1, 2, 3]).astype(int)
    yas_binary = (yas >= 30).astype(int)
    return pd.DataFrame({
        "yas": yas,
        "yas_grubu": yas_grubu,
        "yas_binary": yas_binary,
        "sonuc": rng.normal(50, 5, n),
    })


@pytest.fixture
def yas_vars() -> list:
    return [
        Variable(name="yas", label="Yaş", type="continuous", role="outcome"),
        Variable(name="yas_grubu", label="Yaş Grubu", type="categorical", role="outcome"),
        Variable(name="yas_binary", label="Yaş Binary", type="categorical", role="outcome"),
        Variable(name="sonuc", label="Sonuç", type="continuous", role="outcome"),
    ]


def test_find_derived_yas_grubu_high_confidence(yas_df, yas_vars):
    derived = find_derived_variables(yas_df, yas_vars)
    by_name = {d["name"]: d for d in derived}
    assert "yas_grubu" in by_name
    assert by_name["yas_grubu"]["source"] == "yas"
    assert by_name["yas_grubu"]["confidence"] == "high"
    assert by_name["yas_grubu"]["action"] == "move_to_grouping"
    assert by_name["yas_grubu"]["recommended_role"] == "grouping"


def test_find_derived_binary_exclude_action(yas_df, yas_vars):
    derived = find_derived_variables(yas_df, yas_vars)
    binary = next(d for d in derived if d["name"] == "yas_binary")
    assert binary["kind"] == "binary"
    assert binary["action"] == "exclude"
    assert binary["recommended_role"] is None


def test_hypothesis_summary_line_shows_test_names():
    candidates = [
        {"id": "correlation", "test": "correlation", "label": "Korelasyon Matrisi"},
        {
            "id": "ttest:cinsiyet:oys",
            "test": "ttest",
            "label": "t-Testi — Cinsiyet × OYS",
        },
        {
            "id": "anova:bolum:oys",
            "test": "anova",
            "label": "ANOVA — Bölüm × OYS",
        },
    ]
    by_id = {c["id"]: c for c in candidates}
    h1 = hypothesis_summary_line(
        {"id": "H1", "candidate_ids": ["correlation"]}, by_id,
    )
    h3 = hypothesis_summary_line(
        {"id": "H3", "candidate_ids": ["ttest:cinsiyet:oys"]}, by_id,
    )
    assert "H1 → Korelasyon" in h1
    assert "H3 → t-Testi" in h3
    assert "Cinsiyet" in h3 or "OYS" in h3


def test_filter_unmatched_hides_core_table_questions():
    unmatched = [
        "Demografik frekans tablosu",
        "Cinsiyete göre OYS farkı",
    ]
    shown = filter_unmatched_for_display(unmatched)
    assert "Demografik frekans tablosu" not in shown
    assert "Cinsiyete göre OYS farkı" in shown


def test_enrich_hypotheses_adds_summary():
    candidates = [{"id": "c1", "test": "ttest", "label": "t-Testi — A × B"}]
    out = enrich_hypotheses_for_display(
        [{"id": "H1", "label": "Soru", "candidate_ids": ["c1"]}],
        candidates,
    )
    assert out[0]["summary"].startswith("H1 →")
