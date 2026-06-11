"""Sentetik test veri seti (~30 satır)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from schemas import Variable


@pytest.fixture
def sample_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 30
    sex = rng.choice([1, 2], size=n)
    dept = rng.choice([1, 2, 3], size=n)
    score_a = rng.normal(70, 8, n)
    score_b = rng.normal(68, 9, n)
    score_a[sex == 1] += 5  # Welch için grup varyans farkı
    score_b[sex == 2] += 3
    pre = rng.normal(50, 5, n)  # paired ölçümler
    post = pre + rng.normal(3, 2, n)
    post[5] = pre[5] + 25  # Wilcoxon tetiklemek için aykırı fark

    return pd.DataFrame({
        "id": range(1, n + 1),
        "sex": sex,
        "dept": dept,
        "score_a": score_a,
        "score_b": score_b,
        "pre": pre,
        "post": post,
        "item1": rng.integers(1, 6, n),
        "item2": rng.integers(1, 6, n),
        "item3": rng.integers(1, 6, n),
    })


@pytest.fixture
def cat_cv() -> Variable:
    return Variable(name="sex", label="Cinsiyet", type="categorical", role="grouping")


@pytest.fixture
def cat_cv3() -> Variable:
    return Variable(name="dept", label="Bölüm", type="categorical", role="grouping")


@pytest.fixture
def cont_sv() -> Variable:
    return Variable(name="score_a", label="Puan A", type="continuous", role="outcome")


@pytest.fixture
def cont_sv_b() -> Variable:
    return Variable(name="score_b", label="Puan B", type="continuous", role="outcome")


@pytest.fixture
def fisher_df() -> pd.DataFrame:
    """2x2 tablo — düşük beklenen frekans."""
    return pd.DataFrame({
        "g": [1, 1, 2, 2, 1, 2],
        "o": [1, 2, 1, 2, 1, 2],
    })


def make_variables(names, role="outcome", vtype="continuous"):
    """Yardımcı: Variable listesi oluşturur."""
    return [
        Variable(name=n, label=n, type=vtype, role=role, included=True)
        for n in names
    ]
