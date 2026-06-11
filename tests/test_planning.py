"""Test planlama katmanı birim testleri (LLM mock)."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from schemas import Variable
from test_planner import (
    apply_deterministic_flags,
    build_candidate_tests,
    build_norm_map,
    format_reason,
    make_candidate_id,
    plan_tests,
)


@pytest.fixture
def planner_df() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 40
    sex = [1] * 36 + [2] * 4
    return pd.DataFrame({
        "cinsiyet": sex,
        "bolum": rng.choice([1, 2, 3], size=n),
        "neq1": rng.integers(1, 6, n),
        "neq2": rng.integers(1, 6, n),
        "neq_toplam": rng.integers(10, 30, n),
        "sonuc": rng.normal(50, 5, n),
    })


@pytest.fixture
def planner_vars() -> list:
    return [
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
        Variable(name="bolum", label="Bölüm", type="categorical", role="grouping"),
        Variable(name="neq1", label="NEQ Madde 1", type="continuous", role="outcome"),
        Variable(name="neq2", label="NEQ Madde 2", type="continuous", role="outcome"),
        Variable(name="neq_toplam", label="NEQ Toplam", type="continuous", role="outcome"),
        Variable(name="sonuc", label="Sonuç", type="continuous", role="outcome"),
    ]


def test_yetersiz_n_flag(planner_df, planner_vars):
    norm_map = build_norm_map(planner_df, planner_vars)
    candidates = build_candidate_tests(planner_df, planner_vars, norm_map)
    flagged = apply_deterministic_flags(planner_df, planner_vars, candidates)
    ttest_cands = [
        c for c in flagged
        if c["test"] in ("ttest", "mann_whitney") and "cinsiyet" in c["vars"]
    ]
    assert ttest_cands
    assert any(c["auto_flag"] == "yetersiz_n" for c in ttest_cands)


def test_totoloji_flag_on_subscale_total_correlation(planner_df, planner_vars):
    candidates = [{
        "id": "correlation",
        "test": "correlation",
        "vars": ["neq1", "neq_toplam", "sonuc"],
        "auto_flag": "uygun",
    }]
    flagged = apply_deterministic_flags(planner_df, planner_vars, candidates)
    assert flagged[0]["auto_flag"] == "totoloji"


def test_cift_test_flag_same_pair(planner_df, planner_vars):
    candidates = [
        {
            "id": "chi_square:g:o", "test": "chi_square", "vars": ["cinsiyet", "sonuc"],
            "min_group_n": 20, "auto_flag": "uygun",
        },
        {
            "id": "ttest:g:o", "test": "ttest", "vars": ["cinsiyet", "sonuc"],
            "min_group_n": 20, "auto_flag": "uygun",
        },
    ]
    flagged = apply_deterministic_flags(planner_df, planner_vars, candidates)
    assert all(c["auto_flag"] == "cift_test" for c in flagged)


def test_format_reason_yetersiz_n(planner_vars):
    cand = {"vars": ["cinsiyet", "sonuc"], "min_group_n": 4}
    text = format_reason("yetersiz_n", cand, planner_vars)
    assert "n=4" in text


def test_make_candidate_id():
    assert make_candidate_id("ttest", ["a", "b"]) == "ttest:a:b"
    assert make_candidate_id("descriptive", ["x"]) == "descriptive"


@pytest.mark.asyncio
async def test_plan_tests_without_llm(planner_df, planner_vars):
    recommended, excluded, meta = await plan_tests(
        planner_df, planner_vars, "NEQ ve cinsiyet ilişkisi", use_ai=False,
    )
    assert recommended
    assert meta["llm_calls"] == 0
    assert any(c["auto_flag"] != "uygun" for c in excluded) or excluded


@pytest.mark.asyncio
async def test_plan_tests_llm_mocked(planner_df, planner_vars):
    mock_selection = {
        "selected": [make_candidate_id("descriptive", ["neq_toplam"])],
        "excluded": [],
    }
    with patch(
        "test_planner.select_tests_with_llm",
        new=AsyncMock(return_value=(mock_selection, {"llm_calls": 1, "approx_input_tokens": 120, "approx_output_tokens": 40})),
    ):
        recommended, excluded, meta = await plan_tests(
            planner_df, planner_vars, "Tanımlayıcı analiz", use_ai=True,
        )
    assert meta["llm_calls"] == 1
    assert any(t["id"] == "descriptive" for t in recommended)
