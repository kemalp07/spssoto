"""Şablon bulgu testleri."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from bulgu_templates import (
    _p_txt,
    generate_bulgu_from_template,
    has_bulgu_template,
)
from stat_tests import TableCounter, table_ttest, table_anova, table_mann_whitney, table_kruskal


def _ttest_result_fixture():
    """Gerçek tablo satırları: sütun 0 ölçek etiketi — grup adı sütun 1'de."""
    return {
        "type": "ttest",
        "significant": True,
        "t": 2.45,
        "p": 0.021,
        "cohens_d": 0.62,
        "df": 38,
        "grouping_label": "Cinsiyet",
        "outcome_label": "Puan A",
        "groups": [
            {"name": "Kadın", "n": 20, "mean": 75.2, "sd": 8.1, "median": 74.0},
            {"name": "Erkek", "n": 18, "mean": 68.4, "sd": 7.5, "median": 68.0},
        ],
        "rows": [
            ["Puan A", "Kadın", "20", "75.2 ± 8.1", "2.45", "38", ".021*", "0.62"],
            ["Puan A", "Erkek", "18", "68.4 ± 7.5", "", "", "", ""],
        ],
    }


def test_p_txt_gte_001():
    assert _p_txt(0.021) == "p = .021"


def test_p_txt_lt_001():
    assert _p_txt(0.0005) == "p < .001"
    assert "p = <" not in _p_txt(0.0005)


def test_ttest_uses_structural_groups_not_scale_label():
    result = _ttest_result_fixture()
    text = generate_bulgu_from_template(result)
    assert text
    assert "Kadın" in text
    assert "Erkek" not in text or "daha yüksek" in text
    assert "Puan A grubunun" not in text
    assert "Cinsiyet" in text
    assert "gruplara göre" not in text
    assert "p = .021" in text
    assert "*" not in text


def test_ttest_p_lt_001_in_bulgu():
    result = _ttest_result_fixture()
    result["p"] = 0.0003
    text = generate_bulgu_from_template(result)
    assert "p < .001" in text
    assert "p = <" not in text
    assert "*" not in text


def test_anova_grouping_label_and_no_table_number():
    result = {
        "type": "anova",
        "significant": True,
        "f": 4.2,
        "p": 0.015,
        "eta_squared": 0.12,
        "grouping_label": "Bölüm",
        "outcome_label": "Puan A",
        "title": "Tablo 2. Katılımcıların Puan A Değerlerinin Bölüm Gruplarına Göre Karşılaştırılması",
        "groups": [
            {"name": "1", "n": 10, "mean": 70.0, "sd": 5.0, "median": 69.0},
            {"name": "2", "n": 10, "mean": 75.0, "sd": 5.0, "median": 74.0},
        ],
    }
    text = generate_bulgu_from_template(result)
    assert "Bölüm" in text
    assert "Puan A" in text
    assert "Tablo 2" not in text
    assert "gruplara göre" not in text
    assert "ANOVA ile karşılaştırılması" in text
    assert "p = .015" in text


def test_mann_whitney_grouping_and_p_display():
    result = {
        "type": "mann_whitney",
        "significant": True,
        "U": 120.0,
        "z": 2.1,
        "p": 0.0008,
        "r": 0.35,
        "grouping_label": "Cinsiyet",
        "outcome_label": "Puan B",
        "groups": [
            {"name": "1", "n": 15, "mean": 72.0, "sd": 6.0, "median": 71.0},
            {"name": "2", "n": 15, "mean": 68.0, "sd": 6.0, "median": 65.0},
        ],
    }
    text = generate_bulgu_from_template(result)
    assert "Cinsiyet" in text
    assert "Puan B" in text
    assert "p < .001" in text
    assert "gruplara göre" not in text
    assert "*" not in text


def test_kruskal_grouping_label():
    result = {
        "type": "kruskal_wallis",
        "significant": False,
        "H": 3.2,
        "p": 0.12,
        "grouping_label": "Bölüm",
        "outcome_label": "Puan A",
        "groups": [],
    }
    text = generate_bulgu_from_template(result)
    assert "Bölüm" in text
    assert "gruplara göre" not in text
    assert "p = .120" in text or "p = .12" in text


def test_tukey_uses_significant_pairs_without_stars():
    result = {
        "type": "tukey",
        "grouping_label": "Bölüm",
        "outcome_label": "Puan A",
        "significant_pairs": [
            {"group_i": "A", "group_j": "B", "p": 0.003, "mean_diff": 5.2},
        ],
    }
    text = generate_bulgu_from_template(result)
    assert "A grubunun puanları B grubundan daha yüksektir" in text
    assert "p = .003" in text
    assert "p = <" not in text
    assert "*" not in text


def test_chi_square_p_display():
    result = {
        "type": "chi_square",
        "significant": True,
        "var1": "Cinsiyet",
        "var2": "Bölüm",
        "chi2": 5.4,
        "p": 0.02,
    }
    text = generate_bulgu_from_template(result)
    assert "p = .020" in text or "p = .02" in text
    assert "*" not in text


def test_regression_p_display():
    result = {
        "type": "regression",
        "significant": True,
        "predictor": "BKİ",
        "outcome": "Puan",
        "r_squared": 0.15,
        "p": 0.0002,
    }
    text = generate_bulgu_from_template(result)
    assert "p < .001" in text
    assert "*" not in text


def test_paired_ttest_p_display():
    result = {
        "type": "paired_ttest",
        "significant": True,
        "var1": "Ön test",
        "var2": "Son test",
        "t": 2.1,
        "p": 0.04,
        "cohens_d": 0.5,
        "mean_diff": 3.2,
    }
    text = generate_bulgu_from_template(result)
    assert "p = .040" in text or "p = .04" in text
    assert "*" not in text


def test_descriptive_template():
    result = {
        "type": "descriptive",
        "rows": [["NEQ", "30", "45.2 ± 6.1", "44.0", "12 – 60", "5 – 25"]],
    }
    text = generate_bulgu_from_template(result)
    assert "45.2" in text
    assert "hesaplanmıştır" in text


def test_ttest_from_stat_tests_has_structural_fields(sample_df, cat_cv, cont_sv):
    tc = TableCounter()
    res = table_ttest(tc, sample_df, cat_cv, cont_sv)
    assert "groups" in res
    assert len(res["groups"]) == 2
    assert res["grouping_label"] == "Cinsiyet"
    assert res["outcome_label"] == "Puan A"
    assert res["groups"][0]["name"] != res["outcome_label"]
    text = generate_bulgu_from_template(res)
    assert res["grouping_label"] in text
    assert "*" not in text


def test_anova_from_stat_tests(sample_df, cat_cv3, cont_sv):
    tc = TableCounter()
    res = table_anova(tc, sample_df, cat_cv3, cont_sv)
    assert res["grouping_label"] == "Bölüm"
    text = generate_bulgu_from_template(res)
    assert "Bölüm" in text
    assert "Tablo" not in text


@pytest.mark.parametrize("factory, cv, sv", [
    (table_mann_whitney, "cat_cv", "cont_sv_b"),
    (table_kruskal, "cat_cv3", "cont_sv"),
])
def test_group_tests_expose_labels(factory, cv, sv, sample_df, request):
    cv_obj = request.getfixturevalue(cv)
    sv_obj = request.getfixturevalue(sv)
    tc = TableCounter()
    res = factory(tc, sample_df, cv_obj, sv_obj)
    assert "grouping_label" in res
    assert "outcome_label" in res
    assert "groups" in res
    text = generate_bulgu_from_template(res)
    assert res["grouping_label"] in text
    assert "gruplara göre" not in text
