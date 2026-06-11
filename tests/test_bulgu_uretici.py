"""Bulgu üretici entegrasyon testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from bulgu_uretici import build_bulgu_text
from bulgu_templates import generate_bulgu_from_template


def test_chi_square_includes_effect_size():
    result = {
        "type": "chi_square",
        "significant": True,
        "chi2": 12.45,
        "dof": 2,
        "n_total": 238,
        "p": 0.002,
        "var1": "Program",
        "var2": "Yaralanma",
        "effect_size": 0.23,
        "effect_symbol": "Cramer's V",
        "effect_interp": "zayıf",
        "dominant_row": "Fizyoterapi",
        "dominant_col": "Evet",
        "dominant_pct": 62.5,
        "dominant_n": 45,
    }
    text = generate_bulgu_from_template(result)
    assert "Cramer" in text or "V" in text
    assert "χ²" in text
    assert "p = .002" in text
    assert "Fizyoterapi" in text
    assert "%62.5" in text or "62.5" in text


def test_kruskal_includes_epsilon_squared():
    result = {
        "type": "kruskal_wallis",
        "significant": True,
        "H": 8.42,
        "p": 0.015,
        "df": 2,
        "n_total": 120,
        "epsilon_squared": 0.08,
        "grouping_label": "Bölüm",
        "outcome_label": "OYS",
        "groups": [
            {"name": "A", "median": 40.0, "n": 40},
            {"name": "B", "median": 45.0, "n": 40},
            {"name": "C", "median": 50.0, "n": 40},
        ],
    }
    text = build_bulgu_text(result)
    assert "ε²" in text
    assert "8.42" in text


def test_multiple_regression_lists_predictors():
    result = {
        "type": "multiple_regression",
        "significant": True,
        "outcome": "Puan",
        "r_squared": 0.141,
        "adj_r_squared": 0.130,
        "f": 12.84,
        "p": 0.001,
        "df1": 3,
        "df2": 234,
        "max_vif": 1.45,
        "coefficients": [
            {"label": "Yaş", "beta": 0.28, "t": 4.12, "p": 0.001, "significant": True},
            {"label": "Eğitim", "beta": 0.19, "t": 2.85, "p": 0.005, "significant": True},
            {"label": "Deneyim", "beta": -0.05, "t": -0.75, "p": 0.454, "significant": False},
        ],
    }
    text = build_bulgu_text(result)
    assert "Yaş" in text
    assert "β" in text
    assert "VIF" in text or "doğrusallık" in text


def test_regression_includes_beta_and_t():
    result = {
        "type": "regression",
        "significant": True,
        "predictor": "BKİ",
        "outcome": "Puan",
        "r_squared": 0.061,
        "beta": 0.45,
        "t": 3.93,
        "p": 0.0002,
        "n": 237,
    }
    text = build_bulgu_text(result)
    assert "β" in text
    assert "p < .001" in text


def test_descriptive_with_iqr():
    result = {
        "type": "descriptive",
        "variables_stats": [{
            "label": "OYS",
            "n": 50,
            "mean": 45.2,
            "sd": 6.1,
            "median": 44.0,
            "iqr": 8.0,
            "theory": "12 – 60",
        }],
    }
    text = build_bulgu_text(result)
    assert "IQR" in text
    assert "12 – 60" in text
