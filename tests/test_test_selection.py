"""Deterministik test seçimi ve bağlam puanlama testleri."""
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from schemas import Variable
from test_planner import (
    _build_comparison_decision_log,
    build_candidate_tests,
    build_norm_map,
    format_methodology_paragraph,
    score_candidates_from_context,
)
from word_export import build_word_document


def _group_df(
    n_per_group: int,
    n_groups: int,
    outcome_fn,
    seed: int = 42,
) -> tuple[pd.DataFrame, list]:
    rng = np.random.default_rng(seed)
    rows = []
    grouping = []
    for g in range(1, n_groups + 1):
        vals = outcome_fn(rng, g)
        rows.extend(vals)
        grouping.extend([g] * n_per_group)
    df = pd.DataFrame({
        "cinsiyet": grouping,
        "sonuc": rows,
    })
    vars_ = [
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
        Variable(name="sonuc", label="Sonuç", type="continuous", role="outcome"),
    ]
    return df, vars_


def test_n300_two_groups_normal_selects_ttest_with_shapiro_reason():
    df, vars_ = _group_df(
        150, 2,
        lambda rng, g: rng.normal(50 + g, 5, 150).tolist(),
    )
    norm_map = build_norm_map(df, vars_)
    cv, sv = vars_[0], vars_[1]
    test, log = _build_comparison_decision_log(df, cv, sv, norm_map, 2)
    assert test == "ttest"
    assert log["normality_test"] == "lilliefors"
    assert log["normality_p"] is not None
    assert "normallik" in log["reason"].lower()
    assert log["normality_passed"] is True


def test_n300_two_groups_nonnormal_selects_mann_whitney():
    df, vars_ = _group_df(
        150, 2,
        lambda rng, g: rng.exponential(2 + g * 0.1, 150).tolist(),
    )
    norm_map = build_norm_map(df, vars_)
    test, log = _build_comparison_decision_log(df, vars_[0], vars_[1], norm_map, 2)
    assert test == "mann_whitney"
    assert log["selected_test"] == "mann_whitney"
    assert log["normality_passed"] is False
    assert "Mann-Whitney" in log["reason"]


def test_n300_three_groups_normal_equal_variance_anova():
    df, vars_ = _group_df(
        100, 3,
        lambda rng, g: rng.normal(40 + g, 5, 100).tolist(),
    )
    norm_map = build_norm_map(df, vars_)
    test, log = _build_comparison_decision_log(df, vars_[0], vars_[1], norm_map, 3)
    assert test == "anova"
    assert log["levene_passed"] is True
    assert log["welch"] is False


def test_n300_three_groups_normal_unequal_variance_welch_note():
    df, vars_ = _group_df(
        100, 3,
        lambda rng, g: rng.normal(40 + g, 2 + g * 4, 100).tolist(),
    )
    norm_map = build_norm_map(df, vars_)
    test, log = _build_comparison_decision_log(df, vars_[0], vars_[1], norm_map, 3)
    assert test == "anova"
    assert log["levene_passed"] is False
    assert log["welch"] is True
    assert "Games-Howell" in log["reason"]


def test_etik_cinsiyet_oysto_marks_candidate_uygun():
    candidates = [
        {
            "id": "ttest:cinsiyet:oys",
            "test": "ttest",
            "vars": ["cinsiyet", "oys"],
            "auto_flag": "uygun",
            "seq": "t1",
        },
        {
            "id": "ttest:cinsiyet:gya",
            "test": "ttest",
            "vars": ["cinsiyet", "gya"],
            "auto_flag": "uygun",
            "seq": "t2",
        },
    ]
    labels = {"cinsiyet": "Cinsiyet", "oys": "OYŞTÖ", "gya": "GYA"}
    etik = "Cinsiyet ile OYŞTÖ puanları arasında fark var mıdır?"
    scored = score_candidates_from_context(candidates, etik, labels)
    oys = next(c for c in scored if c["id"] == "ttest:cinsiyet:oys")
    gya = next(c for c in scored if c["id"] == "ttest:cinsiyet:gya")
    assert oys["relevance_flag"] == "uygun"
    assert oys["relevance_score"] >= 2
    assert "oys" in oys["vars"]


def test_no_etik_all_uygun_equal_score():
    candidates = [
        {"id": "a", "test": "ttest", "vars": ["x", "y"], "auto_flag": "uygun", "seq": "t1"},
        {"id": "b", "test": "anova", "vars": ["x", "z"], "auto_flag": "uygun", "seq": "t2"},
    ]
    scored = score_candidates_from_context(candidates, "", {"x": "X", "y": "Y", "z": "Z"})
    assert all(c["relevance_flag"] == "uygun" for c in scored)
    assert all(c["relevance_score"] == 2 for c in scored)


def test_word_export_methodology_section_from_decision_log():
    decision_log = {
        "normality_test": "shapiro-wilk",
        "normality_p": 0.03,
        "normality_passed": False,
        "levene_p": None,
        "levene_passed": None,
        "selected_test": "mann_whitney",
        "reason": "Shapiro-Wilk p=0.03 < 0.05 → Mann-Whitney seçildi",
    }
    paragraph = format_methodology_paragraph(
        decision_log,
        {"sonuc": "OYŞTÖ"},
        ["cinsiyet", "sonuc"],
    )
    assert "OYŞTÖ" in paragraph
    assert "Shapiro-Wilk" in paragraph
    assert "Mann-Whitney" in paragraph

    doc = build_word_document(
        [],
        methodology=[{"vars": ["cinsiyet", "sonuc"], "decision_log": decision_log}],
        label_map={"sonuc": "OYŞTÖ"},
    )
    import zipfile
    import io as _io
    with zipfile.ZipFile(_io.BytesIO(doc)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "statistiksel" in xml.lower() or "Mann-Whitney" in xml


def test_normality_reason_uses_normal_flag_not_p_threshold():
    """n>200 skew/kurt kuralında p düşük olsa bile normal=True ise ≥ 0.05 yazılmamalı."""
    norm_map = {
        "sonuc": {
            "normal": True,
            "is_parametric": True,
            "p": 0.005,
            "test": "Kolmogorov-Smirnov",
        },
    }
    df, vars_ = _group_df(150, 2, lambda rng, g: rng.normal(50, 5, 150).tolist())
    _, log = _build_comparison_decision_log(df, vars_[0], vars_[1], norm_map, 2)
    assert "≥ 0.05" not in log["reason"]
    assert "< 0.05" not in log["reason"]
    assert "p=0.005" in log["reason"]
    assert "normallik sağlandı" in log["reason"]


def test_build_candidate_tests_includes_decision_log(planner_df=None):
    rng = np.random.default_rng(1)
    n = 60
    df = pd.DataFrame({
        "cinsiyet": [1] * 30 + [2] * 30,
        "oys": rng.normal(20, 3, n),
    })
    vars_ = [
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
        Variable(name="oys", label="OYŞTÖ", type="continuous", role="outcome"),
    ]
    norm_map = build_norm_map(df, vars_)
    candidates = build_candidate_tests(df, vars_, norm_map)
    ttest = next(c for c in candidates if c["test"] in ("ttest", "mann_whitney"))
    assert "decision_log" in ttest
    assert ttest.get("reason")
