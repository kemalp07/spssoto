"""data_profile — türev etiket üretimi testleri."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from data_profile import build_derived_label, find_derived_variables
from schemas import Variable


@pytest.mark.parametrize(
    "source_name,source_label,derived_name,expected",
    [
        ("yas", "Yaş", "yas_binary", "Yaş Binary"),
        ("yas", "Yaş", "YAS_BINARY", "Yaş Binary"),
        ("gece_yeme", "Gece Yeme Anketi", "gece_yeme_risk_grubu", "Gece Yeme Anketi Risk Grubu"),
        ("vki", "VKİ", "vki_kategori", "VKİ Kategori"),
        ("vki", "VKİ", "VKI_KATEGORI", "VKİ Kategori"),
        ("bmi", "", "bmi_sinif", "Bmi Sinif"),
        ("yas", "", "yas_grubu", "Yas Grubu"),
        ("score", "Puan", "score_cut_3", "Puan Cut 3"),
        ("abc", "Kaynak", "abc", "Kaynak"),
    ],
)
def test_derived_label_source_plus_normalized_suffix(
    source_name, source_label, derived_name, expected,
):
    source = Variable(
        name=source_name,
        label=source_label or source_name,
        type="continuous",
        role="outcome",
    )
    derived = Variable(
        name=derived_name,
        label=derived_name,
        type="categorical",
        role="outcome",
    )
    assert build_derived_label(derived_name, source_name, source, derived) == expected


def test_derived_label_keeps_existing_sav_label():
    source = Variable(name="yas", label="Yaş", type="continuous", role="outcome")
    derived = Variable(
        name="yas_grubu",
        label="Yaş Grubu",
        type="categorical",
        role="grouping",
    )
    assert build_derived_label("yas_grubu", "yas", source, derived) == "Yaş Grubu"


def test_derived_label_without_source_label_normalizes_column_name():
    source = Variable(name="gece_yeme", label="gece_yeme", type="continuous", role="outcome")
    derived = Variable(name="gece_yeme_risk", label="gece_yeme_risk", type="categorical", role="grouping")
    assert (
        build_derived_label("gece_yeme_risk", "gece_yeme", source, derived)
        == "Gece Yeme Risk"
    )


def test_find_derived_variables_includes_derived_label(yas_df_fixture):
    df, variables = yas_df_fixture
    derived = find_derived_variables(df, variables)
    by_name = {d["name"]: d for d in derived}
    assert by_name["yas_grubu"]["derived_label"] == "Yaş Grubu"
    assert by_name["yas_binary"]["derived_label"] == "Yaş Binary"


@pytest.fixture
def yas_df_fixture():
    rng = np.random.default_rng(11)
    n = 50
    yas = rng.integers(18, 65, n)
    yas_grubu = pd.cut(yas, bins=[0, 30, 45, 100], labels=[1, 2, 3]).astype(int)
    yas_binary = (yas >= 30).astype(int)
    df = pd.DataFrame({
        "yas": yas,
        "yas_grubu": yas_grubu,
        "yas_binary": yas_binary,
    })
    variables = [
        Variable(name="yas", label="Yaş", type="continuous", role="outcome"),
        Variable(name="yas_grubu", label="yas_grubu", type="categorical", role="outcome"),
        Variable(name="yas_binary", label="yas_binary", type="categorical", role="outcome"),
    ]
    return df, variables
