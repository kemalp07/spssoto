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
    table_mann_whitney,
    table_kruskal,
    table_dunn,
    table_chi_square,
    paired_analysis,
    cronbach_analysis,
    table_multiple_regression,
    mann_whitney_z,
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
    assert anova["significant"] == (p_anova < 0.05)
    if anova["significant"]:
        tukey = table_tukey(tc, sample_df, cat_cv3, cont_sv)
        assert tukey is not None
        assert tukey["type"] == "tukey"


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
