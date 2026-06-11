"""Tablo düzeni birleştirme testleri."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from layout_config import LayoutConfig
from table_layout import (
    correlation_lower_triangle,
    merge_cronbach_results,
    merge_demographic_frequencies,
    merge_ttest_tables,
    move_normality_to_descriptive_footnote,
    normalize_table_layout,
    scale_label_from_items,
)
from bulgu_templates import generate_bulgu_from_template


def _cronbach_table(scale: str, k: int, n: int, alpha: str, interp: str, table_no: int = 3):
    return {
        "type": "cronbach",
        "table_number": table_no,
        "title": f"Tablo {table_no}. Ölçek Güvenilirlik Analizi — {scale}",
        "headers": ["Ölçek", "Madde Sayısı", "Geçerli n", "Cronbach α", "Değerlendirme"],
        "rows": [[scale, k, n, alpha, interp]],
        "note": "Not.",
        "alpha": float(alpha),
        "n_items": k,
        "interpretation": interp,
        "scale_label": scale,
        "items": [f"X_{i}" for i in range(1, k + 1)],
    }


def _freq_table(label: str, rows, table_no: int = 1, is_demographic: bool = True):
    return {
        "type": "frequency",
        "table_number": table_no,
        "title": f"Tablo {table_no}. {label} Dağılımı",
        "headers": ["Değişken", "Kategori", "n", "%"],
        "rows": rows,
        "note": "Not.",
        "variable": label,
        "is_demographic": is_demographic,
        "n": 100,
    }


def test_scale_label_from_items():
    assert scale_label_from_items(["OYS_1", "OYS_2"]) == "OYS"
    assert scale_label_from_items(["SBITO_3"]) == "SBITO"


def test_merge_three_cronbach_into_one():
    tables = [
        _cronbach_table("OYS", 15, 300, "0.892", "İyi", 3),
        _cronbach_table("NEQ", 10, 298, "0.845", "İyi", 4),
        _cronbach_table("SBITO", 5, 300, "0.781", "İyi", 5),
    ]
    merged = merge_cronbach_results(tables)
    assert merged is not None
    assert merged.get("combined") is True
    assert len(merged["rows"]) == 3
    assert merged["headers"][0] == "Ölçek"
    assert "Ölçeklerin Güvenilirlik" in merged["title"]


def test_merge_demographic_frequencies():
    t1 = _freq_table("Bölüm", [
        ["Bölüm", "Hemşirelik", "40", "40.0"],
        ["Bölüm", "Ebelik", "60", "60.0"],
        ["Bölüm", "Toplam", "100", "100.0"],
    ], 1)
    t2 = _freq_table("Cinsiyet", [
        ["Cinsiyet", "Kadın", "70", "70.0"],
        ["Cinsiyet", "Erkek", "30", "30.0"],
        ["Cinsiyet", "Toplam", "100", "100.0"],
    ], 2)
    merged = merge_demographic_frequencies([t1, t2])
    assert merged is not None
    assert merged["type"] == "demographics"
    assert "Sosyodemografik" in merged["title"]
    assert merged["headers"] == ["Özellik", "f", "%"]
    assert any("Bölüm" in row[0] for row in merged["rows"])
    assert any("Erkek" in row[0] for row in merged["rows"])
    assert len(merged["rows"]) >= 4


def test_correlation_lower_triangle():
    result = {
        "type": "correlation_matrix",
        "headers": ["Değişken", "1", "2", "3", "n"],
        "rows": [
            ["1. A", "—", "0.50*", "0.20", "100"],
            ["2. B", "0.50*", "—", "0.80**", "100"],
            ["3. C", "0.20", "0.80**", "—", "100"],
        ],
        "note": "Not.",
    }
    out = correlation_lower_triangle(result)
    assert out["rows"][0][2] == ""
    assert out["rows"][0][3] == ""
    assert out["rows"][1][3] == ""
    assert out["rows"][2][1] == "0.20"
    assert out.get("lower_triangle") is True


def test_normalize_sort_order_and_locale():
    results = [
        {"type": "ttest", "table_number": 5, "title": "Tablo 5. t", "rows": [["p", "0.021"]], "headers": ["a"]},
        _freq_table("Bölüm", [["Bölüm", "A", "50", "50.0"], ["Bölüm", "Toplam", "100", "100.0"]], 3),
        _freq_table("Cinsiyet", [["Cinsiyet", "K", "60", "60.0"], ["Cinsiyet", "Toplam", "100", "100.0"]], 4),
        {"type": "descriptive", "table_number": 1, "title": "Tablo 1. Tanımlayıcı", "rows": [["1.23"]], "headers": ["M"]},
        _cronbach_table("OYS", 15, 300, "0.892", "İyi", 2),
    ]
    cfg = LayoutConfig(locale="tr", decimal_separator=",", leading_zero=True)
    out = normalize_table_layout(results, cfg)
    types = [r["type"] for r in out]
    assert types[0] == "demographics"
    assert types[1] == "descriptive"
    assert types[2] == "cronbach"
    assert out[0]["table_number"] == 1
    assert "0,892" in str(out[2]["rows"])


def test_normalize_renumbers_after_merge():
    results = [
        {"type": "descriptive", "table_number": 1, "title": "Tablo 1. Tanımlayıcı", "rows": [["a"]], "headers": ["x"]},
        _cronbach_table("OYS", 15, 300, "0.892", "İyi", 2),
        _cronbach_table("NEQ", 10, 298, "0.845", "İyi", 3),
        {"type": "frequency", "table_number": 4, "title": "Tablo 4. Frekans", "rows": [["b"]], "headers": ["y"], "is_demographic": False},
    ]
    out = normalize_table_layout(results)
    cronbach = [r for r in out if r["type"] == "cronbach"]
    assert len(cronbach) == 1
    assert len(cronbach[0]["rows"]) == 2


def _ttest_table(outcome: str, grouping: str = "Cinsiyet", table_no: int = 5):
    return {
        "type": "ttest",
        "table_number": table_no,
        "title": f"Tablo {table_no}. t — {outcome}",
        "headers": ["Değişken", "Grup", "n", "M±SS", "t", "df", "p", "d"],
        "rows": [
            [outcome, "Kadın", "50", "75.0 ± 8.0", "2.10", "98", ".039*", "0.42"],
            [outcome, "Erkek", "50", "68.0 ± 7.0", "", "", "", ""],
        ],
        "note": "Not.",
        "grouping_label": grouping,
        "outcome_label": outcome,
        "t": 2.1,
        "p": 0.039,
        "cohens_d": 0.42,
        "df": 98,
        "significant": True,
        "groups": [
            {"name": "Kadın", "n": 50, "mean": 75.0, "sd": 8.0},
            {"name": "Erkek", "n": 50, "mean": 68.0, "sd": 7.0},
        ],
    }


def test_merge_ttest_tables():
    merged = merge_ttest_tables([
        _ttest_table("OYS Toplam"),
        _ttest_table("NEQ Toplam"),
    ])
    assert merged is not None
    assert merged.get("combined") is True
    assert len(merged["rows"]) == 2
    assert merged["rows"][0][0] == "OYS Toplam"
    assert len(merged.get("comparison_summaries") or []) == 2


def test_normality_moves_to_descriptive_footnote():
    results = [
        {
            "type": "descriptive",
            "title": "Tablo 1. Tanımlayıcı",
            "headers": ["x"],
            "rows": [["a"]],
            "note": "Not. SS = Standart Sapma.",
        },
        {
            "type": "normality",
            "title": "Tablo 2. Normallik",
            "headers": ["Değişken", "İstatistik", "df", "p"],
            "rows": [["OYS", "W = 0.98", "100", ".214"]],
            "note": "Not.",
        },
    ]
    out = move_normality_to_descriptive_footnote(results)
    assert len(out) == 1
    assert out[0]["type"] == "descriptive"
    assert "Normallik analizi" in out[0]["note"]
    assert "OYS" in out[0]["note"]


def test_normalize_merges_ttests():
    results = [
        {"type": "descriptive", "table_number": 1, "title": "Tablo 1. Tan", "rows": [["1"]], "headers": ["a"], "note": "Not."},
        _ttest_table("OYS Toplam", table_no=2),
        _ttest_table("NEQ Toplam", table_no=3),
    ]
    cfg = LayoutConfig(merge_group_comparisons=True, suppress_normality_to_footnote=False)
    out = normalize_table_layout(results, cfg)
    ttests = [r for r in out if r["type"] == "ttest"]
    assert len(ttests) == 1
    assert ttests[0].get("combined") is True


def test_merged_cronbach_bulgu():
    merged = merge_cronbach_results([
        _cronbach_table("OYS", 15, 300, "0.892", "İyi güvenilirlik"),
        _cronbach_table("NEQ", 10, 298, "0.845", "İyi güvenilirlik"),
    ])
    text = generate_bulgu_from_template(merged)
    assert text
    assert "OYS" in text
    assert "NEQ" in text
    assert "Cronbach" in text
