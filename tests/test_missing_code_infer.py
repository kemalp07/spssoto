"""Kayıp veri kodu sezgisel tespiti testleri."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from missing_code_infer import infer_missing_codes_from_dataframe


def test_detects_sentinel_99():
    df = pd.DataFrame({
        "a": [1, 2, 3, 4, 5, 1, 2, 3, 4, 99, 99, 99],
        "b": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    })
    per_col, global_code = infer_missing_codes_from_dataframe(df)
    assert "a" in per_col
    assert "99" in per_col["a"]
    assert global_code == "99"


def test_ignores_non_repeated_outliers():
    df = pd.DataFrame({"a": list(range(1, 21)) + [999]})
    per_col, _ = infer_missing_codes_from_dataframe(df)
    assert "a" not in per_col
