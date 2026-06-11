"""Golden istatistik testleri — scipy/statsmodels ile bağımsız doğrulama."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats
from scipy.stats import levene, ttest_ind, fisher_exact

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from schemas import Variable
from stat_tests import (
    TableCounter,
    table_ttest,
    table_anova,
    table_tukey,
    table_games_howell,
    table_mann_whitney,
    table_kruskal,
    table_dunn,
    table_chi_square,
    paired_analysis,
    cronbach_analysis,
    table_multiple_regression,
    mann_whitney_z,
    games_howell_pair,
    kruskal_epsilon_squared,
)


def test_ttest_matches_scipy(sample_df, cat_cv, cont_sv):
    g = sample_df.groupby("sex")["score_a"]
    g1 = g.get_group(1).tolist()
    g2 = g.get_group(2).tolist()
    _, lev_p = levene(g1, g2)
    welch = lev_p < 0.05
    _, p_scipy = ttest_ind(g1, g2, equal_var=not welch)

    tc = TableCounter()
    res = table_ttest(tc, sample_df, cat_cv, cont_sv)
    assert res["significant"] == (p_scipy < 0.05)
    assert abs(res["p"] - round(float(p_scipy), 3)) < 0.001


def test_welch_when_levene_significant(sample_df, cat_cv, cont_sv):
    g = sample_df.groupby("sex")["score_a"]
    _, lev_p = levene(g.get_group(1), g.get_group(2))
    tc = TableCounter()
    res = table_ttest(tc, sample_df, cat_cv, cont_sv)
    if lev_p < 0.05:
        assert res.get("welch") is True


def test_anova_and_tukey(sample_df, cat_cv3, cont_sv):
    groups = [g["score_a"].tolist() for _, g in sample_df.groupby("dept")]
    _, p_anova = stats.f_oneway(*groups)

    tc = TableCounter()
    anova = table_anova(tc, sample_df, cat_cv3, cont_sv)
    if anova.get("welch_anova"):
        from statsmodels.stats.oneway import anova_oneway
        welch = anova_oneway(groups, use_var="unequal")
        assert anova["significant"] == (float(welch.pvalue) < 0.05)
    else:
        assert anova["significant"] == (p_anova < 0.05)
    if anova["significant"]:
        if anova.get("levene_violated"):
            posthoc = table_games_howell(tc, sample_df, cat_cv3, cont_sv)
            assert posthoc is not None
            assert posthoc["type"] == "games_howell"
        else:
            tukey = table_tukey(tc, sample_df, cat_cv3, cont_sv)
            assert tukey is not None
            assert tukey["type"] == "tukey"


def test_welch_anova_when_levene_violated():
    import pandas as pd
    from schemas import Variable
    from statsmodels.stats.oneway import anova_oneway

    df = pd.DataFrame({
        "grp": ["A"] * 12 + ["B"] * 12 + ["C"] * 12,
        "score": (
            list(np.random.default_rng(0).normal(10, 1, 12))
            + list(np.random.default_rng(1).normal(12, 6, 12))
            + list(np.random.default_rng(2).normal(11, 1, 12))
        ),
    })
    cv = Variable(name="grp", label="Grup", type="categorical", role="grouping")
    sv = Variable(name="score", label="Puan", type="continuous", role="outcome")
    groups = [g["score"].tolist() for _, g in df.groupby("grp")]
    _, lev_p = levene(*groups)
    assert lev_p < 0.05

    tc = TableCounter()
    anova = table_anova(tc, df, cv, sv)
    assert anova.get("welch_anova") is True
    assert anova.get("posthoc_type") == "games_howell"
    welch = anova_oneway(groups, use_var="unequal")
    assert anova["f"] == pytest.approx(float(welch.statistic), rel=1e-3)
    assert float(anova["p"]) == pytest.approx(float(welch.pvalue), abs=0.001)


def test_games_howell_pairwise():
    g1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    g2 = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    p, diff = games_howell_pair(g1, g2)
    assert 0 <= p <= 1
    assert diff == pytest.approx(np.mean(g1) - np.mean(g2), abs=0.01)


def test_kruskal_epsilon_squared():
    eps = kruskal_epsilon_squared(12.5, 3, 30)
    assert eps == pytest.approx((12.5 - 3 + 1) / (30 - 3), rel=1e-3)


def test_kruskal_includes_epsilon_squared(sample_df, cat_cv3, cont_sv):
    tc = TableCounter()
    kw = table_kruskal(tc, sample_df, cat_cv3, cont_sv)
    assert "epsilon_squared" in kw
    assert kw["epsilon_squared"] >= 0


def test_mann_whitney_r(sample_df, cat_cv, cont_sv_b):
    tc = TableCounter()
    res = table_mann_whitney(tc, sample_df, cat_cv, cont_sv_b)
    assert "r" in res
    assert 0 <= res["r"] <= 1.0
    g = sample_df.groupby("sex")["score_b"]
    n1, n2 = len(g.get_group(1)), len(g.get_group(2))
    u, _ = stats.mannwhitneyu(g.get_group(1), g.get_group(2), alternative="two-sided")
    z = mann_whitney_z(float(u), n1, n2)
    expected_r = abs(z) / np.sqrt(n1 + n2)
    assert abs(res["r"] - expected_r) < 0.01


def test_kruskal_dunn(sample_df, cat_cv3, cont_sv):
    groups = [g["score_a"].tolist() for _, g in sample_df.groupby("dept")]
    _, p_kw = stats.kruskal(*groups)

    tc = TableCounter()
    kw = table_kruskal(tc, sample_df, cat_cv3, cont_sv)
    assert kw["significant"] == (p_kw < 0.05)
    if kw["significant"]:
        dunn = table_dunn(tc, sample_df, cat_cv3, cont_sv)
        assert dunn is not None
        assert dunn["type"] == "dunn"


def test_chi_square_fisher_2x2(fisher_df):
    v1 = Variable(name="g", label="Grup", type="categorical", role="grouping")
    v2 = Variable(name="o", label="Sonuç", type="categorical", role="outcome")
    ct = pd.crosstab(fisher_df["g"], fisher_df["o"])
    _, p_fisher = fisher_exact(ct.values)

    tc = TableCounter()
    res = table_chi_square(tc, fisher_df, v1, v2)
    assert res["type"] in ("chi_square", "fisher_exact")
    if res["type"] == "fisher_exact":
        assert abs(res["p"] - p_fisher) < 0.001


def test_paired_wilcoxon_or_ttest(sample_df):
    res = paired_analysis(sample_df, "pre", "post")
    assert res["type"] in ("paired_ttest", "paired_wilcoxon")
    assert "p" in res


def test_cronbach_alpha(sample_df):
    cols = ["item1", "item2", "item3"]
    items = sample_df[cols].astype(float)
    k = len(cols)
    item_var = items.var(axis=0, ddof=1).sum()
    total_var = items.sum(axis=1).var(ddof=1)
    alpha_expected = (k / (k - 1)) * (1 - item_var / total_var)

    res = cronbach_analysis(sample_df, cols)
    assert res is not None
    assert abs(res["alpha"] - float(alpha_expected)) < 0.001


def test_multiple_regression(sample_df):
    predictors = [
        Variable(name="pre", label="Ön test", type="continuous", role="grouping"),
        Variable(name="score_a", label="Puan A", type="continuous", role="grouping"),
    ]
    outcome = Variable(name="post", label="Son test", type="continuous", role="outcome")
    tc = TableCounter()
    res = table_multiple_regression(tc, sample_df, predictors, outcome)
    assert res["type"] == "multiple_regression"
    assert "r_squared" in res
    assert 0 <= res["r_squared"] <= 1
