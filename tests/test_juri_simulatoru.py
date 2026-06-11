"""Jüri simülatörü kalite kontrol testleri."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from juri_simulatoru import run_python_checks, run_quality_check


def _anova_result(
    table_no=4,
    sig=True,
    groups=None,
    grouping="bolum",
    outcome="oys",
):
    groups = groups or [
        {"name": "Hemşirelik", "n": 20, "mean": 52.1, "sd": 5.0},
        {"name": "Tıp", "n": 20, "mean": 49.6, "sd": 4.5},
    ]
    return {
        "type": "anova",
        "table_number": table_no,
        "significant": sig,
        "f": 3.445,
        "p": 0.017,
        "grouping_name": grouping,
        "outcome_name": outcome,
        "grouping_label": "Bölüm",
        "outcome_label": "OYS",
        "groups": groups,
    }


def _compact_from_results(results, bulgular=None):
    from juri_simulatoru import build_compact_input
    return build_compact_input(results, bulgular or {})


def test_sig_anova_without_posthoc_warns():
    results = [_anova_result(sig=True)]
    rows = _compact_from_results(results)
    findings = run_python_checks(rows, "", [])
    rules = {f.get("rule") for f in findings}
    assert "posthoc_missing" in rules


def test_claimed_higher_wrong_group_is_error():
    results = [_anova_result()]
    bulgu = (
        "OYS puanlarının Bölüm değişkenine göre karşılaştırılması sonucunda "
        "istatistiksel olarak anlamlı bir fark saptanmıştır; Tıp grubunun ortalaması daha yüksektir."
    )
    rows = _compact_from_results(results, {"0": bulgu})
    findings = run_python_checks(rows, "", [])
    assert any(
        f.get("rule") == "claimed_higher_mismatch" and f.get("severity") == "hata"
        for f in findings
    )


def test_intro_parametric_with_mann_whitney_is_error():
    intro = (
        "Araştırmanın örneklemini toplam 50 katılımcı (N = 50) oluşturmaktadır. "
        "Tüm sonuç değişkenlerinin normal dağılım gösterdiği saptanmıştır. "
        "Bu doğrultuda, araştırmanın amaçları kapsamında parametrik test "
        "yöntemlerinin uygulanmasına karar verilmiştir."
    )
    rows = [{
        "table_no": 2,
        "type": "mann_whitney",
        "vars": "cinsiyet×oys",
        "sig": True,
        "p": ".032",
    }]
    findings = run_python_checks(rows, intro, [])
    assert any(f.get("rule") == "intro_parametric_mismatch" for f in findings)


def test_clean_set_overall_temiz():
    intro = (
        "Araştırmanın örneklemini toplam 40 katılımcı (N = 40) oluşturmaktadır. "
        "Bu doğrultuda, araştırmanın amaçları kapsamında parametrik test "
        "yöntemlerinin uygulanmasına karar verilmiştir."
    )
    results = [
        {
            "type": "ttest",
            "table_number": 3,
            "significant": False,
            "p": 0.21,
            "grouping_name": "cinsiyet",
            "outcome_name": "oys",
            "grouping_label": "Cinsiyet",
            "outcome_label": "OYS",
            "groups": [
                {"name": "Kadın", "n": 20, "mean": 50.0},
                {"name": "Erkek", "n": 20, "mean": 49.0},
            ],
        }
    ]
    with patch("juri_simulatoru.has_claude", return_value=False):
        output, meta = run_quality_check(results, intro, [], 40, {})
    assert output["overall"] == "temiz"
    assert output["findings"] == []
    assert meta.get("python_only") is True
