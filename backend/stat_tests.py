"""İstatistiksel testler."""
import re
from collections import defaultdict
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from scipy.stats import (
    shapiro, spearmanr, mannwhitneyu, kruskal, ttest_rel, ttest_ind,
    linregress, kstest, levene, tukey_hsd, wilcoxon, fisher_exact,
)
from statsmodels.stats.oneway import anova_oneway
from statsmodels.stats.outliers_influence import variance_inflation_factor
from schemas import Variable
from constants import PRIMARY_GROUPING_KEYS, DEMO_LABEL_KEYWORDS, SCALE_SCORE_RE
from formatting import (
    TableCounter, fmt_num, fmt_p, fmt_p_display, fmt_r, p_stars, make_result,
    build_group_comparison_title, build_measure_analysis_title,
    build_intro, apa_italicize_stats, academic_short_label,
)
from data_cleaning import (
    filter_chi_square_data, _ordered_category_labels, infer_theoretical_range,
    resolve_scale_info, is_numeric_continuous, format_category_value,
    detect_scale_groups,
)

def _safe_int(val) -> int:
    """'1.0' gibi float-string değerleri güvenle int'e çevir."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return int(float(val))

def cohens_d_interpretation(d: float) -> str:
    ad = abs(d)
    if ad < 0.20:
        return "önemsiz"
    if ad < 0.50:
        return "küçük"
    if ad < 0.80:
        return "orta"
    return "büyük"

def _comparison_labels(cv: Variable, sv: Variable) -> Dict[str, str]:
    return {
        "grouping_label": academic_short_label(cv),
        "grouping_name": cv.name,
        "outcome_label": academic_short_label(sv),
        "outcome_name": sv.name,
    }


def _groups_from_lists(index, group_lists) -> List[dict]:
    out = []
    for name, g in zip(index, group_lists):
        arr = np.asarray(g, dtype=float)
        out.append({
            "name": format_category_value(name),
            "n": int(len(arr)),
            "mean": round(float(np.mean(arr)), 4),
            "sd": round(float(np.std(arr, ddof=1)), 4) if len(arr) > 1 else 0.0,
            "median": round(float(np.median(arr)), 4),
        })
    return out


def rank_effect_interpretation(r: float) -> str:
    ar = abs(r)
    if ar < 0.30:
        return "küçük"
    if ar <= 0.50:
        return "orta"
    return "büyük"

def mann_whitney_z(u: float, n1: int, n2: int) -> float:
    mean_u = n1 * n2 / 2
    std_u = np.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if std_u == 0:
        return 0.0
    return float((u - mean_u) / std_u)

def wilcoxon_z(w_stat: float, n: int) -> float:
    mu = n * (n + 1) / 4
    sigma = np.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    if sigma == 0:
        return 0.0
    return float((w_stat - mu) / sigma)

def eta_interpretation(eta2: float) -> str:
    if eta2 < 0.01:
        return "küçük"
    if eta2 <= 0.06:
        return "orta"
    if eta2 <= 0.14:
        return "orta-üst"
    return "büyük"

def cohens_d(g1: list, g2: list) -> float:
    n1, n2 = len(g1), len(g2)
    if n1 < 2 or n2 < 2:
        return 0.0
    v1, v2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
    pooled = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    if pooled == 0:
        return 0.0
    return float((np.mean(g1) - np.mean(g2)) / pooled)

def welch_df(g1: list, g2: list) -> float:
    n1, n2 = len(g1), len(g2)
    v1, v2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
    num = (v1 / n1 + v2 / n2) ** 2
    den = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    return float(num / den) if den else n1 + n2 - 2

def games_howell_pair(g1: list, g2: list) -> Tuple[float, float]:
    """Games-Howell ikili karşılaştırma — p ve ortalama farkı."""
    a1 = np.asarray(g1, dtype=float)
    a2 = np.asarray(g2, dtype=float)
    n1, n2 = len(a1), len(a2)
    if n1 < 2 or n2 < 2:
        return 1.0, 0.0
    m1, m2 = float(np.mean(a1)), float(np.mean(a2))
    v1, v2 = float(np.var(a1, ddof=1)), float(np.var(a2, ddof=1))
    se = np.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        return 1.0, 0.0
    t_stat = abs(m1 - m2) / se
    num = v1 / n1 + v2 / n2
    den = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    df = num ** 2 / den if den else n1 + n2 - 2
    p = float(2 * stats.t.sf(t_stat, df))
    return p, m1 - m2


def kruskal_epsilon_squared(h_stat: float, k: int, n_total: int) -> float:
    if n_total <= k or k < 2:
        return 0.0
    return max(0.0, float((float(h_stat) - k + 1) / (n_total - k)))


def eta_squared(group_lists: list) -> float:
    all_data = np.concatenate([np.array(g) for g in group_lists])
    grand = np.mean(all_data)
    ss_total = np.sum((all_data - grand) ** 2)
    if ss_total == 0:
        return 0.0
    ss_between = sum(len(g) * (np.mean(g) - grand) ** 2 for g in group_lists)
    return float(ss_between / ss_total)

def assess_normality(series: pd.Series) -> dict:
    from statsmodels.stats.diagnostic import lilliefors

    s = pd.to_numeric(series, errors="coerce").dropna()
    n = len(s)

    if n < 3:
        return {
            "normal": True,
            "n": n,
            "test": "insufficient_data",
            "method": "yetersiz_veri",
            "statistic": None,
            "stat_label": "W",
            "p": None,
            "df": n,
            "skewness": None,
            "skew_se": None,
            "kurtosis": None,
            "kurt_se": None,
            "is_parametric": True,
        }

    if n <= 50:
        stat, p = stats.shapiro(s)
        test_name = "Shapiro-Wilk"
        stat_label = "W"
    else:
        try:
            stat, p = lilliefors(s, dist="norm")
            test_name = "Kolmogorov-Smirnov"
            stat_label = "D"
        except Exception:
            stat, p = kstest(s, "norm", args=(float(s.mean()), float(s.std(ddof=1))))
            test_name = "Kolmogorov-Smirnov"
            stat_label = "D"

    skewness = float(s.skew())
    kurt = float(s.kurtosis())
    skew_se = (6 / n) ** 0.5
    kurt_se = (24 / n) ** 0.5

    if n > 200:
        normal = abs(skewness) < 2 and abs(kurt) < 2
    else:
        normal = float(p) > 0.05

    return {
        "normal": normal,
        "n": n,
        "test": test_name,
        "method": test_name,
        "stat_label": stat_label,
        "statistic": round(float(stat), 3),
        "p": round(float(p), 3),
        "df": n,
        "skewness": round(skewness, 3),
        "kurtosis": round(kurt, 3),
        "skew_se": round(skew_se, 3),
        "kurt_se": round(kurt_se, 3),
        "is_parametric": bool(normal),
    }

def table_descriptive(
    tc: TableCounter,
    variables: List[Variable],
    df: pd.DataFrame,
    scale_info: Optional[dict] = None,
) -> Optional[dict]:
    rows = []
    stats_meta = []
    for v in variables:
        if v.name not in df.columns:
            continue
        s = pd.to_numeric(df[v.name], errors="coerce").dropna()
        if len(s) == 0:
            continue
        theory = infer_theoretical_range(v, df, scale_info) or "—"
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        iqr = q3 - q1
        rows.append([
            v.label, str(len(s)),
            f"{fmt_num(s.mean())} ± {fmt_num(s.std(ddof=1))}",
            fmt_num(s.median()), f"{fmt_num(s.min())} – {fmt_num(s.max())}", theory,
        ])
        stats_meta.append({
            "label": v.label,
            "n": int(len(s)),
            "mean": round(float(s.mean()), 3),
            "sd": round(float(s.std(ddof=1)), 3),
            "median": round(float(s.median()), 3),
            "iqr": round(float(iqr), 3),
            "theory": theory,
        })
    if not rows:
        return None
    no, title = tc.next("Tanımlayıcı İstatistikler")
    return make_result(
        "descriptive", no, title,
        ["Ölçek", "n", "x̄ ± SS", "Medyan", "Min – Maks", "Teorik Aralık"],
        rows, "Not. SS = Standart Sapma.",
        variables_stats=stats_meta,
    )

def table_normality(tc: TableCounter, variables: List[Variable], df: pd.DataFrame, norm_map: dict) -> Optional[dict]:
    rows = []
    for v in variables:
        if v.name not in norm_map:
            continue
        nm = norm_map[v.name]
        if nm.get("statistic") is None:
            continue
        stat_str = f"{nm['stat_label']} = {nm['statistic']}"
        p_str = fmt_p_display(nm["p"])
        skew_ratio = (
            f"{nm['skewness']} / {nm['skew_se']}"
            if nm.get("skewness") is not None else "—"
        )
        kurt_ratio = (
            f"{nm['kurtosis']} / {nm['kurt_se']}"
            if nm.get("kurtosis") is not None else "—"
        )
        rows.append([v.label, stat_str, str(nm["df"]), p_str, skew_ratio, kurt_ratio])
    if not rows:
        return None
    headers = [
        "Değişken", "İstatistik", "df", "p",
        "Çarpıklık / Std. Hata", "Basıklık / Std. Hata",
    ]
    note = (
        "* p < .05; ** p < .01; *** p < .001. "
        "Çarpıklık ve basıklık ±2.0 içindeyse "
        "normal dağılım varsayımı karşılanmış kabul edilir."
    )
    no, title = tc.next("Normallik Testi Sonuçları")
    norm_by_label = {v.label: norm_map[v.name] for v in variables if v.name in norm_map}
    return make_result(
        "normality", no, title, headers, rows, note,
        norm_map={v.name: norm_map[v.name] for v in variables if v.name in norm_map},
        norm_by_label=norm_by_label,
    )

def table_frequency(
    tc: TableCounter,
    series: pd.Series,
    label: str,
    value_labels: Optional[Dict[str, str]] = None,
    is_demographic: bool = False,
) -> dict:
    total_n = int(len(series))
    valid = series.dropna()
    counts = valid.value_counts()
    rows = []
    missing_n = int(series.isna().sum())
    seen_cats = set()

    if value_labels:
        for cat in _ordered_category_labels(value_labels):
            if cat not in counts.index:
                continue
            cnt = _safe_int(counts[cat])
            rows.append([label, cat, str(cnt), ""])
            seen_cats.add(cat)

    for val, cnt in counts.items():
        cat = format_category_value(val)
        if cat == "Kayıp Veri":
            missing_n += _safe_int(cnt)
            continue
        if cat in seen_cats:
            continue
        rows.append([label, cat, str(_safe_int(cnt)), ""])
    valid_n = sum(_safe_int(cnt) for val, cnt in counts.items() if format_category_value(val) != "Kayıp Veri")
    for i, row in enumerate(rows):
        cnt = _safe_int(row[2])
        pct = round(cnt / valid_n * 100, 1) if valid_n else 0
        rows[i][3] = fmt_num(pct, 1)
    if missing_n > 0:
        pct_miss = round(missing_n / total_n * 100, 1) if total_n else 0
        rows.append([label, "Kayıp Veri", str(missing_n), fmt_num(pct_miss, 1)])
    rows.append([label, "Toplam", str(valid_n), "100.0"])
    note = "Not. Değerler frekans (n) ve yüzde (%) olarak verilmiştir."
    if missing_n > 0:
        note += (
            f" Kategori yüzdeleri geçerli örneklem (Valid N={valid_n}) üzerinden hesaplanmıştır;"
            f" analize dahil edilmeyen {missing_n} kayıp veri ayrı gösterilmiştir."
        )
    no, title = tc.next(f"{label} Dağılımı")
    return make_result(
        "frequency", no, title,
        ["Değişken", "Kategori", "n", "%"],
        rows, note,
        variable=label, n=valid_n,
        is_demographic=is_demographic,
        frequency_role="grouping" if is_demographic else "outcome",
    )

def table_chi_square(
    tc: TableCounter,
    df: pd.DataFrame,
    v1: Variable,
    v2: Variable,
    missing_codes: Optional[List[str]] = None,
) -> dict:
    sub, excluded_n = filter_chi_square_data(df, v1, v2, missing_codes)
    ct = pd.crosstab(sub[v1.name], sub[v2.name])
    valid_cols = [c for c in ct.columns if format_category_value(c) != "Kayıp Veri"]
    valid_rows = [i for i in ct.index if format_category_value(i) != "Kayıp Veri"]
    ct = ct.loc[valid_rows, valid_cols]

    row_order = _ordered_category_labels(v1.value_labels)
    if row_order:
        row_order = [r for r in row_order if r in ct.index] + [
            r for r in ct.index if r not in row_order
        ]
        ct = ct.reindex(row_order)
    col_order = _ordered_category_labels(v2.value_labels)
    if col_order:
        col_order = [c for c in col_order if c in ct.columns] + [
            c for c in ct.columns if c not in col_order
        ]
        ct = ct.reindex(columns=col_order)
    chi2, p, dof, expected = stats.chi2_contingency(ct)
    min_expected = float(np.min(expected))
    low_cell_ratio = float((expected < 5).sum() / expected.size)
    use_fisher = low_cell_ratio > 0.20 and ct.shape == (2, 2)
    test_type = "fisher_exact" if use_fisher else "chi_square"
    odds_ratio = None
    if use_fisher:
        odds_ratio, p = fisher_exact(ct.values)
        chi2_report = None
    else:
        chi2_report = round(float(chi2), 3)

    col_headers = [format_category_value(c) for c in ct.columns]
    rows = []
    for idx in ct.index:
        row_total = _safe_int(ct.loc[idx].sum())
        cells = [format_category_value(idx)]
        for col in ct.columns:
            n = _safe_int(ct.loc[idx, col])
            pct = round(n / row_total * 100, 1) if row_total else 0
            cells.append(f"{n} ({fmt_num(pct, 1)})")
        cells.append(str(row_total))
        cells.extend(["", ""])
        rows.append(cells)
    valid_n = _safe_int(ct.values.sum())
    summary_row = ["Toplam"] + [str(_safe_int(ct[c].sum())) for c in ct.columns] + [str(valid_n)]
    if use_fisher:
        summary_row += [f"OR = {fmt_num(odds_ratio)}", fmt_p_display(p)]
        stat_headers = ["OR", "p"]
        title_suffix = "Fisher Kesin Olasılık Testi"
    else:
        summary_row += [f"χ² = {fmt_num(chi2)}", fmt_p_display(p)]
        stat_headers = ["χ²", "p"]
        title_suffix = "Ki-Kare Testi"
    rows.append(summary_row)
    headers = [v1.label] + col_headers + ["Toplam"] + stat_headers
    no, title = tc.next(f"{v1.label} × {v2.label} Dağılımı ({title_suffix})")
    note = "Not. * p < .05. Değerler n (kişi sayısı) ve satır yüzdesi (%) olarak verilmiştir."
    note += f" Minimum beklenen frekans = {fmt_num(min_expected, 2)}."
    if low_cell_ratio > 0.20 and not use_fisher:
        pct_low = round(low_cell_ratio * 100, 1)
        note += (
            f" Beklenen frekansı 5'in altında olan hücre oranı %{pct_low} olduğundan"
            " sonuçlar ihtiyatla yorumlanmalıdır."
        )
    if use_fisher:
        note += " Beklenen frekans varsayımı karşılanmadığından Fisher kesin olasılık testi uygulanmıştır."
    if excluded_n > 0:
        note += (
            f" Ki-kare analizine dahil edilmeyen {excluded_n} kayıp/hatalı kayıt"
            f" matristen çıkarılmıştır (Valid N={valid_n})."
        )
    dominant_row = dominant_col = dominant_pct = dominant_n = None
    if not use_fisher:
        max_pct = -1.0
        for idx in ct.index:
            row_total = _safe_int(ct.loc[idx].sum())
            if row_total <= 0:
                continue
            for col in ct.columns:
                n_cell = _safe_int(ct.loc[idx, col])
                pct = round(n_cell / row_total * 100, 1)
                if pct > max_pct:
                    max_pct = pct
                    dominant_row = format_category_value(idx)
                    dominant_col = format_category_value(col)
                    dominant_n = n_cell
                    dominant_pct = pct
    extra = {
        "p": round(float(p), 3),
        "dof": int(dof),
        "significant": bool(p < 0.05),
        "var1": v1.label,
        "var2": v2.label,
        "min_expected": round(min_expected, 3),
        "low_cell_ratio": round(low_cell_ratio, 3),
    }
    if use_fisher:
        extra["odds_ratio"] = round(float(odds_ratio), 3)
        extra["test_used"] = "fisher_exact"
    else:
        extra["chi2"] = chi2_report
        n_valid = _safe_int(ct.values.sum())
        k_dim = min(ct.shape[0], ct.shape[1])
        if k_dim > 1 and n_valid > 0:
            cramers_v = float(np.sqrt(float(chi2) / (n_valid * (k_dim - 1))))
        else:
            cramers_v = 0.0
        if ct.shape == (2, 2) and n_valid > 0:
            phi = float(np.sqrt(float(chi2) / n_valid))
            extra["effect_size"] = round(phi, 3)
            extra["effect_symbol"] = "φ"
        else:
            extra["effect_size"] = round(cramers_v, 3)
            extra["effect_symbol"] = "Cramer's V"
        extra["effect_interp"] = (
            "güçlü" if cramers_v >= 0.50 else
            "orta" if cramers_v >= 0.30 else
            "zayıf" if cramers_v >= 0.10 else "ihmal edilebilir"
        )
        extra["n_total"] = n_valid
        extra["test_used"] = "chi_square"
        if dominant_row is not None:
            extra["dominant_row"] = dominant_row
            extra["dominant_col"] = dominant_col
            extra["dominant_pct"] = dominant_pct
            extra["dominant_n"] = dominant_n
    return make_result(
        test_type, no, title, headers, rows,
        note,
        **extra,
    )

def table_ttest(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> dict:
    groups = df.groupby(cv.name)[sv.name].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist())
    g1, g2 = list(groups.iloc[0]), list(groups.iloc[1])
    n1, n2 = len(g1), len(g2)
    lev_f, lev_p = levene(g1, g2)
    welch = float(lev_p) < 0.05
    t, p = ttest_ind(g1, g2, equal_var=not welch)
    df_t = int(welch_df(g1, g2)) if welch else n1 + n2 - 2
    d = cohens_d(g1, g2)
    rows = []
    for name, g in zip(groups.index, [g1, g2]):
        rows.append([
            sv.label, format_category_value(name), str(len(g)),
            f"{fmt_num(np.mean(g))} ± {fmt_num(np.std(g, ddof=1))}",
            "", "", "", fmt_num(d) if name == groups.index[0] else "",
        ])
    rows[0][4] = fmt_num(t)
    rows[0][5] = str(df_t)
    rows[0][6] = fmt_p_display(p)
    lev_note = (
        f"Welch düzeltmeli t değeri raporlanmıştır. Levene varyans homojenliği testi: F({n1-1}, {n2-1}) = {fmt_num(lev_f)}; p = {fmt_p(lev_p)}."
        if welch else
        f"Eşit varyans varsayımı karşılanmıştır. Levene varyans homojenliği testi: F({n1-1}, {n2-1}) = {fmt_num(lev_f)}; p = {fmt_p(lev_p)}."
    )
    labels = _comparison_labels(cv, sv)
    groups_meta = _groups_from_lists(groups.index, [g1, g2])
    no, title = tc.next(build_group_comparison_title(cv, sv, "Bağımsız Örneklem t-Testi"))
    return make_result(
        "ttest", no, title,
        ["Değişken", "Grup", "n", "x̄ ± SS", "t", "df", "p", "Cohen's d"],
        rows, f"Not. {lev_note} * p < .05",
        t=round(float(t), 3), p=round(float(p), 3), cohens_d=round(d, 3),
        cohens_d_interp=cohens_d_interpretation(d), significant=bool(p < 0.05),
        welch=welch, levene_f=round(float(lev_f), 3), levene_p=round(float(lev_p), 3),
        df=df_t, groups=groups_meta, **labels,
    )

def table_mann_whitney(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> dict:
    groups = df.groupby(cv.name)[sv.name].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist())
    g1, g2 = list(groups.iloc[0]), list(groups.iloc[1])
    n1, n2 = len(g1), len(g2)
    u, p = mannwhitneyu(g1, g2, alternative="two-sided")
    z = mann_whitney_z(float(u), n1, n2)
    r_effect = abs(z) / np.sqrt(n1 + n2) if (n1 + n2) > 0 else 0.0
    rows = []
    for name, g in zip(groups.index, [g1, g2]):
        rows.append([
            sv.label, format_category_value(name), str(len(g)), fmt_num(np.median(g)),
            "", "", "", "",
        ])
    rows[0][4] = f"U = {fmt_num(u)}"
    rows[0][5] = fmt_num(z)
    rows[0][6] = fmt_p_display(p)
    rows[0][7] = fmt_r(r_effect)
    labels = _comparison_labels(cv, sv)
    groups_meta = _groups_from_lists(groups.index, [g1, g2])
    no, title = tc.next(build_group_comparison_title(cv, sv, "Mann-Whitney U"))
    return make_result(
        "mann_whitney", no, title,
        ["Değişken", "Grup", "n", "Medyan", "U", "z", "p", "r"],
        rows,
        f"Not. * p < .05. Non-parametrik test uygulanmıştır. r = |z|/√n; etki büyüklüğü: {rank_effect_interpretation(r_effect)}.",
        U=round(float(u), 3), z=round(float(z), 3), p=round(float(p), 3),
        r=round(float(r_effect), 3), r_interp=rank_effect_interpretation(r_effect),
        significant=bool(p < 0.05), groups=groups_meta, **labels,
    )

def table_anova(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> dict:
    groups = df.groupby(cv.name)[sv.name].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist())
    group_lists = [g for g in groups]
    k = len(group_lists)
    lev_f, lev_p = levene(*group_lists)
    levene_violated = bool(float(lev_p) < 0.05)
    n_denom = sum(len(g) for g in group_lists) - k
    if levene_violated:
        welch_res = anova_oneway(group_lists, use_var="unequal")
        f, p = float(welch_res.statistic), float(welch_res.pvalue)
        df1, df2 = float(welch_res.df_num), float(welch_res.df_denom)
        welch_anova = True
        posthoc_type = "games_howell"
        test_label = "Welch ANOVA"
        posthoc_note = "Post-hoc: Games-Howell (anlamlıysa)."
    else:
        f, p = stats.f_oneway(*group_lists)
        df1, df2 = k - 1, n_denom
        welch_anova = False
        posthoc_type = "tukey"
        test_label = "Tek Yönlü ANOVA"
        posthoc_note = "Post-hoc: Tukey HSD (anlamlıysa)."
    eta2 = eta_squared(group_lists)
    rows = []
    for name, g in zip(groups.index, group_lists):
        m, sd = np.mean(g), np.std(g, ddof=1)
        ci_lo, ci_hi = m - 1.96 * sd / np.sqrt(len(g)), m + 1.96 * sd / np.sqrt(len(g))
        rows.append([
            format_category_value(name), str(len(g)), f"{fmt_num(m)} ± {fmt_num(sd)}",
            f"{fmt_num(ci_lo)}–{fmt_num(ci_hi)}", "", "", "",
        ])
    rows[0][4] = fmt_num(f)
    rows[0][5] = fmt_p_display(p)
    rows[0][6] = fmt_r(eta2)
    lev_note = (
        f"Levene testi: F({k-1}, {n_denom}) = {fmt_num(lev_f)}; p = {fmt_p(lev_p)}."
    )
    if levene_violated:
        lev_note += " Varyans homojenliği sağlanmadığından Welch ANOVA uygulanmıştır."
    labels = _comparison_labels(cv, sv)
    groups_meta = _groups_from_lists(groups.index, group_lists)
    no, title = tc.next(build_group_comparison_title(cv, sv, test_label))
    return make_result(
        "anova", no, title,
        ["Grup", "n", "x̄ ± SS", "Alt–Üst", "F", "p", "η²"],
        rows, f"Not. {lev_note} {posthoc_note} ** p < .01",
        f=round(float(f), 3), p=round(float(p), 3), eta_squared=round(eta2, 3),
        eta_interp=eta_interpretation(eta2), significant=bool(p < 0.05),
        df1=round(float(df1), 3) if welch_anova else int(df1),
        df2=round(float(df2), 3) if welch_anova else int(df2),
        levene_f=round(float(lev_f), 3), levene_p=round(float(lev_p), 3),
        levene_violated=levene_violated,
        welch_anova=welch_anova, posthoc_type=posthoc_type,
        groups=groups_meta, **labels,
    )

def table_games_howell(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> Optional[dict]:
    groups = df.groupby(cv.name)[sv.name].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist())
    group_lists = [list(g) for g in groups]
    names = [format_category_value(x) for x in groups.index]
    if len(group_lists) < 2:
        return None
    rows = []
    significant_pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            p_val, mean_diff = games_howell_pair(group_lists[i], group_lists[j])
            rows.append([
                names[i], names[j], fmt_num(mean_diff), "",
                fmt_p_display(p_val), "",
            ])
            if p_val < 0.05:
                significant_pairs.append({
                    "group_i": names[i], "group_j": names[j],
                    "p": round(p_val, 3), "mean_diff": round(mean_diff, 3),
                })
    if not rows:
        return None
    labels = _comparison_labels(cv, sv)
    no, title = tc.next(build_measure_analysis_title(sv, "Post-Hoc Games-Howell Çoklu Karşılaştırması"))
    return make_result(
        "games_howell", no, title,
        ["(I) Grup", "(J) Grup", "Ort. Fark (I–J)", "Std. Hata", "p", "95% GA (Alt–Üst)"],
        rows, "Not. * p < .05. Eşit varyans varsayılmayan gruplar için Games-Howell testi.",
        significant_pairs=significant_pairs, **labels,
    )


def table_tukey(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> Optional[dict]:
    groups = df.groupby(cv.name)[sv.name].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist())
    group_lists = [np.array(g) for g in groups]
    names = [format_category_value(x) for x in groups.index]
    if len(group_lists) < 2:
        return None
    res = tukey_hsd(*group_lists)
    rows = []
    significant_pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            mean_diff = float(np.mean(group_lists[i]) - np.mean(group_lists[j]))
            p = float(res.pvalue[i, j])
            se_val = float(np.std(np.concatenate(group_lists), ddof=1) * np.sqrt(1/len(group_lists[i]) + 1/len(group_lists[j])))
            try:
                ci = res.confidence_interval(alpha=0.05)
                lo, hi = float(ci.low[i, j]), float(ci.high[i, j])
            except Exception:
                lo, hi = mean_diff - 1.96 * se_val, mean_diff + 1.96 * se_val
            rows.append([
                names[i], names[j], fmt_num(mean_diff), fmt_num(se_val),
                fmt_p_display(p), f"{fmt_num(lo)}–{fmt_num(hi)}",
            ])
            if p < 0.05:
                significant_pairs.append({
                    "group_i": names[i], "group_j": names[j],
                    "p": round(p, 3), "mean_diff": round(mean_diff, 3),
                })
    if not rows:
        return None
    labels = _comparison_labels(cv, sv)
    no, title = tc.next(build_measure_analysis_title(sv, "Post-Hoc Tukey HSD Çoklu Karşılaştırması"))
    return make_result(
        "tukey", no, title,
        ["(I) Grup", "(J) Grup", "Ort. Fark (I–J)", "Std. Hata", "p", "95% GA (Alt–Üst)"],
        rows, "Not. * p < .05. GA = Güven Aralığı.",
        significant_pairs=significant_pairs, **labels,
    )

def table_kruskal(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> dict:
    groups = df.groupby(cv.name)[sv.name].apply(lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist())
    group_lists = [g for g in groups]
    h, p = kruskal(*group_lists)
    n_total = sum(len(g) for g in group_lists)
    df_h = len(group_lists) - 1
    eps2 = kruskal_epsilon_squared(float(h), df_h + 1, n_total)
    rows = []
    for name, g in zip(groups.index, group_lists):
        rows.append([format_category_value(name), str(len(g)), fmt_num(np.median(g))])
    labels = _comparison_labels(cv, sv)
    groups_meta = _groups_from_lists(groups.index, group_lists)
    no, title = tc.next(build_group_comparison_title(cv, sv, "Kruskal-Wallis"))
    note = "Not. * p < .05. Non-parametrik test uygulanmıştır."
    if p < 0.05:
        note += " Anlamlı fark için Bonferroni düzeltmeli Dunn post-hoc testi uygulanmıştır."
    return make_result(
        "kruskal_wallis", no, title,
        ["Grup", "n", "Medyan"],
        rows + [["H", fmt_num(h), fmt_p_display(p)]],
        note,
        H=round(float(h), 3), p=round(float(p), 3), significant=bool(p < 0.05),
        df=df_h, n_total=n_total,
        epsilon_squared=round(eps2, 3),
        groups=groups_meta, **labels,
    )

def table_dunn(tc: TableCounter, df: pd.DataFrame, cv: Variable, sv: Variable) -> Optional[dict]:
    import scikit_posthocs as sp

    sub = df[[cv.name, sv.name]].copy()
    sub[sv.name] = pd.to_numeric(sub[sv.name], errors="coerce")
    sub = sub.dropna()
    if sub[cv.name].nunique() < 2:
        return None

    medians = sub.groupby(cv.name)[sv.name].median()
    try:
        dunn_df = sp.posthoc_dunn(
            sub, val_col=sv.name, group_col=cv.name, p_adjust="bonferroni",
        )
    except Exception:
        return None

    rows = []
    significant_pairs = []
    group_keys = list(dunn_df.columns)
    for i in range(len(group_keys)):
        for j in range(i + 1, len(group_keys)):
            g1_key, g2_key = group_keys[i], group_keys[j]
            p_val = float(dunn_df.loc[g1_key, g2_key])
            g1_label = format_category_value(g1_key)
            g2_label = format_category_value(g2_key)
            med1 = float(medians.loc[g1_key]) if g1_key in medians.index else 0.0
            med2 = float(medians.loc[g2_key]) if g2_key in medians.index else 0.0
            direction = ""
            if p_val < 0.05:
                direction = f"{g1_label} daha yüksek" if med1 > med2 else f"{g2_label} daha yüksek"
                significant_pairs.append({
                    "group_i": g1_label, "group_j": g2_label,
                    "p": round(p_val, 3), "direction": direction,
                })
            rows.append([
                g1_label, g2_label, fmt_num(med1), fmt_num(med2),
                fmt_p_display(p_val), direction,
            ])

    if not rows:
        return None

    labels = _comparison_labels(cv, sv)
    no, title = tc.next(build_measure_analysis_title(sv, "Post-Hoc Dunn Çoklu Karşılaştırması"))
    return make_result(
        "dunn", no, title,
        ["(I) Grup", "(J) Grup", "Medyan (I)", "Medyan (J)", "p (Bonferroni)", "Yorum"],
        rows,
        "Not. * p < .05. Bonferroni düzeltmeli Dunn testi. Anlamlı çiftlerde medyanı yüksek olan grup belirtilmiştir.",
        significant_pairs=significant_pairs, **labels,
    )

def table_correlation_matrix(
    tc: TableCounter,
    variables: List[Variable],
    df: pd.DataFrame,
    norm_map: Optional[dict] = None,
    missing_codes: Optional[List[str]] = None,
) -> Optional[dict]:
    names = [v.name for v in variables if v.name in df.columns]
    labels = [v.label for v in variables if v.name in df.columns]
    n_vars = len(names)
    if n_vars < 2:
        return None

    sample_sizes = [
        norm_map.get(v.name, {}).get("n", 0)
        for v in variables
        if v.name in (norm_map or {})
    ]
    min_n = min(sample_sizes) if sample_sizes else 0

    if min_n > 200:
        use_pearson = True
    else:
        use_pearson = all(
            norm_map.get(v.name, {}).get("normal", norm_map.get(v.name, {}).get("is_parametric", True))
            for v in variables
            if v.name in (norm_map or {})
        )

    method = "Pearson" if use_pearson else "Spearman"
    corr_fn = stats.pearsonr if use_pearson else spearmanr
    matrix = np.eye(n_vars)
    p_matrix = np.zeros((n_vars, n_vars))
    n_matrix = np.zeros((n_vars, n_vars), dtype=int)

    for i in range(n_vars):
        for j in range(i + 1, n_vars):
            s1 = pd.to_numeric(df[names[i]], errors="coerce").dropna()
            s2 = pd.to_numeric(df[names[j]], errors="coerce").dropna()
            common = s1.index.intersection(s2.index)
            if len(common) < 3:
                continue
            r, p = corr_fn(s1[common], s2[common])
            matrix[i, j] = matrix[j, i] = r
            p_matrix[i, j] = p_matrix[j, i] = p
            n_matrix[i, j] = n_matrix[j, i] = len(common)

    headers = ["Değişken"] + [str(i + 1) for i in range(n_vars)] + ["n"]
    rows = []
    for i, label in enumerate(labels):
        row = [f"{i+1}. {label}"]
        for j in range(n_vars):
            if i == j:
                row.append("—")
            else:
                r, p = matrix[i, j], p_matrix[i, j]
                sym = "ρ" if not use_pearson else "r"
                sign = "−" if r < 0 else ""
                row.append(f"{sign}{fmt_r(abs(r))}{p_stars(p)}")
        row.append(str(int(np.max(n_matrix[i])) if np.max(n_matrix[i]) else len(df)))
        rows.append(row)

    significant_pairs = []
    sym = "ρ" if not use_pearson else "r"
    for i in range(n_vars):
        for j in range(i + 1, n_vars):
            p_ij = float(p_matrix[i, j])
            if p_ij < 0.05:
                significant_pairs.append({
                    "var_i": labels[i], "var_j": labels[j],
                    "r": round(float(matrix[i, j]), 4), "p": round(p_ij, 3),
                    "symbol": sym,
                })

    no, title = tc.next(f"Değişkenler Arası {method} Korelasyon Katsayıları")
    note = (
        f"Not. {method} korelasyon katsayıları. "
        "* p < .05; ** p < .01; *** p < .001 (çift kuyruklu)."
    )
    return make_result(
        "correlation_matrix", no, title, headers, rows, note,
        method=method, variables=labels, significant_pairs=significant_pairs,
    )

def table_regression(tc: TableCounter, df: pd.DataFrame, v1: Variable, v2: Variable) -> dict:
    x = pd.to_numeric(df[v1.name], errors="coerce").dropna()
    y = pd.to_numeric(df[v2.name], errors="coerce").dropna()
    common = x.index.intersection(y.index)
    slope, intercept, r, p, se = linregress(x[common], y[common])
    n = len(common)
    t_stat = float(slope / se) if se else 0.0
    no, title = tc.next(f"{v1.label} → {v2.label} Basit Doğrusal Regresyon")
    rows = [
        ["β (eğim)", fmt_num(slope), "SE", fmt_num(se)],
        ["Kesme (intercept)", fmt_num(intercept), "R²", fmt_r(r ** 2)],
        ["p", fmt_p_display(p), "n", str(len(common))],
    ]
    return make_result(
        "regression", no, title,
        ["Parametre", "Değer", "Parametre", "Değer"],
        rows, "Not. * p < .05.",
        slope=round(float(slope), 3), intercept=round(float(intercept), 3),
        beta=round(float(slope), 3), t=round(t_stat, 3),
        r_squared=round(float(r ** 2), 3), p=round(float(p), 3), se=round(float(se), 3),
        n=n, significant=bool(p < 0.05), predictor=v1.label, outcome=v2.label,
    )

def cronbach_analysis(df: pd.DataFrame, columns: List[str], table_no: Optional[int] = None) -> Optional[dict]:
    items_df = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    k = len(columns)
    if k < 2 or len(items_df) < 3:
        return None
    item_var = items_df.var(axis=0, ddof=1).sum()
    total_var = items_df.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return None
    alpha = float((k / (k - 1)) * (1 - item_var / total_var))

    if alpha >= 0.90:
        interp = "Mükemmel"
    elif alpha >= 0.80:
        interp = "Çok İyi"
    elif alpha >= 0.70:
        interp = "İyi"
    elif alpha >= 0.60:
        interp = "Kabul Edilebilir"
    else:
        interp = "Düşük"

    if table_no is None:
        tc = TableCounter()
        table_no, title = tc.next("Ölçek Güvenilirlik Analizi (Cronbach α)")
    else:
        title = f"Tablo {table_no}. Ölçek Güvenilirlik Analizi (Cronbach α)"

    from table_layout import scale_label_from_items

    scale_label = scale_label_from_items(columns)
    return make_result(
        "cronbach", table_no, title,
        ["Ölçek", "Madde Sayısı", "Geçerli n", "Cronbach α", "Değerlendirme"],
        [[scale_label, k, len(items_df), f"{alpha:.3f}", interp]],
        "Not. α = Cronbach alfa iç tutarlılık katsayısı. Kabul edilebilir sınır: α ≥ .70.",
        items=columns, n_items=k, n=int(len(items_df)),
        alpha=round(alpha, 3), interpretation=interp,
        scale_label=scale_label,
    )

def paired_ttest(df: pd.DataFrame, col1: str, col2: str, label1: Optional[str] = None, label2: Optional[str] = None) -> dict:
    s1 = pd.to_numeric(df[col1], errors="coerce")
    s2 = pd.to_numeric(df[col2], errors="coerce")
    mask = s1.notna() & s2.notna()
    s1, s2 = s1[mask], s2[mask]
    diff = (s1 - s2).tolist()
    t, p = ttest_rel(s1, s2)
    sd_d = float(np.std(diff, ddof=1))
    d = float(np.mean(diff) / sd_d) if sd_d > 0 else 0.0
    n = len(s1)
    pair_label = f"{label1 or col1}–{label2 or col2}"
    _, shapiro_p = shapiro(diff) if n >= 3 else (0.0, 1.0)
    note = (
        "Not. * p < .05. Fark skorları normal dağıldığından (Shapiro-Wilk "
        f"p = {fmt_p(shapiro_p)}) bağımlı örneklem t-testi uygulanmıştır."
    )
    return make_result(
        "paired_ttest", 0, f"{pair_label} - Bağımlı Örneklem t-Testi",
        ["Değişken", "n", "Ort.1", "Ort.2", "Ort. Fark", "SS Fark", "t", "df", "p", "Cohen's d"],
        [[pair_label, str(n), fmt_num(s1.mean()), fmt_num(s2.mean()),
          fmt_num(np.mean(diff)), fmt_num(np.std(diff, ddof=1)),
          fmt_num(t), str(n - 1), fmt_p_display(p), fmt_num(d)]],
        note,
        var1=label1 or col1, var2=label2 or col2, n=n,
        mean1=round(float(s1.mean()), 2), mean2=round(float(s2.mean()), 2),
        mean_diff=round(float(np.mean(diff)), 2),
        sd_diff=round(float(np.std(diff, ddof=1)), 2),
        t=round(float(t), 3), p=round(float(p), 3),
        cohens_d=round(d, 3), cohens_d_interp=cohens_d_interpretation(d),
        df=n - 1, significant=bool(p < 0.05),
        shapiro_p=round(float(shapiro_p), 3),
    )

def paired_wilcoxon(df: pd.DataFrame, col1: str, col2: str, label1: Optional[str] = None, label2: Optional[str] = None, shapiro_p: float = 0.0) -> dict:
    s1 = pd.to_numeric(df[col1], errors="coerce")
    s2 = pd.to_numeric(df[col2], errors="coerce")
    mask = s1.notna() & s2.notna()
    s1, s2 = s1[mask], s2[mask]
    n = len(s1)
    w_stat, p = wilcoxon(s1, s2, alternative="two-sided", zero_method="wilcox")
    z = wilcoxon_z(float(w_stat), n)
    r_effect = abs(z) / np.sqrt(n) if n > 0 else 0.0
    pair_label = f"{label1 or col1}–{label2 or col2}"
    note = (
        "Not. * p < .05. Fark skorları normal dağılmadığından (Shapiro-Wilk "
        f"p = {fmt_p(shapiro_p)}) Wilcoxon işaretli sıralar testi uygulanmıştır."
    )
    return make_result(
        "paired_wilcoxon", 0, f"{pair_label} - Wilcoxon İşaretli Sıralar Testi",
        ["Değişken", "n", "Medyan1", "Medyan2", "z", "p", "r"],
        [[pair_label, str(n), fmt_num(s1.median()), fmt_num(s2.median()),
          fmt_num(z), fmt_p_display(p), fmt_r(r_effect)]],
        note,
        var1=label1 or col1, var2=label2 or col2, n=n,
        median1=round(float(s1.median()), 2), median2=round(float(s2.median()), 2),
        z=round(float(z), 3), p=round(float(p), 3),
        r=round(float(r_effect), 3), r_interp=rank_effect_interpretation(r_effect),
        significant=bool(p < 0.05), shapiro_p=round(float(shapiro_p), 3),
    )

def paired_analysis(df: pd.DataFrame, col1: str, col2: str, label1: Optional[str] = None, label2: Optional[str] = None) -> dict:
    s1 = pd.to_numeric(df[col1], errors="coerce")
    s2 = pd.to_numeric(df[col2], errors="coerce")
    mask = s1.notna() & s2.notna()
    s1, s2 = s1[mask], s2[mask]
    n = len(s1)
    if n < 3:
        raise ValueError("Eşleştirilmiş analiz için en az 3 geçerli gözlem gerekir.")
    diff = (s1 - s2).values
    _, shapiro_p = shapiro(diff)
    if shapiro_p < 0.05:
        return paired_wilcoxon(df, col1, col2, label1, label2, shapiro_p=float(shapiro_p))
    return paired_ttest(df, col1, col2, label1, label2)

def table_multiple_regression(
    tc: TableCounter,
    df: pd.DataFrame,
    predictors: List[Variable],
    outcome: Variable,
) -> dict:
    pred_names = [p.name for p in predictors]
    cols = [outcome.name] + pred_names
    sub = df[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < len(predictors) + 2:
        raise ValueError("Regresyon için yetersiz geçerli gözlem.")

    y = sub[outcome.name]
    x_raw = sub[pred_names]
    x_const = sm.add_constant(x_raw)
    model = sm.OLS(y, x_const).fit()

    y_sd = float(y.std(ddof=1)) if float(y.std(ddof=1)) > 0 else 1.0
    vif_warn = False
    max_vif = 0.0
    coef_rows = []
    rows = []
    const_b = float(model.params["const"])
    const_se = float(model.bse["const"])
    const_t = float(model.tvalues["const"])
    const_p = float(model.pvalues["const"])
    rows.append([
        "Sabit", fmt_num(const_b), fmt_num(const_se), "—",
        fmt_num(const_t), fmt_p_display(const_p), "—",
    ])

    for i, pred in enumerate(predictors):
        coef = float(model.params[pred.name])
        se = float(model.bse[pred.name])
        t_val = float(model.tvalues[pred.name])
        p_val = float(model.pvalues[pred.name])
        x_sd = float(sub[pred.name].std(ddof=1))
        beta_std = coef * (x_sd / y_sd) if x_sd > 0 else 0.0
        vif = float(variance_inflation_factor(x_raw.values, i))
        max_vif = max(max_vif, vif)
        if vif > 10:
            vif_warn = True
        coef_rows.append({
            "label": pred.label,
            "B": round(coef, 3),
            "beta": round(beta_std, 3),
            "t": round(t_val, 3),
            "p": round(p_val, 3),
            "vif": round(vif, 2),
            "significant": bool(p_val < 0.05),
        })
        rows.append([
            pred.label, fmt_num(coef), fmt_num(se), fmt_r(beta_std),
            fmt_num(t_val), fmt_p_display(p_val), fmt_num(vif, 2),
        ])

    r2 = float(model.rsquared)
    adj_r2 = float(model.rsquared_adj)
    f_stat = float(model.fvalue) if model.fvalue is not None else 0.0
    f_p = float(model.f_pvalue) if model.f_pvalue is not None else 1.0
    df1 = int(model.df_model)
    df2 = int(model.df_resid)

    pred_labels = ", ".join(p.label for p in predictors)
    no, title = tc.next(f"{outcome.label} Çoklu Doğrusal Regresyon ({pred_labels})")
    note = (
        f"Not. * p < .05. n = {len(sub)}. Model: R² = {fmt_r(r2)}, "
        f"düzeltilmiş R² = {fmt_r(adj_r2)}, F({df1}, {df2}) = {fmt_num(f_stat)}, "
        f"p = {fmt_p(f_p)}."
    )
    if vif_warn:
        note += " VIF > 10 olan yordayıcı(lar) bulunduğundan çoklu bağlantı riski vardır."

    return make_result(
        "multiple_regression", no, title,
        ["Yordayıcı", "B", "SE", "β", "t", "p", "VIF"],
        rows, note,
        n=len(sub), r_squared=round(r2, 3), adj_r_squared=round(adj_r2, 3),
        f=round(f_stat, 3), p=round(f_p, 3), significant=bool(f_p < 0.05),
        df1=df1, df2=df2,
        outcome=outcome.label, predictors=[p.label for p in predictors],
        coefficients=coef_rows, max_vif=round(max_vif, 2),
        vif_warning=vif_warn,
    )

def is_primary_grouping(var: Variable) -> bool:
    name = var.name.lower()
    return any(key in name for key in PRIMARY_GROUPING_KEYS)

def _is_demographic_continuous(v: Variable) -> bool:
    """Sürekli ama demografik olan değişkenleri etiket/kolon adından tespit et."""
    text = f"{v.name} {v.label or ''}".lower()
    return bool(DEMO_LABEL_KEYWORDS.search(text))

def generate_plan(df: pd.DataFrame, variables: List[Variable]) -> List[dict]:
    active = [v for v in variables if v.included]
    cat_vars = [v for v in active if v.type == "categorical"]
    cont_vars = [v for v in active if v.type == "continuous"]
    grouping_cat = [v for v in cat_vars if v.role == "grouping"]
    outcome_cat = [v for v in cat_vars if v.role == "outcome"]
    grouping_cont = [v for v in cont_vars if v.role == "grouping"]
    outcome_cont = [v for v in cont_vars if v.role == "outcome"]
    all_cont = outcome_cont + grouping_cont

    tests: List[dict] = []

    if all_cont:
        tests.append({
            "id": "descriptive",
            "type": "descriptive",
            "label": "Tanımlayıcı İstatistikler",
            "detail": f"{len(all_cont)} sürekli değişken: {', '.join(v.label for v in all_cont[:3])}{'...' if len(all_cont) > 3 else ''}",
            "recommended": True,
            "count": 1,
        })

    if all_cont:
        tests.append({
            "id": "normality",
            "type": "normality",
            "label": "Normallik Testi",
            "detail": f"{len(all_cont)} değişken için Shapiro-Wilk / Kolmogorov-Smirnov",
            "recommended": True,
            "count": 1,
        })

    freq_vars = grouping_cat + outcome_cat
    if freq_vars:
        tests.append({
            "id": "frequency",
            "type": "frequency",
            "label": "Frekans Tabloları",
            "detail": f"{len(freq_vars)} kategorik değişken: {', '.join(v.label for v in freq_vars[:3])}{'...' if len(freq_vars) > 3 else ''}",
            "recommended": True,
            "count": len(freq_vars),
        })

    for cv in grouping_cat:
        if cv.name not in df.columns:
            continue
        kare_pairs = [
            f"{cv.label} × {ov.label}"
            for ov in outcome_cat
            if ov.name in df.columns
            and not SCALE_SCORE_RE.search(ov.name)
        ]
        if not kare_pairs:
            continue
        tests.append({
            "id": f"chi_square_{cv.name}",
            "type": "chi_square",
            "label": f"Ki-Kare — {cv.label}",
            "detail": "; ".join(kare_pairs[:3]) + ("..." if len(kare_pairs) > 3 else ""),
            "recommended": is_primary_grouping(cv),
            "count": len(kare_pairs),
        })

    cont_targets = [
        v for v in outcome_cont + grouping_cont
        if v.name in df.columns
        and is_numeric_continuous(df, v, {})
        and not _is_demographic_continuous(v)
    ]
    for cv in grouping_cat:
        if cv.name not in df.columns:
            continue
        n_groups = df[cv.name].dropna().nunique()
        if n_groups < 2:
            continue
        test_name = "t-Testi" if n_groups == 2 else "ANOVA"
        pairs = [f"{cv.label} × {sv.label}" for sv in cont_targets]
        if pairs:
            tests.append({
                "id": f"ttest_anova_{cv.name}",
                "type": "ttest_anova",
                "label": f"{cv.label} için {test_name}",
                "detail": "; ".join(pairs[:3]) + ("..." if len(pairs) > 3 else ""),
                "recommended": is_primary_grouping(cv),
                "count": len(pairs),
            })

    corr_vars = [v for v in outcome_cont if is_numeric_continuous(df, v, {})]
    if len(corr_vars) >= 2:
        tests.append({
            "id": "correlation",
            "type": "correlation",
            "label": "Korelasyon Matrisi",
            "detail": f"{len(corr_vars)} değişken: {', '.join(v.label for v in corr_vars)}",
            "recommended": True,
            "count": 1,
        })

    return tests

def _normalize_ai_plan_tests(tests: List[dict]) -> List[dict]:
    normalized = []
    for t in tests:
        item = dict(t)
        if "detail" not in item:
            parts = []
            if item.get("test_name"):
                parts.append(str(item["test_name"]))
            if item.get("reason"):
                parts.append(str(item["reason"]))
            if item.get("variables"):
                parts.append(", ".join(str(v) for v in item["variables"]))
            item["detail"] = " — ".join(parts) if parts else str(item.get("label", ""))
        if "count" not in item:
            item["count"] = len(item.get("variables") or []) or 1
        if "recommended" not in item:
            item["recommended"] = True
        normalized.append(item)
    return normalized

def _normalize_ai_plan_ids(
    ai_tests: List[dict],
    rule_tests: List[dict],
) -> List[dict]:
    rule_id_map = {t["id"]: t for t in rule_tests}

    normalized = []
    for ai_test in ai_tests:
        ai_type = ai_test.get("type", "")
        ai_grouping = ai_test.get("grouping", "")

        matched_id = ai_test.get("id")

        for rule_id, rule_test in rule_id_map.items():
            rule_type = rule_test.get("type", "")

            if ai_type != rule_type:
                continue

            if ai_grouping and ai_grouping.lower() in rule_id.lower():
                matched_id = rule_id
                break

            ai_id_lower = ai_test.get("id", "").lower()
            if ai_grouping and ai_grouping.lower() in ai_id_lower:
                if ai_grouping.lower() in rule_id.lower():
                    matched_id = rule_id
                    break

        normalized_test = dict(ai_test)
        normalized_test["id"] = matched_id
        normalized.append(normalized_test)

    return normalized

def _test_enabled(test_id: str, enabled: Optional[List[str]]) -> bool:
    if enabled is None:
        return True
    return test_id in enabled

def run_analyze(
    df: pd.DataFrame,
    variables: List[Variable],
    active_types: Optional[List[str]] = None,
    enabled_tests: Optional[List[str]] = None,
    scale_info: Optional[dict] = None,
    missing_codes: Optional[List[str]] = None,
) -> Tuple[List[dict], dict]:
    def enabled(test_key: str) -> bool:
        if enabled_tests is not None:
            return _test_enabled(test_key, enabled_tests)
        if active_types is None:
            return True
        return test_key in active_types

    def enabled_group(group_type: str, item_key: str) -> bool:
        if enabled_tests is not None:
            return (
                _test_enabled(item_key, enabled_tests)
                or _test_enabled(group_type, enabled_tests)
            )
        if active_types is None:
            return True
        return group_type in active_types or item_key in active_types

    from test_planner import granular_test_enabled, uses_granular_enabled_tests

    granular = uses_granular_enabled_tests(enabled_tests)

    def genabled(test: str, vars: List[str]) -> bool:
        if not granular:
            return True
        return granular_test_enabled(test, vars, enabled_tests)

    tc = TableCounter()
    results: List[dict] = []
    errors: List[dict] = []

    def record_error(analysis: str, variables_label: str, exc: Exception) -> None:
        errors.append({
            "analysis": analysis,
            "variables": variables_label,
            "error": str(exc),
        })

    active = [v for v in variables if v.included]

    cat_vars = [v for v in active if v.type == "categorical"]
    cont_vars = [v for v in active if v.type == "continuous"]

    grouping_cat = [v for v in cat_vars if v.role == "grouping"]
    outcome_cat = [v for v in cat_vars if v.role == "outcome"]
    grouping_cont = [v for v in cont_vars if v.role == "grouping"]
    outcome_cont = [v for v in cont_vars if v.role == "outcome"]
    all_cont = cont_vars

    norm_map: Dict[str, dict] = {}
    for v in all_cont:
        if v.name in df.columns:
            try:
                norm_map[v.name] = assess_normality(df[v.name])
            except Exception as e:
                record_error("Normallik değerlendirmesi", v.label or v.name, e)
                norm_map[v.name] = {"is_parametric": True, "normal": True, "n": 0}

    # 1. Tanımlayıcı
    if enabled("descriptive") and genabled("descriptive", [v.name for v in outcome_cont]):
        try:
            r = table_descriptive(tc, outcome_cont, df, scale_info)
            if r:
                results.append(r)
        except Exception as e:
            labels = ", ".join(v.label for v in outcome_cont) or "—"
            record_error("Tanımlayıcı istatistikler", labels, e)

    # 2. Normallik tablosu
    if enabled("normality") and genabled("normality", [v.name for v in outcome_cont]):
        try:
            r = table_normality(tc, outcome_cont, df, norm_map)
            if r:
                results.append(r)
        except Exception as e:
            labels = ", ".join(v.label for v in outcome_cont) or "—"
            record_error("Normallik testi", labels, e)

    # 3. Cronbach devre dışı — ters madde için /analyze/cronbach-batch kullanılıyor

    # 4. Frekans
    freq_vars = grouping_cat + outcome_cat if enabled("frequency") else []
    for v in freq_vars:
        if granular and not genabled("frequency", [v.name]):
            continue
        if v.name in df.columns:
            try:
                results.append(table_frequency(
                    tc, df[v.name], v.label, v.value_labels,
                    is_demographic=(v in grouping_cat),
                ))
            except Exception as e:
                record_error("Frekans tablosu", v.label or v.name, e)

    # 5. Ki-kare: gruplandırma × sonuç (kategorik)
    for cv in grouping_cat:
        chi_key = f"chi_square_{cv.name}"
        if not granular and not enabled_group("chi_square", chi_key):
            continue
        for ov in outcome_cat:
            if granular and not genabled("chi_square", [cv.name, ov.name]):
                continue
            if not granular and not enabled_group("chi_square", chi_key):
                continue
            if cv.name in df.columns and ov.name in df.columns:
                try:
                    results.append(table_chi_square(tc, df, cv, ov, missing_codes))
                except Exception as e:
                    record_error(
                        "Ki-kare / Fisher",
                        f"{cv.label} × {ov.label}",
                        e,
                    )

    # 6. t-test / ANOVA / Mann-Whitney / Kruskal: gruplandırma × (sonuç + ölçüm)
    for cv in grouping_cat:
        ttest_key = f"ttest_anova_{cv.name}"
        if not granular and not enabled_group("ttest_anova", ttest_key):
            continue
        for sv in outcome_cont + grouping_cont:
            if cv.name not in df.columns or sv.name not in df.columns:
                continue
            if not is_numeric_continuous(df, sv, norm_map):
                continue
            try:
                n_groups = df[cv.name].dropna().nunique()
                if n_groups == 2:
                    test_key = (
                        "ttest"
                        if norm_map.get(sv.name, {}).get("is_parametric", True)
                        else "mann_whitney"
                    )
                    if granular and not genabled(test_key, [cv.name, sv.name]):
                        continue
                    if not granular and not enabled_group("ttest_anova", ttest_key):
                        continue
                    if norm_map.get(sv.name, {}).get("is_parametric", True):
                        results.append(table_ttest(tc, df, cv, sv))
                    else:
                        results.append(table_mann_whitney(tc, df, cv, sv))
                elif n_groups > 2:
                    test_key = (
                        "anova"
                        if norm_map.get(sv.name, {}).get("is_parametric", True)
                        else "kruskal_wallis"
                    )
                    if granular and not genabled(test_key, [cv.name, sv.name]):
                        continue
                    if not granular and not enabled_group("ttest_anova", ttest_key):
                        continue
                    if norm_map.get(sv.name, {}).get("is_parametric", True):
                        anova_res = table_anova(tc, df, cv, sv)
                        results.append(anova_res)
                        if anova_res.get("significant"):
                            if anova_res.get("levene_violated"):
                                posthoc = table_games_howell(tc, df, cv, sv)
                            else:
                                posthoc = table_tukey(tc, df, cv, sv)
                            if posthoc:
                                results.append(posthoc)
                    else:
                        kruskal_res = table_kruskal(tc, df, cv, sv)
                        results.append(kruskal_res)
                        if kruskal_res.get("significant"):
                            dunn = table_dunn(tc, df, cv, sv)
                            if dunn:
                                results.append(dunn)
            except Exception as e:
                record_error(
                    "Grup karşılaştırması",
                    f"{cv.label} × {sv.label}",
                    e,
                )

    # 7. Korelasyon matrisi (kodlanmış kategorikler hariç)
    corr_vars = [v for v in outcome_cont if is_numeric_continuous(df, v, norm_map)]
    corr_var_names = [v.name for v in corr_vars]
    if (
        enabled("correlation")
        and len(corr_vars) >= 2
        and genabled("correlation", corr_var_names)
    ):
        try:
            r = table_correlation_matrix(
                tc, corr_vars, df,
                norm_map=norm_map,
                missing_codes=missing_codes,
            )
            if r:
                results.append(r)
        except Exception as e:
            labels = ", ".join(v.label for v in corr_vars)
            record_error("Korelasyon matrisi", labels, e)

    results = [
        r for r in results
        if r is not None
        and r.get("rows")
        and len(r["rows"]) > 0
        and not all(
            str(cell) in ("—", "nan", "None", "")
            for row in r.get("rows", [])
            for cell in (row[:2] if len(row) >= 2 else row)
        )
    ]

    meta = {
        "n_total": len(df),
        "intro": build_intro(len(df), norm_map, outcome_cont),
        "norm_map": {
            v.name: norm_map[v.name] for v in outcome_cont if v.name in norm_map
        },
        "errors": errors,
    }

    from table_layout import normalize_table_layout

    results = normalize_table_layout(results)
    return results, meta

