"""Kesin sınıflandırma kuralları (_deterministic_classify)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from ai_services import _deterministic_classify  # noqa: E402


@pytest.mark.parametrize("col", [
    "dbf_boy", "dbf_kilo", "boy", "kilo", "vki", "VKI", "bmi", "height", "weight",
])
def test_anthropometric_columns_are_continuous_optional_outcome(col):
    result = _deterministic_classify(col)
    assert result is not None
    assert result["type"] == "continuous"
    assert result["role"] == "outcome"
    assert result["recommended"] is False
    assert "Antropometrik" in result["reason"]


@pytest.mark.parametrize("col", ["dbf_cinsiyet", "dbf_yas", "dbf_bolum"])
def test_other_dbf_columns_remain_grouping(col):
    result = _deterministic_classify(col)
    assert result is not None
    assert result["role"] == "grouping"
    assert result["type"] == "categorical"


def test_anthro_rule_takes_precedence_over_dbf_prefix():
    """dbf_boy dbf_ demografik kuralına düşmemeli."""
    result = _deterministic_classify("dbf_boy")
    assert result["type"] == "continuous"
    assert result["recommended"] is False
