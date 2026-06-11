"""Şablon tabanlı APA bulgu cümleleri — LLM gerektirmez."""
import re
from typing import Dict, List, Optional

from formatting import fmt_p, fmt_r, apply_academic_text_rules


def _lbl(name: str, label_map: Optional[Dict[str, str]]) -> str:
    if label_map and name in label_map and label_map[name]:
        return label_map[name]
    return name


def _p_txt(p: Optional[float]) -> str:
    """Tam p ifadesi — bulgu cümlelerinde yıldız içermez."""
    if p is None:
        return "—"
    p = float(p)
    if p < 0.001:
        return "p < .001"
    return f"p = {fmt_p(p)}"


def _comparison_intro(result: dict) -> str:
    outcome = result.get("outcome_label") or ""
    grouping = result.get("grouping_label") or ""
    if outcome and grouping:
        return f"{outcome} puanlarının {grouping} değişkenine göre "
    return ""


def _higher_group_name(groups: List[dict], key: str = "mean") -> Optional[str]:
    if len(groups) < 2:
        return None
    g1, g2 = groups[0], groups[1]
    v1 = float(g1.get(key) or 0)
    v2 = float(g2.get(key) or 0)
    return g1["name"] if v1 > v2 else g2["name"]


def _sig_phrase(significant: bool, pos: str, neg: str) -> str:
    return pos if significant else neg


def _corr_strength(r: float) -> str:
    ar = abs(r)
    if ar < 0.30:
        return "zayıf"
    if ar < 0.70:
        return "orta düzeyde"
    return "güçlü"


def _bulgu_descriptive(result: dict) -> Optional[str]:
    rows = result.get("rows") or []
    if not rows:
        return None
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


def _bulgu_normality(result: dict) -> Optional[str]:
    rows = result.get("rows") or []
    parts = []
    for row in rows:
        if len(row) < 4:
            continue
        var, stat_str, _df, p_str = row[0], row[1], row[2], row[3]
        p_match = re.search(r"([<.]?\s*\.?\d+)", p_str.replace("<", "< "))
        p_note = p_str.strip()
        if "*" in p_str or (p_match and "<" in p_str):
            parts.append(
                f"{var} değişkeninin dağılımının normal dağılımdan anlamlı sapma "
                f"gösterdiği saptanmıştır ({stat_str}, p {p_note})."
            )
        else:
            parts.append(
                f"{var} değişkeninin normal dağılım gösterdiği belirlenmiştir "
                f"({stat_str}, p = {p_note.lstrip('=').strip()})."
            )
    return " ".join(parts) if parts else None


def _bulgu_frequency(result: dict) -> Optional[str]:
    rows = [r for r in (result.get("rows") or []) if r and r[1] != "Toplam" and r[1] != "Kayıp Veri"]
    if not rows:
        return None
    var = result.get("variable") or rows[0][0]
    best = max(rows, key=lambda r: float(r[3]) if r[3] and r[3] != "" else 0)
    cat, pct = best[1], best[3]
    return (
        f"{var} değişkeninde katılımcıların en yüksek oranı %{pct} ile "
        f"'{cat}' kategorisinde yoğunlaşmıştır."
    )


def _bulgu_chi_square(result: dict) -> Optional[str]:
    v1 = result.get("var1", "")
    v2 = result.get("var2", "")
    p = result.get("p")
    sig = result.get("significant", False)
    rtype = result.get("type", "chi_square")
    if rtype == "fisher_exact":
        or_val = result.get("odds_ratio")
        base = _sig_phrase(
            sig,
            f"{v1} ile {v2} arasında istatistiksel olarak anlamlı bir ilişki saptanmıştır",
            f"{v1} ile {v2} arasında istatistiksel olarak anlamlı bir ilişki saptanmamıştır",
        )
        return f"{base} (OR = {or_val}, {_p_txt(p)})."
    chi2 = result.get("chi2")
    return (
        f"{v1} ile {v2} arasındaki ilişkinin incelenmesinde "
        f"{_sig_phrase(sig, 'anlamlı bir ilişki saptanmıştır', 'anlamlı bir ilişki saptanmamıştır')} "
        f"(χ² = {chi2}, {_p_txt(p)})."
    )


def _bulgu_ttest(result: dict) -> Optional[str]:
    if result.get("combined") and result.get("comparison_summaries"):
        grouping = result.get("grouping_label") or "gruplandırıcı değişken"
        parts = []
        for item in result["comparison_summaries"]:
            outcome = item.get("outcome_label") or "değişken"
            t_val, p_val, d_val = item.get("t"), item.get("p"), item.get("cohens_d")
            df_t = item.get("df")
            sig = item.get("significant", False)
            base = _sig_phrase(
                sig,
                "anlamlı fark saptanmıştır",
                "anlamlı fark saptanmamıştır",
            )
            df_part = f"({df_t})" if df_t else ""
            parts.append(
                f"{outcome} için {base} [t{df_part} = {t_val}, {_p_txt(p_val)}; d = {d_val}]"
            )
        return (
            f"Katılımcıların {grouping} gruplarına göre bağımsız örneklem t-testi "
            f"sonuçları: " + "; ".join(parts) + "."
        )
    groups = result.get("groups") or []
    if len(groups) < 2:
        return None
    t, p, d = result.get("t"), result.get("p"), result.get("cohens_d")
    df_t = result.get("df")
    higher = _higher_group_name(groups, "mean")
    sig = result.get("significant", False)
    if sig and higher:
        diff_phrase = (
            f"istatistiksel olarak anlamlı bir fark saptanmıştır; "
            f"{higher} grubunun ortalaması daha yüksektir"
        )
    elif sig:
        diff_phrase = "istatistiksel olarak anlamlı bir fark saptanmıştır"
    else:
        diff_phrase = "istatistiksel olarak anlamlı bir fark saptanmamıştır"
    df_part = f"({df_t})" if df_t else ""
    intro = _comparison_intro(result)
    return (
        f"{intro}bağımsız örneklem t-testi ile karşılaştırılması sonucunda {diff_phrase} "
        f"[t{df_part} = {t}, {_p_txt(p)}; Cohen's d = {d}]."
    )


def _bulgu_mann_whitney(result: dict) -> Optional[str]:
    if result.get("combined") and result.get("comparison_summaries"):
        grouping = result.get("grouping_label") or "gruplandırıcı değişken"
        parts = []
        for item in result["comparison_summaries"]:
            outcome = item.get("outcome_label") or "değişken"
            u, z, p = item.get("U"), item.get("z"), item.get("p")
            r_val = item.get("r")
            sig = item.get("significant", False)
            base = _sig_phrase(
                sig,
                "anlamlı fark saptanmıştır",
                "anlamlı fark saptanmamıştır",
            )
            parts.append(
                f"{outcome} için {base} (U = {u}, z = {z}, {_p_txt(p)}, r = {r_val})"
            )
        return (
            f"Katılımcıların {grouping} gruplarına göre Mann-Whitney U testi "
            f"sonuçları: " + "; ".join(parts) + "."
        )
    groups = result.get("groups") or []
    if len(groups) < 2:
        return None
    u, z, p, r = result.get("U"), result.get("z"), result.get("p"), result.get("r")
    sig = result.get("significant", False)
    higher = _higher_group_name(groups, "median")
    if sig and higher:
        diff_phrase = (
            f"istatistiksel olarak anlamlı bir fark saptanmıştır; "
            f"{higher} grubunun medyanı daha yüksektir"
        )
    elif sig:
        diff_phrase = "istatistiksel olarak anlamlı bir fark saptanmıştır"
    else:
        diff_phrase = "istatistiksel olarak anlamlı bir fark saptanmamıştır"
    intro = _comparison_intro(result)
    return (
        f"{intro}Mann-Whitney U testi ile karşılaştırılması sonucunda {diff_phrase} "
        f"(U = {u}, z = {z}, {_p_txt(p)}, r = {r})."
    )


def _bulgu_anova(result: dict) -> Optional[str]:
    if result.get("combined") and result.get("comparison_summaries"):
        grouping = result.get("grouping_label") or "gruplandırıcı değişken"
        parts = []
        for item in result["comparison_summaries"]:
            outcome = item.get("outcome_label") or "değişken"
            f_val, p, eta = item.get("f"), item.get("p"), item.get("eta_squared")
            sig = item.get("significant", False)
            base = _sig_phrase(
                sig,
                "anlamlı fark saptanmıştır",
                "anlamlı fark saptanmamıştır",
            )
            parts.append(
                f"{outcome} için {base} (F = {f_val}, {_p_txt(p)}; η² = {fmt_r(eta)})"
            )
        return (
            f"Katılımcıların {grouping} gruplarına göre tek yönlü ANOVA "
            f"sonuçları: " + "; ".join(parts) + "."
        )
    f_val, p, eta = result.get("f"), result.get("p"), result.get("eta_squared")
    sig = result.get("significant", False)
    outcome = result.get("outcome_label") or "Bağımlı değişken"
    grouping = result.get("grouping_label") or "gruplandırma değişkeni"
    base = _sig_phrase(
        sig,
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    return (
        f"{outcome} puanlarının {grouping} değişkenine göre tek yönlü ANOVA ile "
        f"karşılaştırılması sonucunda {base} "
        f"(F = {f_val}, {_p_txt(p)}; η² = {fmt_r(eta)})."
    )


def _bulgu_tukey(result: dict) -> Optional[str]:
    pairs = result.get("significant_pairs") or []
    intro = _comparison_intro(result)
    if not pairs:
        return (
            f"{intro}Tukey HSD post-hoc karşılaştırmasında gruplar arasında "
            f"anlamlı fark saptanmamıştır."
        )
    sig_rows = [
        f"{p['group_i']}–{p['group_j']} ({_p_txt(p['p'])})" for p in pairs[:5]
    ]
    return (
        f"{intro}Tukey HSD post-hoc karşılaştırmasında anlamlı fark gösteren gruplar: "
        + "; ".join(sig_rows)
        + "."
    )


def _bulgu_kruskal(result: dict) -> Optional[str]:
    h, p = result.get("H"), result.get("p")
    sig = result.get("significant", False)
    base = _sig_phrase(
        sig,
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    note = " Dunn post-hoc testi uygulanmıştır." if sig else ""
    intro = _comparison_intro(result)
    return (
        f"{intro}Kruskal-Wallis testi ile karşılaştırılması sonucunda {base} "
        f"(H = {h}, {_p_txt(p)}).{note}"
    )


def _bulgu_dunn(result: dict) -> Optional[str]:
    pairs = result.get("significant_pairs") or []
    intro = _comparison_intro(result)
    if not pairs:
        return (
            f"{intro}Dunn post-hoc karşılaştırmasında gruplar arasında "
            f"anlamlı fark saptanmamıştır."
        )
    sig_rows = [
        f"{p['group_i']}–{p['group_j']}: {p.get('direction', '')}" for p in pairs[:5]
    ]
    return f"{intro}Dunn post-hoc testinde anlamlı çiftler: " + "; ".join(sig_rows) + "."


def _bulgu_correlation_matrix(result: dict) -> Optional[str]:
    method = result.get("method", "Pearson")
    pairs = result.get("significant_pairs") or []
    if not pairs:
        return f"{method} korelasyon analizinde değişkenler arasında anlamlı ilişki saptanmamıştır."
    sig_pairs = [
        f"{p['var_i']}–{p['var_j']} ({p.get('symbol', 'r')} = {fmt_r(p['r'])})"
        for p in pairs[:6]
    ]
    return (
        f"{method} korelasyon analizinde anlamlı ilişkiler: "
        + "; ".join(sig_pairs)
        + "."
    )


def _bulgu_regression(result: dict) -> Optional[str]:
    r2, p = result.get("r_squared"), result.get("p")
    pred = result.get("predictor", "")
    out = result.get("outcome", "")
    sig = result.get("significant", False)
    base = _sig_phrase(
        sig,
        f"{pred} değişkeninin {out} üzerinde anlamlı yordayıcı etkisi saptanmıştır",
        f"{pred} değişkeninin {out} üzerinde anlamlı yordayıcı etkisi saptanmamıştır",
    )
    return f"Basit doğrusal regresyon analizinde {base} (R² = {fmt_r(r2)}, {_p_txt(p)})."


def _bulgu_multiple_regression(result: dict) -> Optional[str]:
    r2 = result.get("r_squared")
    adj = result.get("adj_r_squared")
    f_val, p = result.get("f"), result.get("p")
    out = result.get("outcome", "")
    sig = result.get("significant", False)
    preds = ", ".join(result.get("predictors") or [])
    base = _sig_phrase(
        sig,
        "regresyon modeli istatistiksel olarak anlamlı bulunmuştur",
        "regresyon modeli istatistiksel olarak anlamlı bulunmamıştır",
    )
    vif = ""
    if result.get("vif_warning"):
        vif = " VIF > 10 uyarısı göz önünde bulundurulmalıdır."
    return (
        f"{out} değişkeni üzerinde {preds} yordayıcılarıyla çoklu doğrusal regresyon "
        f"analizinde {base} (R² = {fmt_r(r2)}, düzeltilmiş R² = {fmt_r(adj)}, "
        f"F = {f_val}, {_p_txt(p)}).{vif}"
    )


def _bulgu_paired_ttest(result: dict) -> Optional[str]:
    v1, v2 = result.get("var1", ""), result.get("var2", "")
    t, p, d = result.get("t"), result.get("p"), result.get("cohens_d")
    sig = result.get("significant", False)
    diff = result.get("mean_diff")
    base = _sig_phrase(
        sig,
        "ölçümler arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "ölçümler arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    return (
        f"{v1} ve {v2} puanlarının eşleştirilmiş örneklem t-testi sonucunda {base} "
        f"(ortalama fark = {diff}, t = {t}, {_p_txt(p)}; Cohen's d = {d})."
    )


def _bulgu_paired_wilcoxon(result: dict) -> Optional[str]:
    v1, v2 = result.get("var1", ""), result.get("var2", "")
    z, p, r = result.get("z"), result.get("p"), result.get("r")
    sig = result.get("significant", False)
    base = _sig_phrase(
        sig,
        "ölçümler arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "ölçümler arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    return (
        f"{v1} ve {v2} puanlarının Wilcoxon işaretli sıralar testi sonucunda {base} "
        f"(z = {z}, {_p_txt(p)}, r = {r})."
    )


def _bulgu_cronbach(result: dict) -> Optional[str]:
    scales = result.get("merged_scales") or []
    if len(scales) > 1 or result.get("combined"):
        parts = []
        for s in scales:
            name = s.get("name", "Ölçek")
            n_items = s.get("n_items", "—")
            alpha = s.get("alpha")
            alpha_txt = fmt_r(alpha) if alpha is not None else s.get("alpha_display", "—")
            interp = s.get("interpretation", "")
            tail = f" ({interp})" if interp else ""
            parts.append(
                f"{name} ölçeğinin {n_items} maddesi için Cronbach α = {alpha_txt}{tail}"
            )
        return (
            "Kullanılan ölçeklerin güvenilirlik analizi sonucunda "
            + "; ".join(parts)
            + "."
        )
    alpha = result.get("alpha")
    n_items = result.get("n_items")
    interp = result.get("interpretation", "")
    return (
        f"Ölçeğin {n_items} maddesi için Cronbach α güvenilirlik katsayısı "
        f"{fmt_r(alpha)} olarak hesaplanmıştır ({interp})."
    )


_TEMPLATE_HANDLERS = {
    "descriptive": _bulgu_descriptive,
    "normality": _bulgu_normality,
    "frequency": _bulgu_frequency,
    "chi_square": _bulgu_chi_square,
    "fisher_exact": _bulgu_chi_square,
    "ttest": _bulgu_ttest,
    "mann_whitney": _bulgu_mann_whitney,
    "anova": _bulgu_anova,
    "tukey": _bulgu_tukey,
    "kruskal_wallis": _bulgu_kruskal,
    "dunn": _bulgu_dunn,
    "correlation": _bulgu_correlation_matrix,
    "correlation_matrix": _bulgu_correlation_matrix,
    "regression": _bulgu_regression,
    "multiple_regression": _bulgu_multiple_regression,
    "paired_ttest": _bulgu_paired_ttest,
    "paired_wilcoxon": _bulgu_paired_wilcoxon,
    "cronbach": _bulgu_cronbach,
}


def has_bulgu_template(result: dict) -> bool:
    return result.get("type") in _TEMPLATE_HANDLERS


def generate_bulgu_from_template(
    result: dict,
    label_map: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    rtype = result.get("type")
    handler = _TEMPLATE_HANDLERS.get(rtype)
    if not handler:
        return None
    text = handler(result)
    if not text:
        return None
    if label_map:
        for code, label in sorted(label_map.items(), key=lambda x: -len(x[0])):
            if code and label:
                text = text.replace(code, label)
    return apply_academic_text_rules(text)


def compact_result_summary(result: dict) -> dict:
    """Genel değerlendirme için kompakt özet."""
    rtype = result.get("type", "")
    vars_part = ""
    if result.get("var1") and result.get("var2"):
        vars_part = f"{result.get('var1')}×{result.get('var2')}"
    elif result.get("variable"):
        vars_part = str(result.get("variable"))
    elif result.get("variables"):
        vars_part = "×".join(result["variables"][:3])
    direction = ""
    if rtype == "ttest":
        groups = result.get("groups") or []
        higher = _higher_group_name(groups, "mean")
        if higher:
            direction = f"{higher}>diğer"
    summary = {
        "test": rtype,
        "vars": vars_part,
        "sig": bool(result.get("significant")),
        "p": fmt_p(result.get("p")) if result.get("p") is not None else None,
    }
    if direction:
        summary["direction"] = direction
    return summary
