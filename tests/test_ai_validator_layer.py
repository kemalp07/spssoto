"""AI kısıtlama katmanı — validator ve deterministik pipeline testleri."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from document_parser import extract_scale_test_requirements
from etik_parser import parse_etik_to_hypotheses
from hypothesis_engine import filter_ai_hypothesis_matches
from schemas import Variable
from test_planner import validate_test_selection, build_candidate_tests, build_norm_map


def test_validate_ttest_requires_two_groups():
    grouping = Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping")
    outcome = Variable(name="oys", label="OYŞTÖ", type="continuous", role="outcome")
    ok, _ = validate_test_selection("ttest", grouping, outcome, n_groups=2)
    assert ok
    ok, msg = validate_test_selection("ttest", grouping, outcome, n_groups=3)
    assert not ok
    assert "ANOVA" in msg


def test_validate_rejects_wrong_outcome_type():
    grouping = Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping")
    outcome = Variable(name="durum", label="Durum", type="categorical", role="outcome")
    ok, msg = validate_test_selection("ttest", grouping, outcome, n_groups=2)
    assert not ok
    assert "continuous" in msg


def test_filter_ai_hypothesis_matches_drops_invalid():
    variables = [
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
        Variable(name="oys", label="OYŞTÖ", type="continuous", role="outcome"),
        Variable(name="durum", label="Durum", type="categorical", role="outcome"),
    ]
    candidates = [
        {
            "id": "ttest:cinsiyet:oys",
            "test": "ttest",
            "vars": ["cinsiyet", "oys"],
            "n_groups": 2,
        },
        {
            "id": "ttest:bad",
            "test": "ttest",
            "vars": ["cinsiyet", "durum"],
            "n_groups": 2,
        },
    ]
    hypotheses = [{
        "id": "H1",
        "label": "Test",
        "candidate_ids": ["ttest:cinsiyet:oys", "ttest:bad"],
    }]
    filtered = filter_ai_hypothesis_matches(hypotheses, variables, candidates)
    assert len(filtered) == 1
    assert filtered[0]["candidate_ids"] == ["ttest:cinsiyet:oys"]


def test_extract_scale_test_requirements_from_registry():
    anket = {"sections": [{"title": "GYA", "items": []}]}
    registry = [{
        "scale": {
            "id": "gya",
            "names": ["GYA"],
            "reverse_items": ["gya3"],
            "scale_range": [1, 5],
        },
        "matched_cols": ["gya1", "gya2", "gya3"],
    }]
    reqs = extract_scale_test_requirements(anket, registry)
    assert len(reqs["cronbach_scales"]) == 1
    assert reqs["cronbach_scales"][0]["test"] == "cronbach"
    assert reqs["cronbach_scales"][0]["items"] == ["gya1", "gya2", "gya3"]


def test_parse_etik_to_hypotheses_keyword_matching():
    rng = np.random.default_rng(1)
    n = 40
    df = pd.DataFrame({
        "cinsiyet": [1] * 20 + [2] * 20,
        "oys": rng.normal(20, 3, n),
    })
    variables = [
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
        Variable(name="oys", label="OYŞTÖ", type="continuous", role="outcome"),
    ]
    norm_map = build_norm_map(df, variables)
    candidates = build_candidate_tests(df, variables, norm_map)
    etik = "Cinsiyet grupları arasında OYŞTÖ puanlarında fark olup olmadığı incelenecektir."
    hyps = parse_etik_to_hypotheses(etik, variables, candidates)
    assert hyps
    assert any("ttest" in cid or "mann_whitney" in cid for cid in hyps[0]["candidate_ids"])
