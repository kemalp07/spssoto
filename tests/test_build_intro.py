"""build_intro ile normallik sonuçları tutarlılık testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from schemas import Variable
from formatting import build_intro
from stat_tests import run_analyze, assess_normality


def _outcome_vars():
    return [
        Variable(name="score_a", label="Puan A", type="continuous", role="outcome"),
        Variable(name="score_b", label="Puan B", type="continuous", role="outcome"),
    ]


def test_build_intro_all_parametric(sample_df):
    grouping = Variable(
        name="sex", label="Cinsiyet", type="categorical", role="grouping",
    )
    variables = [grouping, *_outcome_vars()]
    _, meta = run_analyze(sample_df, variables)
    intro = meta["intro"]
    norm_map = meta["norm_map"]

    normal = [
        v.label for v in _outcome_vars()
        if norm_map[v.name].get("is_parametric", True)
    ]
    non_normal = [
        v.label for v in _outcome_vars()
        if not norm_map[v.name].get("is_parametric", True)
    ]

    assert "Shapiro-Wilk" in intro or "Kolmogorov-Smirnov" in intro or "çarpıklık" in intro
    if normal and not non_normal:
        assert "parametrik test" in intro.lower()
        assert "non-parametrik test yöntemleri uygulanmıştır" not in intro
    elif non_normal and not normal:
        assert "non-parametrik" in intro.lower()
    else:
        assert "parametrik ve non-parametrik" in intro.lower()


def test_build_intro_non_parametric_message():
    norm_map = {
        "x": assess_normality(__import__("pandas").Series([1, 1, 2, 2, 3, 3])),
        "y": assess_normality(__import__("pandas").Series([10, 10, 11, 11, 12, 12])),
    }
    outcomes = [
        Variable(name="x", label="Skor X", type="continuous", role="outcome"),
        Variable(name="y", label="Skor Y", type="continuous", role="outcome"),
    ]
    for nm in norm_map.values():
        nm["is_parametric"] = False
        nm["normal"] = False
        nm["test"] = "Shapiro-Wilk"

    intro = build_intro(50, norm_map, outcomes)
    assert "non-parametrik" in intro.lower()
    assert "Shapiro-Wilk" in intro
    assert "Skor X" in intro and "Skor Y" in intro


def test_run_analyze_returns_errors_list(sample_df):
    grouping = Variable(
        name="sex", label="Cinsiyet", type="categorical", role="grouping",
    )
    _, meta = run_analyze(sample_df, [grouping, *_outcome_vars()])
    assert "errors" in meta
    assert isinstance(meta["errors"], list)
