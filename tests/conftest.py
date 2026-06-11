"""Sentetik test veri seti (~30 satır)."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from schemas import Variable

_session_t0: float | None = None
_progress = {"done": 0, "passed": 0, "failed": 0, "skipped": 0, "total": 0}


def _fmt_elapsed(seconds: float) -> str:
    if seconds >= 60:
        return f"{int(seconds // 60)} dk {seconds % 60:.1f} sn"
    return f"{seconds:.1f} sn"


def pytest_sessionstart(session):
    global _session_t0
    _session_t0 = time.perf_counter()


def pytest_collection_finish(session):
    _progress["total"] = len(session.items)
    total = _progress["total"]
    print(f"\n{'=' * 56}", flush=True)
    print(f"  StatAI test kosusu - {total} test", flush=True)
    print(f"  Baslangic: {time.strftime('%H:%M:%S')}", flush=True)
    print(f"{'=' * 56}\n", flush=True)


def pytest_runtest_logreport(report):
    if report.when != "call" or _session_t0 is None:
        return
    _progress["done"] += 1
    elapsed = time.perf_counter() - _session_t0
    total = _progress["total"] or "?"
    short = report.nodeid.split("::")[-1]
    if report.passed:
        _progress["passed"] += 1
        icon = "OK"
    elif report.skipped:
        _progress["skipped"] += 1
        icon = "ATLA"
    else:
        _progress["failed"] += 1
        icon = "KALDI"
    print(
        f"  [{_progress['done']}/{total}] {icon:4} {short}"
        f"  | gecen: {_fmt_elapsed(elapsed)}",
        flush=True,
    )


def pytest_sessionfinish(session, exitstatus):
    if _session_t0 is None:
        return
    elapsed = time.perf_counter() - _session_t0
    c = _progress
    print(f"\n{'=' * 56}", flush=True)
    print(
        f"  Sonuc: {c['passed']} gecti | {c['failed']} kaldi | {c['skipped']} atlandi",
        flush=True,
    )
    print(f"  Toplam sure: {_fmt_elapsed(elapsed)}", flush=True)
    if exitstatus == 0:
        print("  Durum: TUM TESTLER GECTI", flush=True)
    else:
        print("  Durum: BASARISIZ - yukaridaki hatalara bakin", flush=True)
    print(f"{'=' * 56}\n", flush=True)


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
