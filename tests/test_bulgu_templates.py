"""Şablon bulgu testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from bulgu_templates import generate_bulgu_from_template, has_bulgu_template


def test_ttest_template():
    result = {
        "type": "ttest",
        "significant": True,
        "t": 2.45,
        "p": 0.021,
        "cohens_d": 0.62,
        "rows": [
            ["Puan", "Kadın", "20", "75.2 ± 8.1", "2.45", "38", ".021*", "0.62"],
            ["Puan", "Erkek", "18", "68.4 ± 7.5", "", "", "", ""],
        ],
    }
    assert has_bulgu_template(result)
    text = generate_bulgu_from_template(result)
    assert text
    assert "t-testi" in text.lower() or "t-test" in text.lower()
    assert "0.021" in text or ".021" in text


def test_descriptive_template():
    result = {
        "type": "descriptive",
        "rows": [["NEQ", "30", "45.2 ± 6.1", "44.0", "12 – 60", "5 – 25"]],
    }
    text = generate_bulgu_from_template(result)
    assert "45.2" in text
    assert "hesaplanmıştır" in text
