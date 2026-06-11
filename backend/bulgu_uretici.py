"""Akademik rehbere göre test türü bazlı bulgu metni üretimi."""
from __future__ import annotations

from typing import List, Optional

from formatting import fmt_r
from akademik_rehber.loader import (
    decision_phrase,
    effect_size_label,
    vif_warning_text,
)
from yorum_motoru import (
    append_posthoc_to_text,
    comparison_intro,
    cronbach_tier,
    cronbach_warning,
    dunn_pair_text,
    effect_clause,
    format_correlation_pair,
    group_median_snippet,
    highest_group_name,
    p_txt,
    sig_phrase,
    tukey_pair_text,
    welch_note,
)


def _group_mean_snippet(groups: List[dict], name: Optional[str] = None) -> str:
    for g in groups or []:
        if name and str(g.get("name")) != name:
            continue
        mean = g.get("mean")
        sd = g.get("sd")
        if mean is not None:
            sd_part = f" ± {fmt_r(sd)}" if sd is not None else ""
            return f"{g.get('name')} (x̄ = {fmt_r(mean)}{sd_part})"
    return name or ""


def _levene_anova_note(result: dict) -> str:
    if result.get("type") != "anova":
        return ""
    if result.get("welch_anova"):
        return decision_phrase("welch_anova")
    if result.get("levene_p") is not None:
        return decision_phrase("levene_anova_ok")
    return ""


def _chi_dominant_phrase(result: dict) -> str:
    if not result.get("significant"):
        return ""
    row = result.get("dominant_row")
    col = result.get("dominant_col")
    pct = result.get("dominant_pct")
    n_val = result.get("dominant_n")
    if row is None or col is None or pct is None:
        return ""
    n_part = f", n = {n_val}" if n_val is not None else ""
    return (
        f" {row} katılımcılarının en yüksek oranı (%{pct}{n_part}) "
        f"'{col}' kategorisinde yoğunlaşmıştır."
    )


def bulgu_descriptive(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    stats = result.get("variables_stats") or []
    if stats:
        parts = []
        for st in stats:
            theory = st.get("theory")
            sent = (
                f"{st['label']} ortalama puanı {fmt_r(st['mean'])} ± {fmt_r(st['sd'])} "
                f"(n = {st['n']}, medyan = {fmt_r(st['median'])}, IQR = {fmt_r(st['iqr'])}) "
                f"olarak hesaplanmıştır."
            )
            if theory and theory != "—":
                sent += f" Ölçeğin teorik puan aralığı {theory} arasındadır."
            parts.append(sent)
        return " ".join(parts)

    rows = result.get("rows") or []
    parts = []
    for row in rows:
        if len(row) < 4:
            continue
        scale, n, mean_sd, med = row[0], row[1], row[2], row[3]
        theory = row[5] if len(row) > 5 else None
        sent = (
            f"{scale} ortalama puanı {mean_sd} (n = {n}, medyan = {med}) "
            f"olarak hesaplanmıştır."
        )
        if theory and theory != "—":
            sent += f" Ölçeğin teorik puan aralığı {theory} arasındadır."
        parts.append(sent)
    return " ".join(parts) if parts else None


def bulgu_normality(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    norm_by_label = result.get("norm_by_label") or {}
    rows = result.get("rows") or []
    parts = []
    for row in rows:
        if len(row) < 4:
            continue
        var_label = row[0]
        stat_str, _df, p_str = row[1], row[2], row[3]
        p_note = p_str.strip()
        nm = norm_by_label.get(var_label) or {}
        n_val = nm.get("n") or 0
        test_note = (
            decision_phrase("shapiro_used") if n_val and n_val < 50
            else decision_phrase("ks_used") if n_val else ""
        )
        nonnormal = "*" in p_str or "<" in p_note
        skew_ok = kurt_ok = True
        if nm.get("skewness") is not None:
            skew_ok = abs(float(nm["skewness"])) <= 2.0
            kurt_ok = abs(float(nm.get("kurtosis") or 0)) <= 2.0
        if nonnormal and skew_ok and kurt_ok:
            decision = decision_phrase("normality_mixed")
        elif nonnormal:
            decision = decision_phrase("normality_nonparametric")
        else:
            decision = decision_phrase("normality_parametric")
        skew_part = ""
        if nm.get("skewness") is not None:
            skew_part = (
                f" Çarpıklık = {nm['skewness']}, Basıklık = {nm.get('kurtosis', '—')}."
            )
        parts.append(
            f"{var_label} değişkeninin "
            f"{'dağılımının normal dağılımdan anlamlı sapma gösterdiği saptanmıştır' if nonnormal else 'normal dağılım gösterdiği belirlenmiştir'} "
            f"({stat_str}, p {p_note}).{skew_part} {test_note} {decision}"
        )
    return " ".join(parts) if parts else None


def bulgu_frequency(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    rows = [r for r in (result.get("rows") or []) if r and r[1] not in ("Toplam", "Kayıp Veri")]
    if not rows:
        return None
    var = result.get("variable") or rows[0][0]
    best = max(rows, key=lambda r: float(r[3]) if r[3] and r[3] != "" else 0)
    cat, pct, n_val = best[1], best[3], best[2]
    return (
        f"{var} değişkeninde katılımcıların en yüksek oranı %{pct} (n = {n_val}) ile "
        f"'{cat}' kategorisinde yoğunlaşmıştır."
    )


def bulgu_chi_square(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    v1, v2 = result.get("var1", ""), result.get("var2", "")
    p, sig = result.get("p"), result.get("significant", False)
    rtype = result.get("type", "chi_square")
    if rtype == "fisher_exact":
        base = sig_phrase(
            sig,
            f"{v1} ile {v2} arasında istatistiksel olarak anlamlı bir ilişki saptanmıştır",
            f"{v1} ile {v2} arasında istatistiksel olarak anlamlı bir ilişki saptanmamıştır",
        )
        return f"{base} ({decision_phrase('fisher_used')} OR = {result.get('odds_ratio')}, {p_txt(p)})."
    chi2 = result.get("chi2")
    dof = result.get("dof")
    n_total = result.get("n_total")
    df_part = f"({dof}, N = {n_total})" if dof is not None and n_total else ""
    effect = ""
    if sig and result.get("effect_size") is not None:
        sym = result.get("effect_symbol", "Cramer's V")
        ev = result.get("effect_size")
        interp = result.get("effect_interp") or effect_size_label("cramers_v", ev)
        effect = f", {sym} = {fmt_r(ev)} ({interp} düzeyde ilişki)"
    return (
        f"{v1} ile {v2} arasındaki ilişkinin incelenmesinde "
        f"{sig_phrase(sig, 'anlamlı bir ilişki saptanmıştır', 'anlamlı bir ilişki saptanmamıştır')} "
        f"(χ²{df_part} = {chi2}, {p_txt(p)}{effect})."
        f"{_chi_dominant_phrase(result)}"
    )


def _group_diff_phrase(result: dict, key: str = "mean") -> str:
    sig = result.get("significant", False)
    groups = result.get("groups") or []
    higher = highest_group_name(groups, key)
    if sig and higher:
        stat_word = "medyanı" if key == "median" else "ortalaması"
        return (
            f"istatistiksel olarak anlamlı bir fark saptanmıştır; "
            f"{higher} grubunun {stat_word} daha yüksektir"
        )
    if sig:
        return "istatistiksel olarak anlamlı bir fark saptanmıştır"
    return "istatistiksel olarak anlamlı bir fark saptanmamıştır"


def bulgu_ttest(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    if result.get("combined") and result.get("comparison_summaries"):
        grouping = result.get("grouping_label") or "gruplandırıcı değişken"
        parts = []
        for item in result["comparison_summaries"]:
            outcome = item.get("outcome_label") or "değişken"
            t_val, p_val, d_val = item.get("t"), item.get("p"), item.get("cohens_d")
            df_t = item.get("df")
            sig = item.get("significant", False)
            base = sig_phrase(sig, "anlamlı fark saptanmıştır", "anlamlı fark saptanmamıştır")
            df_part = f"({df_t})" if df_t else ""
            parts.append(
                f"{outcome} için {base} [t{df_part} = {t_val}, {p_txt(p_val)}; d = {d_val}]"
            )
        return (
            f"Katılımcıların {grouping} gruplarına göre bağımsız örneklem t-testi "
            f"sonuçları: " + "; ".join(parts) + "."
        )
    groups = result.get("groups") or []
    if len(groups) < 2:
        return None
    t, p = result.get("t"), result.get("p")
    df_t = result.get("df")
    diff_phrase = _group_diff_phrase(result, "mean")
    df_part = f"({df_t})" if df_t else ""
    intro = comparison_intro(result)
    mean_parts = ", ".join(
        _group_mean_snippet(groups, g.get("name")) for g in groups[:2] if g.get("name")
    )
    tail = f" ({mean_parts})" if mean_parts and result.get("significant") else ""
    text = (
        f"{intro}bağımsız örneklem t-testi ile karşılaştırılması sonucunda {diff_phrase}{tail} "
        f"[t{df_part} = {t}, {p_txt(p)}"
        f"{effect_clause(result, 'cohens_d', 'cohens_d_interp', 'cohens_d', 'Cohen\'s d')}]."
    )
    note = welch_note(result)
    return f"{text} {note}" if note else text


def bulgu_mann_whitney(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    groups = result.get("groups") or []
    if len(groups) < 2:
        return None
    u, z, p = result.get("U"), result.get("z"), result.get("p")
    diff_phrase = _group_diff_phrase(result, "median")
    intro = comparison_intro(result)
    med_parts = ", ".join(
        group_median_snippet(groups, g.get("name")) for g in groups[:2] if g.get("name")
    )
    tail = f" ({med_parts})" if med_parts and result.get("significant") else ""
    return (
        f"{intro}Mann-Whitney U testi ile karşılaştırılması sonucunda {diff_phrase}{tail} "
        f"(U = {u}, z = {z}, {p_txt(p)}"
        f"{effect_clause(result, 'r', 'r_interp', 'rank_r', 'r')})."
    )


def bulgu_anova(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    f_val, p, eta = result.get("f"), result.get("p"), result.get("eta_squared")
    sig = result.get("significant", False)
    df1, df2 = result.get("df1"), result.get("df2")
    df_part = f"({df1}, {df2})" if df1 is not None and df2 is not None else ""
    base = sig_phrase(
        sig,
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    intro = comparison_intro(result)
    eta_part = ""
    if eta is not None:
        eta_part = f"; η² = {fmt_r(eta)}"
        interp = result.get("eta_interp")
        if interp and sig:
            eta_part += f", etki büyüklüğü {interp} düzeydedir"
    text = (
        f"{intro}tek yönlü ANOVA ile karşılaştırılması sonucunda {base} "
        f"(F{df_part} = {f_val}, {p_txt(p)}{eta_part})."
    )
    levene = _levene_anova_note(result)
    if levene:
        text += f" {levene}"
    return append_posthoc_to_text(text, result, all_results)


def bulgu_tukey(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    pairs = result.get("significant_pairs") or []
    intro = comparison_intro(result)
    if not pairs:
        return (
            f"{intro}Tukey HSD post-hoc karşılaştırmasında gruplar arasında "
            f"anlamlı fark saptanmamıştır."
        )
    parts = [tukey_pair_text(p) for p in pairs[:5]]
    return f"{intro}Tukey HSD post-hoc karşılaştırmasında " + "; ".join(parts) + "."


def bulgu_games_howell(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    pairs = result.get("significant_pairs") or []
    intro = comparison_intro(result)
    if not pairs:
        return (
            f"{intro}Games-Howell post-hoc karşılaştırmasında gruplar arasında "
            f"anlamlı fark saptanmamıştır."
        )
    parts = [tukey_pair_text(p) for p in pairs[:5]]
    return f"{intro}Games-Howell post-hoc karşılaştırmasında " + "; ".join(parts) + "."


def bulgu_kruskal(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    h, p = result.get("H"), result.get("p")
    sig = result.get("significant", False)
    df_h = result.get("df")
    n_total = result.get("n_total")
    h_part = f"({df_h}, N = {n_total})" if df_h is not None and n_total else ""
    base = sig_phrase(
        sig,
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    intro = comparison_intro(result)
    eps = result.get("epsilon_squared")
    eps_part = ""
    if eps is not None:
        eps_part = f"; ε² = {fmt_r(eps)}"
        if sig:
            interp = result.get("epsilon_squared_interp") or effect_size_label("epsilon_squared", eps)
            if interp:
                eps_part += f", etki büyüklüğü {interp} düzeydedir"
    text = (
        f"{intro}Kruskal-Wallis testi ile karşılaştırılması sonucunda {base} "
        f"(H{h_part} = {h}, {p_txt(p)}{eps_part})."
    )
    return append_posthoc_to_text(text, result, all_results)


def bulgu_dunn(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    pairs = result.get("significant_pairs") or []
    intro = comparison_intro(result)
    if not pairs:
        return (
            f"{intro}Dunn post-hoc karşılaştırmasında (Bonferroni düzeltmeli) gruplar arasında "
            f"anlamlı fark saptanmamıştır."
        )
    parts = [dunn_pair_text(p) for p in pairs[:5]]
    return f"{intro}Dunn post-hoc testinde (Bonferroni düzeltmeli) " + "; ".join(parts) + "."


def bulgu_correlation(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    method = result.get("method", "Pearson")
    pairs = result.get("significant_pairs") or []
    if not pairs:
        return (
            f"{method} korelasyon analizinde değişkenler arasında "
            f"anlamlı ilişki saptanmamıştır."
        )
    parts = [format_correlation_pair(p) for p in pairs[:6]]
    return f"{method} korelasyon analizinde " + " ".join(parts)


def bulgu_regression(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    r2, p = result.get("r_squared"), result.get("p")
    pred, out = result.get("predictor", ""), result.get("outcome", "")
    beta, t_val = result.get("beta"), result.get("t")
    n = result.get("n")
    sig = result.get("significant", False)
    direction = "pozitif" if beta and float(beta) > 0 else "negatif" if beta else ""
    base = sig_phrase(
        sig,
        f"{pred} değişkeninin {out} üzerinde anlamlı yordayıcı etkisi saptanmıştır",
        f"{pred} değişkeninin {out} üzerinde anlamlı yordayıcı etkisi saptanmamıştır",
    )
    dir_part = f"; {direction} yönde" if direction and sig else ""
    return (
        f"Basit doğrusal regresyon analizinde {base}{dir_part} "
        f"(R² = {fmt_r(r2)}, β = {fmt_r(beta)}, t = {t_val}, {p_txt(p)}, n = {n})."
    )


def bulgu_multiple_regression(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    r2 = result.get("r_squared")
    adj = result.get("adj_r_squared")
    f_val, p = result.get("f"), result.get("p")
    df1, df2 = result.get("df1"), result.get("df2")
    out = result.get("outcome", "")
    sig = result.get("significant", False)
    df_part = f"({df1}, {df2})" if df1 is not None and df2 is not None else ""
    base = sig_phrase(
        sig,
        "regresyon modeli istatistiksel olarak anlamlı bulunmuştur",
        "regresyon modeli istatistiksel olarak anlamlı bulunmamıştır",
    )
    coefs = result.get("coefficients") or []
    sig_preds = [c for c in coefs if c.get("significant")]
    nonsig_preds = [c for c in coefs if not c.get("significant")]
    pred_parts = []
    for c in sig_preds[:4]:
        direction = "pozitif" if float(c.get("beta") or 0) > 0 else "negatif"
        pred_parts.append(
            f"{c['label']} (β = {fmt_r(c.get('beta'))}, t = {c.get('t')}, {p_txt(c.get('p'))}, {direction})"
        )
    nonsig_names = ", ".join(c["label"] for c in nonsig_preds[:3])
    text = (
        f"{out} değişkeni üzerinde çoklu doğrusal regresyon analizinde {base} "
        f"(R² = {fmt_r(r2)}, düzeltilmiş R² = {fmt_r(adj)}, F{df_part} = {f_val}, {p_txt(p)})."
    )
    if pred_parts:
        text += " Anlamlı yordayıcılar: " + "; ".join(pred_parts) + "."
    if nonsig_names:
        text += f" {nonsig_names} yordayıcı olmamıştır."
    vif_note = vif_warning_text(result.get("max_vif"))
    if vif_note:
        text += f" {vif_note}"
    elif result.get("max_vif") is not None and float(result.get("max_vif", 0)) < 5:
        from akademik_rehber.loader import load_rules
        ok = load_rules().get("vif", {}).get("ok_range", "")
        if ok:
            text += f" {ok}"
    return text


def bulgu_paired_ttest(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    v1, v2 = result.get("var1", ""), result.get("var2", "")
    t, p = result.get("t"), result.get("p")
    sig = result.get("significant", False)
    diff = result.get("mean_diff")
    m1, m2 = result.get("mean1"), result.get("mean2")
    df_t = result.get("df")
    df_part = f"({df_t})" if df_t is not None else ""
    if sig and diff is not None:
        higher = v1 if float(diff) > 0 else v2
        base = (
            f"ölçümler arasında istatistiksel olarak anlamlı fark saptanmıştır; "
            f"{higher} puanları daha yüksektir"
        )
    else:
        base = sig_phrase(
            sig,
            "ölçümler arasında istatistiksel olarak anlamlı fark saptanmıştır",
            "ölçümler arasında istatistiksel olarak anlamlı fark saptanmamıştır",
        )
    means = ""
    if m1 is not None and m2 is not None:
        means = f" (x̄₁ = {fmt_r(m1)}, x̄₂ = {fmt_r(m2)})"
    return (
        f"{v1} ve {v2} puanlarının eşleştirilmiş örneklem t-testi sonucunda {base}{means} "
        f"(ortalama fark = {diff}, t{df_part} = {t}, {p_txt(p)}"
        f"{effect_clause(result, 'cohens_d', 'cohens_d_interp', 'cohens_d', 'Cohen\'s d')})."
    )


def bulgu_paired_wilcoxon(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    v1, v2 = result.get("var1", ""), result.get("var2", "")
    z, p = result.get("z"), result.get("p")
    sig = result.get("significant", False)
    med1, med2 = result.get("median1"), result.get("median2")
    if sig and med1 is not None and med2 is not None:
        higher = v1 if float(med1) > float(med2) else v2
        base = (
            f"ölçümler arasında istatistiksel olarak anlamlı fark saptanmıştır; "
            f"{higher} medyan puanı daha yüksektir"
        )
    else:
        base = sig_phrase(
            sig,
            "ölçümler arasında istatistiksel olarak anlamlı fark saptanmıştır",
            "ölçümler arasında istatistiksel olarak anlamlı fark saptanmamıştır",
        )
    med_part = ""
    if med1 is not None and med2 is not None:
        med_part = f" (Med₁ = {fmt_r(med1)}, Med₂ = {fmt_r(med2)})"
    return (
        f"{v1} ve {v2} puanlarının Wilcoxon işaretli sıralar testi sonucunda {base}{med_part} "
        f"(z = {z}, {p_txt(p)}"
        f"{effect_clause(result, 'r', 'r_interp', 'rank_r', 'r')})."
    )


def bulgu_cronbach(result: dict, all_results: Optional[List[dict]] = None) -> Optional[str]:
    scales = result.get("merged_scales") or []
    if len(scales) > 1 or result.get("combined"):
        parts, warnings = [], []
        for s in scales:
            name = s.get("name", "Ölçek")
            n_items = s.get("n_items", "—")
            alpha = s.get("alpha")
            alpha_txt = fmt_r(alpha) if alpha is not None else s.get("alpha_display", "—")
            tier = cronbach_tier(alpha) if alpha is not None else s.get("interpretation", "")
            warn = cronbach_warning(alpha)
            if warn:
                warnings.append(warn)
            parts.append(
                f"{name} ölçeğinin {n_items} maddesi için Cronbach α = {alpha_txt} ({tier})"
            )
        text = (
            "Kullanılan ölçeklerin güvenilirlik analizi sonucunda "
            + "; ".join(parts) + "."
        )
        if warnings:
            text += " " + warnings[0]
        return text

    alpha = result.get("alpha")
    n_items = result.get("n_items")
    tier = cronbach_tier(alpha) if alpha is not None else result.get("interpretation", "")
    warn = cronbach_warning(alpha)
    text = (
        f"Araştırmada kullanılan ölçeğin {n_items} maddesi için Cronbach α güvenilirlik katsayısı "
        f"{fmt_r(alpha)} olarak hesaplanmıştır ({tier} düzeyinde iç tutarlılık)."
    )
    if warn:
        text += f" {warn}"
    return text


BULGU_BUILDERS = {
    "descriptive": bulgu_descriptive,
    "normality": bulgu_normality,
    "frequency": bulgu_frequency,
    "chi_square": bulgu_chi_square,
    "fisher_exact": bulgu_chi_square,
    "ttest": bulgu_ttest,
    "mann_whitney": bulgu_mann_whitney,
    "anova": bulgu_anova,
    "tukey": bulgu_tukey,
    "games_howell": bulgu_games_howell,
    "kruskal_wallis": bulgu_kruskal,
    "kruskal": bulgu_kruskal,
    "dunn": bulgu_dunn,
    "correlation": bulgu_correlation,
    "correlation_matrix": bulgu_correlation,
    "regression": bulgu_regression,
    "multiple_regression": bulgu_multiple_regression,
    "paired_ttest": bulgu_paired_ttest,
    "paired_wilcoxon": bulgu_paired_wilcoxon,
    "cronbach": bulgu_cronbach,
}


def build_bulgu_text(
    result: dict,
    all_results: Optional[List[dict]] = None,
) -> Optional[str]:
    rtype = result.get("type")
    builder = BULGU_BUILDERS.get(rtype)
    if not builder:
        return None
    return builder(result, all_results)
