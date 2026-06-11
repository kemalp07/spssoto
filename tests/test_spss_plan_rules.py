"""Genel plan öncelik kuralları — ölçek/değişken adından bağımsız."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from conftest import make_variables
from schemas import Variable
from test_planner import (
    apply_deterministic_flags,
    build_candidate_tests,
    build_norm_map,
    chi_square_allowed,
    is_derived_categorical_name,
    is_redundant_derived_categorical,
    plan_tests,
)


@pytest.fixture
def generic_df() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 120
    return pd.DataFrame({
        "grp_a": rng.choice([1, 2, 3], n),
        "grp_b": rng.choice([1, 2], n),
        "age_bin": rng.choice([1, 2, 3], n),
        "scale_x_total": rng.normal(50, 10, n),
        "scale_x_group": rng.choice([0, 1], n),
        "scale_x_binary": rng.choice([0, 1], n),
        "scale_y_total": rng.normal(30, 5, n),
        "scale_y_total_cat": rng.choice([1, 2, 3], n),
        "anthro_cat": rng.choice([1, 2, 3, 4], n),
        "grp_extra_1": rng.choice([1, 2], n),
        "grp_extra_2": rng.choice([1, 2], n),
        "grp_extra_3": rng.choice([1, 2], n),
        "grp_extra_4": rng.choice([1, 2], n),
        **{f"scale_x_{i}": rng.integers(1, 6, n) for i in range(1, 4)},
    })


@pytest.fixture
def generic_vars() -> list:
    specs = [
        ("grp_a", "categorical", "grouping"),
        ("grp_b", "categorical", "grouping"),
        ("age_bin", "categorical", "grouping"),
        ("grp_extra_1", "categorical", "grouping"),
        ("grp_extra_2", "categorical", "grouping"),
        ("grp_extra_3", "categorical", "grouping"),
        ("grp_extra_4", "categorical", "grouping"),
        ("scale_x_total", "continuous", "outcome"),
        ("scale_y_total", "continuous", "outcome"),
        ("scale_x_group", "categorical", "outcome"),
        ("scale_x_binary", "categorical", "outcome"),
        ("scale_y_total_cat", "categorical", "outcome"),
        ("anthro_cat", "categorical", "outcome"),
    ]
    return [
        Variable(name=n, label=n, type=t, role=r, included=True)
        for n, t, r in specs
    ] + make_variables([f"scale_x_{i}" for i in range(1, 4)], role="outcome")


def test_derived_categorical_suffix_detection():
    assert is_derived_categorical_name("scale_a_group")
    assert is_derived_categorical_name("scale_a_binary")
    assert is_derived_categorical_name("foo_kategori")
    assert not is_derived_categorical_name("grp_a")


def test_redundant_binary_when_group_exists():
    cols = {"scale_x_total", "scale_x_group", "scale_x_binary"}
    groups = {}
    assert is_redundant_derived_categorical("scale_x_binary", cols, groups)
    assert not is_redundant_derived_categorical("scale_x_group", cols, groups)


def test_chi_square_requires_grouping_role(generic_vars):
    vmap = {v.name: v for v in generic_vars}
    cols = set(vmap)
    assert not chi_square_allowed(vmap["grp_a"], vmap["grp_b"], cols, {})
    assert chi_square_allowed(vmap["grp_a"], vmap["scale_y_total_cat"], cols, {})
    assert not chi_square_allowed(
        vmap["scale_x_group"], vmap["scale_x_binary"], cols, {},
    )


def test_scale_items_excluded_from_group_comparisons(generic_df, generic_vars):
    norm_map = build_norm_map(generic_df, generic_vars)
    candidates = build_candidate_tests(generic_df, generic_vars, norm_map)
    group_tests = [
        c for c in candidates
        if c["test"] in ("ttest", "mann_whitney", "anova", "kruskal_wallis")
    ]
    outcome_vars = {pair[1] for c in group_tests for pair in [c["vars"]]}
    assert "scale_x_1" not in outcome_vars
    assert "scale_x_total" in outcome_vars


def test_redundant_derived_skipped_in_frequency(generic_df, generic_vars):
    norm_map = build_norm_map(generic_df, generic_vars)
    candidates = build_candidate_tests(generic_df, generic_vars, norm_map)
    freq_vars = {c["vars"][0] for c in candidates if c["test"] == "frequency"}
    assert "scale_x_binary" not in freq_vars
    assert "grp_a" in freq_vars


def test_supplementary_grouping_omitted_from_comparisons(generic_df, generic_vars):
    norm_map = build_norm_map(generic_df, generic_vars)
    candidates = build_candidate_tests(generic_df, generic_vars, norm_map)
    compare_tests = (
        "chi_square", "ttest", "mann_whitney", "anova", "kruskal_wallis",
    )
    late = [
        c for c in candidates
        if c["test"] in compare_tests and c["vars"][0] == "grp_extra_4"
    ]
    assert not late


def test_raw_age_frequency_flagged_when_binned_age_exists(generic_df):
    rng = np.random.default_rng(1)
    n = len(generic_df)
    df = generic_df.copy()
    df["age_raw"] = rng.integers(18, 40, n)
    vars_ = [
        Variable(name="age_bin", label="Yaş grubu", type="categorical", role="grouping"),
        Variable(name="age_raw", label="Yaş", type="categorical", role="grouping"),
        Variable(name="scale_x_total", label="X", type="continuous", role="outcome"),
    ]
    norm_map = build_norm_map(df, vars_)
    candidates = build_candidate_tests(df, vars_, norm_map)
    flagged = apply_deterministic_flags(df, vars_, candidates)
    age_freq = next(
        c for c in flagged
        if c["test"] == "frequency" and c["vars"] == ["age_raw"]
    )
    assert age_freq["auto_flag"] == "tekrarli_demografi"


@pytest.mark.asyncio
async def test_plan_keeps_core_analyses_for_any_scale(generic_df, generic_vars):
    recommended, excluded, _catalog, meta = await plan_tests(
        generic_df, generic_vars, "", use_ai=False,
    )
    ids = {c["id"] for c in recommended}
    assert "descriptive" in ids
    assert "correlation" in ids
    assert any(i.startswith("chi_square:grp_a:") for i in ids)
    assert "anova:grp_a:scale_x_total" in ids
    assert meta["llm_calls"] == 0
    assert len(recommended) <= meta["uygun_count"]
    assert not any(
        c["vars"][0] == "grp_extra_4"
        for c in recommended
        if c["test"] in ("ttest", "mann_whitney", "anova", "kruskal_wallis", "chi_square")
    )
