"""Ortak yorum motoru testleri."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from yorum_motoru import (
    append_posthoc_to_text,
    clean_label_text,
    cronbach_tier,
    cronbach_warning,
    find_posthoc_for_result,
    format_correlation_pair,
    generate_template_summary,
    highest_group_name,
    p_txt,
    tukey_pair_text,
    validate_bulgu_text,
)
from bulgu_templates import generate_bulgu_from_template


def test_p_txt_formats():
    assert p_txt(0.021) == "p = .021"
    assert p_txt(0.0005) == "p < .001"


def test_cronbach_tiers():
    assert cronbach_tier(0.92) == "Mükemmel"
    assert cronbach_tier(0.85) == "Çok İyi"
    assert cronbach_tier(0.75) == "İyi"
    assert cronbach_tier(0.65) == "Kabul Edilebilir"
    assert cronbach_tier(0.55) == "Düşük"


def test_cronbach_warning_low_alpha():
    assert cronbach_warning(0.55) is not None
    assert cronbach_warning(0.85) is None


def test_clean_duplicate_puanlari():
    assert "Puanları Puanları" not in clean_label_text("OYS Puanları Puanları")


def test_highest_group_across_three():
    groups = [
        {"name": "A", "mean": 10},
        {"name": "B", "mean": 15},
        {"name": "C", "mean": 12},
    ]
    assert highest_group_name(groups, "mean") == "B"


def test_tukey_pair_direction():
    pair = {"group_i": "Hemşirelik", "group_j": "Tıp", "p": 0.01, "mean_diff": 2.5}
    text = tukey_pair_text(pair)
    assert "Hemşirelik" in text
    assert "Tıp" in text
    assert "daha yüksektir" in text


def test_correlation_includes_direction_and_strength():
    pair = {"var_i": "A", "var_j": "B", "r": 0.45, "p": 0.02, "symbol": "r"}
    text = format_correlation_pair(pair)
    assert "pozitif" in text
    assert "orta düzeyde" in text
    assert "r²" in text


def test_anova_appends_posthoc():
    anova = {
        "type": "anova",
        "significant": True,
        "f": 4.2,
        "p": 0.015,
        "grouping_name": "bolum",
        "outcome_name": "oys",
        "grouping_label": "Bölüm",
        "outcome_label": "OYS",
        "groups": [
            {"name": "A", "mean": 70},
            {"name": "B", "mean": 75},
        ],
    }
    tukey = {
        "type": "tukey",
        "grouping_name": "bolum",
        "outcome_name": "oys",
        "significant_pairs": [
            {"group_i": "A", "group_j": "B", "p": 0.01, "mean_diff": -5.0},
        ],
    }
    base = "ANOVA sonucu anlamlı."
    text = append_posthoc_to_text(base, anova, [anova, tukey])
    assert "Tukey" in text
    assert "B grubunun puanları" in text


def test_validate_bulgu_sig_mismatch():
    result = {
        "type": "ttest",
        "significant": True,
        "p": 0.02,
        "table_number": 3,
        "groups": [
            {"name": "Kadın", "mean": 75},
            {"name": "Erkek", "mean": 68},
        ],
    }
    bad = "gruplar arasında anlamlı fark saptanmamıştır."
    issues = validate_bulgu_text(result, bad)
    assert any(i["rule"] == "bulgu_sig_mismatch" for i in issues)


def test_generate_bulgu_no_duplicate_puanlari():
    result = {
        "type": "ttest",
        "significant": False,
        "t": 1.1,
        "p": 0.28,
        "cohens_d": 0.2,
        "df": 38,
        "grouping_label": "Cinsiyet",
        "outcome_label": "OYS Toplam Puanları",
        "groups": [
            {"name": "Kadın", "n": 20, "mean": 75.2},
            {"name": "Erkek", "n": 18, "mean": 68.4},
        ],
    }
    text = generate_bulgu_from_template(result)
    assert text
    assert "Puanları Puanları" not in text


def test_template_summary_includes_posthoc_note():
    summaries = [{
        "test": "anova",
        "vars": "Bölüm×OYS",
        "sig": True,
        "posthoc_present": True,
        "posthoc_sig_pairs": 0,
    }]
    text = generate_template_summary(summaries)
    assert "post-hoc" in text.lower()
