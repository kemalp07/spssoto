"""Şablon tabanlı APA bulgu cümleleri — LLM gerektirmez."""
import re
from typing import Dict, List, Optional

from formatting import fmt_p, fmt_p_display, fmt_r, apply_academic_text_rules


def _lbl(name: str, label_map: Optional[Dict[str, str]]) -> str:
    if label_map and name in label_map and label_map[name]:
        return label_map[name]
    return name


def _p_txt(p: Optional[float]) -> str:
    if p is None:
        return "—"
    return fmt_p_display(p)


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
        return f"{base} (OR = {or_val}, p = {_p_txt(p)})."
    chi2 = result.get("chi2")
    return (
        f"{v1} ile {v2} arasındaki ilişkinin incelenmesinde "
        f"{_sig_phrase(sig, 'anlamlı bir ilişki saptanmıştır', 'anlamlı bir ilişki saptanmamıştır')} "
        f"(χ² = {chi2}, p = {_p_txt(p)})."
    )


def _group_rows(result: dict) -> List[dict]:
    rows = result.get("rows") or []
    parsed = []
    for row in rows:
        if len(row) < 3:
            continue
        if row[0] in ("H", "Toplam") or str(row[0]).startswith("χ"):
            continue
        parsed.append({"group": row[0], "n": row[1], "stat": row[2] if len(row) > 2 else ""})
    return parsed


def _bulgu_ttest(result: dict) -> Optional[str]:
    groups = _group_rows(result)
    if len(groups) < 2:
        return None
    t, p, d = result.get("t"), result.get("p"), result.get("cohens_d")
    df_t = None
    for row in result.get("rows") or []:
        if len(row) > 5 and row[4]:
            df_t = row[5]
            break
    g1, g2 = groups[0], groups[1]
    m1 = g1["stat"]
    m2 = g2["stat"]
    higher = g1["group"] if _mean_from_cell(m1) > _mean_from_cell(m2) else g2["group"]
    sig = result.get("significant", False)
    base = _sig_phrase(
        sig,
        f"gruplar arasında istatistiksel olarak anlamlı bir fark saptanmıştır; "
        f"{higher} grubunun ortalaması daha yüksektir",
        "gruplar arasında istatistiksel olarak anlamlı bir fark saptanmamıştır",
    )
    df_part = f"({df_t})" if df_t else ""
    return (
        f"Bağımsız örneklem t-testi sonucunda {base} "
        f"[t{df_part} = {t}, p = {_p_txt(p)}; Cohen's d = {d}]."
    )


def _mean_from_cell(cell: str) -> float:
    try:
        return float(str(cell).split("±")[0].strip())
    except ValueError:
        return 0.0


def _bulgu_mann_whitney(result: dict) -> Optional[str]:
    groups = _group_rows(result)
    if len(groups) < 2:
        return None
    u, z, p, r = result.get("U"), result.get("z"), result.get("p"), result.get("r")
    sig = result.get("significant", False)
    med1 = float(groups[0]["stat"]) if groups[0]["stat"] else 0
    med2 = float(groups[1]["stat"]) if groups[1]["stat"] else 0
    higher = groups[0]["group"] if med1 > med2 else groups[1]["group"]
    base = _sig_phrase(
        sig,
        f"gruplar arasında istatistiksel olarak anlamlı bir fark saptanmıştır; "
        f"{higher} grubunun medyanı daha yüksektir",
        "gruplar arasında istatistiksel olarak anlamlı bir fark saptanmamıştır",
    )
    return (
        f"Mann-Whitney U testi sonucunda {base} "
        f"(U = {u}, z = {z}, p = {_p_txt(p)}, r = {r})."
    )


def _bulgu_anova(result: dict) -> Optional[str]:
    f_val, p, eta = result.get("f"), result.get("p"), result.get("eta_squared")
    sig = result.get("significant", False)
    title = result.get("title", "")
    dep = title.split("Değerlerinin")[0].replace("Katılımcıların", "").strip() if "Değerlerinin" in title else "Bağımlı değişken"
    base = _sig_phrase(
        sig,
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmıştır",
        "gruplar arasında istatistiksel olarak anlamlı fark saptanmamıştır",
    )
    return (
        f"{dep} puanlarının gruplara göre tek yönlü ANOVA sonucunda {base} "
        f"(F = {f_val}, p = {_p_txt(p)}; η² = {fmt_r(eta)})."
    )


def _bulgu_tukey(result: dict) -> Optional[str]:
    sig_rows = []
    for row in result.get("rows") or []:
        if len(row) >= 5 and "*" in str(row[4]):
            sig_rows.append(f"{row[0]}–{row[1]} (p = {row[4]})")
    if not sig_rows:
        return "Tukey HSD post-hoc karşılaştırmasında gruplar arasında anlamlı fark saptanmamıştır."
    return (
        "Tukey HSD post-hoc karşılaştırmasında anlamlı fark gösteren gruplar: "
        + "; ".join(sig_rows[:5])
        + ("." if sig_rows else "")
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
    return f"Kruskal-Wallis testi sonucunda {base} (H = {h}, p = {_p_txt(p)}).{note}"


def _bulgu_dunn(result: dict) -> Optional[str]:
    sig_rows = []
    for row in result.get("rows") or []:
        if len(row) >= 6 and row[5] and "yüksek" in str(row[5]):
            sig_rows.append(f"{row[0]}–{row[1]}: {row[5]}")
    if not sig_rows:
        return "Dunn post-hoc karşılaştırmasında gruplar arasında anlamlı fark saptanmamıştır."
    return "Dunn post-hoc testinde anlamlı çiftler: " + "; ".join(sig_rows[:5]) + "."


def _bulgu_correlation_matrix(result: dict) -> Optional[str]:
    method = result.get("method", "Pearson")
    sym = "ρ" if method == "Spearman" else "r"
    vars_ = result.get("variables") or []
    rows = result.get("rows") or []
    sig_pairs = []
    for i, row in enumerate(rows):
        if i >= len(vars_):
            break
        for j, cell in enumerate(row[1:-1], start=0):
            if j >= len(vars_) or i == j:
                continue
            if "*" in str(cell):
                sig_pairs.append(f"{vars_[i]}–{vars_[j]} ({sym} = {cell})")
    if not sig_pairs:
        return f"{method} korelasyon analizinde değişkenler arasında anlamlı ilişki saptanmamıştır."
    return (
        f"{method} korelasyon analizinde anlamlı ilişkiler: "
        + "; ".join(sig_pairs[:6])
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
    return f"Basit doğrusal regresyon analizinde {base} (R² = {fmt_r(r2)}, p = {_p_txt(p)})."


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
        f"F = {f_val}, p = {_p_txt(p)}).{vif}"
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
        f"(ortalama fark = {diff}, t = {t}, p = {_p_txt(p)}; Cohen's d = {d})."
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
        f"(z = {z}, p = {_p_txt(p)}, r = {r})."
    )


def _bulgu_cronbach(result: dict) -> Optional[str]:
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
        groups = _group_rows(result)
        if len(groups) >= 2:
            higher = groups[0]["group"] if _mean_from_cell(groups[0]["stat"]) > _mean_from_cell(groups[1]["stat"]) else groups[1]["group"]
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
