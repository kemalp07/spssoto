"""Ortak bulgu yorumlama motoru — tutarlılık, etiket temizliği ve kalite doğrulama."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from formatting import fmt_p, fmt_r, apply_academic_text_rules, substitute_variable_codes
from akademik_rehber.loader import (
    decision_phrase,
    effect_size_label,
    hypothesis_phrase,
    label_cleanup_patterns,
    llm_compact_rules,
    posthoc_empty_phrase,
    qc_message,
)

P_THRESHOLD = 0.05

POSTHOC_FOR_PARENT = {
    "anova": "tukey",
    "kruskal_wallis": "dunn",
    "kruskal": "dunn",
}


def posthoc_type_for(result: dict) -> str:
    explicit = result.get("posthoc_type")
    if explicit:
        return str(explicit)
    parent = str(result.get("type") or "")
    if parent == "anova" and result.get("levene_violated"):
        return "games_howell"
    return POSTHOC_FOR_PARENT.get(parent, "")

SIG_POSITIVE_PATTERNS = (
    r"anlamlı\s+(?:bir\s+)?(?:fark|ilişki)\s+saptanmış",
    r"anlamlı\s+bulunmuştur",
    r"anlamlı\s+yordayıcı",
    r"daha\s+yüksek(?:tir| olduğu)",
    r"istatistiksel\s+olarak\s+anlamlı",
)
SIG_NEGATIVE_PATTERNS = (
    r"anlamlı\s+(?:bir\s+)?(?:fark|ilişki)\s+saptanmamış",
    r"anlamlı\s+bulunmamış",
    r"anlamlı\s+yordayıcı\s+etkisi\s+saptanmamış",
    r"anlamlı\s+ilişki\s+saptanmamış",
)


def p_txt(p: Optional[float]) -> str:
    if p is None:
        return "—"
    p = float(p)
    if p < 0.001:
        return "p < .001"
    return f"p = {fmt_p(p)}"


def cronbach_tier(alpha: Optional[float]) -> str:
    if alpha is None:
        return ""
    a = float(alpha)
    if a >= 0.90:
        return "Mükemmel"
    if a >= 0.80:
        return "Çok İyi"
    if a >= 0.70:
        return "İyi"
    if a >= 0.60:
        return "Kabul Edilebilir"
    return "Düşük"


def cronbach_warning(alpha: Optional[float]) -> Optional[str]:
    if alpha is None:
        return None
    a = float(alpha)
    if a < 0.60:
        return (
            "Cronbach α değeri düşük düzeydedir; ölçek maddelerinin iç tutarlılığı "
            "sınırlı olabilir ve yorum dikkatle yapılmalıdır."
        )
    if a < 0.70:
        return (
            "Güvenilirlik katsayısı kabul edilebilir sınırın (α ≥ .70) altındadır; "
            "madde analizi veya ölçek revizyonu değerlendirilebilir."
        )
    return None


def corr_strength_label(r: float) -> str:
    return effect_size_label("correlation", r) or "zayıf"


def corr_direction_label(r: float) -> str:
    return "pozitif" if float(r) >= 0 else "negatif"


def sig_phrase(significant: bool, pos: str, neg: str) -> str:
    return pos if significant else neg


def clean_label_text(text: str) -> str:
    if not text:
        return ""
    result = re.sub(r"\s+", " ", str(text).strip())
    dup_patterns = tuple(label_cleanup_patterns()) + (
        (r"\bpuanlarının\s+puanlarının\b", "puanlarının"),
        (r"\bdeğerlerinin\s+değerlerinin\b", "değerlerinin"),
        (r"\btoplam\s+toplam\b", "toplam"),
    )
    for pattern, repl in dup_patterns:
        if isinstance(pattern, str) and not pattern.startswith("("):
            result = result.replace(pattern, repl)
        else:
            result = re.sub(pattern, repl, result, flags=re.I)
    return result


def normalize_measure_label(label: str) -> str:
    """Bulgu cümlesinde 'X puanlarının' tekrarını önler."""
    label = clean_label_text(label)
    lower = label.lower()
    for suffix in (" toplam puanları", " puanları", " toplam puan", " puan"):
        if lower.endswith(suffix):
            return label[: -len(suffix)].strip()
    return label


def comparison_intro(result: dict) -> str:
    outcome = normalize_measure_label(result.get("outcome_label") or "")
    grouping = clean_label_text(result.get("grouping_label") or "")
    if outcome and grouping:
        return f"{outcome} puanlarının {grouping} değişkenine göre "
    return ""


def highest_group_name(groups: List[dict], key: str = "mean") -> Optional[str]:
    best_name: Optional[str] = None
    best_val: Optional[float] = None
    for g in groups or []:
        name = str(g.get("name") or "").strip()
        if not name:
            continue
        val = g.get(key)
        if val is None:
            val = g.get("mean")
        if val is None:
            continue
        fv = float(val)
        if best_val is None or fv > best_val:
            best_val = fv
            best_name = name
    return best_name


def _match_key(result: dict) -> Tuple[str, str]:
    g = str(
        result.get("grouping_name")
        or result.get("grouping_label")
        or ""
    ).strip().lower()
    o = str(
        result.get("outcome_name")
        or result.get("outcome_label")
        or ""
    ).strip().lower()
    return g, o


def find_posthoc_for_result(result: dict, all_results: List[dict]) -> Optional[dict]:
    parent_type = str(result.get("type") or "")
    want = posthoc_type_for(result)
    if not want or not all_results:
        return None
    g_key, o_key = _match_key(result)
    for other in all_results:
        if str(other.get("type") or "") != want:
            continue
        og, oo = _match_key(other)
        if g_key and og and g_key != og:
            continue
        if o_key and oo and o_key != oo:
            continue
        return other
    return None


def tukey_pair_text(pair: dict) -> str:
    gi = pair.get("group_i", "")
    gj = pair.get("group_j", "")
    diff = float(pair.get("mean_diff") or 0)
    p_part = p_txt(pair.get("p"))
    if diff > 0:
        return f"{gi} grubunun puanları {gj} grubundan daha yüksektir ({p_part})"
    if diff < 0:
        return f"{gj} grubunun puanları {gi} grubundan daha yüksektir ({p_part})"
    return f"{gi}–{gj} arasında anlamlı fark ({p_part})"


def dunn_pair_text(pair: dict) -> str:
    direction = (pair.get("direction") or "").strip()
    p_part = p_txt(pair.get("p"))
    gi = pair.get("group_i", "")
    gj = pair.get("group_j", "")
    if direction:
        return f"{gi}–{gj}: {direction} ({p_part})"
    return f"{gi}–{gj} arasında anlamlı fark ({p_part})"


def format_correlation_pair(pair: dict) -> str:
    r = float(pair.get("r") or 0)
    sym = pair.get("symbol", "r")
    direction = corr_direction_label(r)
    strength = corr_strength_label(r)
    r2 = round(r * r, 3)
    return (
        f"{pair.get('var_i')} ile {pair.get('var_j')} arasında {strength} düzeyde "
        f"{direction} yönde anlamlı bir ilişki saptanmıştır "
        f"({sym} = {fmt_r(r)}, {p_txt(pair.get('p'))}; açıklanan varyans r² = {fmt_r(r2)})."
    )


def effect_clause(result: dict, value_key: str, interp_key: str, kind: str, symbol: str) -> str:
    val = result.get(value_key)
    if val is None:
        return ""
    interp = result.get(interp_key) or effect_size_label(kind, val)
    if not interp:
        return f"; {symbol} = {fmt_r(val)}"
    return f"; {symbol} = {fmt_r(val)}, etki büyüklüğü {interp} düzeydedir"


def group_median_snippet(groups: List[dict], name: Optional[str] = None) -> str:
    for g in groups or []:
        if name and str(g.get("name")) != name:
            continue
        med = g.get("median")
        if med is not None:
            return f"{g.get('name')} (Med = {fmt_r(med)})"
    return name or ""


def welch_note(result: dict) -> str:
    if result.get("type") != "ttest":
        return ""
    if result.get("welch"):
        return decision_phrase("welch_ttest")
    if result.get("levene_p") is not None:
        return decision_phrase("standard_ttest")
    return ""


def build_llm_rules_block() -> str:
    rules = llm_compact_rules()
    if not rules:
        return ""
    return "Kurallar:\n" + "\n".join(f"- {r}" for r in rules)


def append_posthoc_to_text(base: str, result: dict, all_results: Optional[List[dict]]) -> str:
    if not result.get("significant") or not all_results:
        return base
    posthoc = find_posthoc_for_result(result, all_results)
    if not posthoc:
        return base
    pairs = posthoc.get("significant_pairs") or []
    ph_type = str(posthoc.get("type") or "")
    if not pairs:
        empty = posthoc_empty_phrase(ph_type)
        if empty:
            return base + " " + empty
        label = {
            "tukey": "Tukey HSD",
            "games_howell": "Games-Howell",
            "dunn": "Dunn",
        }.get(ph_type, "Post-hoc")
        return base + f" {label} post-hoc analizinde gruplar arasında anlamlı fark saptanmamıştır."
    if ph_type == "tukey":
        parts = [tukey_pair_text(p) for p in pairs[:5]]
        return base + " Tukey HSD post-hoc analizinde " + "; ".join(parts) + "."
    if ph_type == "games_howell":
        parts = [tukey_pair_text(p) for p in pairs[:5]]
        return base + " Games-Howell post-hoc analizinde " + "; ".join(parts) + "."
    parts = [dunn_pair_text(p) for p in pairs[:5]]
    return base + " Dunn post-hoc analizinde " + "; ".join(parts) + "."


def apply_label_pipeline(text: str, label_map: Optional[Dict[str, str]] = None) -> str:
    if not text:
        return ""
    resolved = label_map or {}
    if resolved:
        text = substitute_variable_codes(text, resolved)
    text = clean_label_text(text)
    return apply_academic_text_rules(text)


def _text_matches(text: str, patterns: Tuple[str, ...]) -> bool:
    lower = (text or "").lower()
    return any(re.search(p, lower) for p in patterns)


def validate_bulgu_text(result: dict, text: str) -> List[dict]:
    """Bulgu metni ile tablo sonuçlarını karşılaştır."""
    issues: List[dict] = []
    if not text or not isinstance(result, dict):
        return issues

    table_no = result.get("table_number")
    sig = result.get("significant")
    if sig is not None:
        claims_sig = _text_matches(text, SIG_POSITIVE_PATTERNS)
        claims_nonsig = _text_matches(text, SIG_NEGATIVE_PATTERNS)
        if sig and claims_nonsig and not claims_sig:
            issues.append({
                "severity": "hata",
                "rule": "bulgu_sig_mismatch",
                "message": (
                    f"Tablo {table_no}: p < .05 olmasına rağmen bulgu metni anlamsızlık ifadesi içeriyor."
                ),
            })
        elif not sig and claims_sig and not claims_nonsig:
            issues.append({
                "severity": "hata",
                "rule": "bulgu_sig_mismatch",
                "message": (
                    f"Tablo {table_no}: p ≥ .05 olmasına rağmen bulgu metni anlamlılık ifadesi içeriyor."
                ),
            })

    p_val = result.get("p")
    if p_val is not None and sig is not None:
        computed_sig = float(p_val) < P_THRESHOLD
        if computed_sig != bool(sig):
            issues.append({
                "severity": "hata",
                "rule": "p_flag_mismatch",
                "message": (
                    f"Tablo {table_no}: significant bayrağı ile p değeri tutarsız "
                    f"(p = {fmt_p(p_val)})."
                ),
            })

    groups = result.get("groups") or []
    rtype = str(result.get("type") or "")
    if sig and groups and rtype in ("ttest", "mann_whitney", "anova", "kruskal_wallis", "kruskal"):
        key = "median" if rtype in ("mann_whitney", "kruskal_wallis", "kruskal") else "mean"
        highest = highest_group_name(groups, key)
        for pattern in (
            r"([^.;\]]+?) grubunun ortalaması daha yüksektir",
            r"([^.;\]]+?) grubunun medyanı daha yüksektir",
        ):
            m = re.search(pattern, text, re.I)
            if m and highest:
                claimed = m.group(1).strip()
                if claimed.lower() != highest.lower():
                    issues.append({
                        "severity": "hata",
                        "rule": "claimed_higher_mismatch",
                        "message": (
                            f"Tablo {table_no}: '{claimed}' yüksek grubu olarak belirtilmiş; "
                            f"grup değerlerine göre en yüksek '{highest}'."
                        ),
                    })
                break

    lower = (text or "").lower()
    if rtype in ("mann_whitney", "kruskal_wallis", "kruskal", "dunn", "paired_wilcoxon"):
        if re.search(r"\bortalama\b", lower) and "medyan" not in lower:
            issues.append({
                "severity": "hata",
                "rule": "nonparametric_uses_mean",
                "message": f"Tablo {table_no}: {qc_message('nonparametric_uses_mean')}",
            })
    if rtype == "chi_square" and sig and result.get("effect_size") is not None:
        sym = str(result.get("effect_symbol") or "").lower()
        if sym and sym not in lower and "cramer" not in lower and "φ" not in text and "phi" not in lower:
            issues.append({
                "severity": "uyari",
                "rule": "chi_sig_without_effect",
                "message": f"Tablo {table_no}: {qc_message('chi_sig_without_effect')}",
            })
    if rtype == "anova" and result.get("levene_violated") and "tukey" in lower:
        if not result.get("welch_anova"):
            issues.append({
                "severity": "uyari",
                "rule": "anova_levene_tukey",
                "message": f"Tablo {table_no}: {qc_message('anova_levene_tukey')}",
            })

    return issues


def finalize_bulgu(
    result: dict,
    raw_text: str,
    label_map: Optional[Dict[str, str]] = None,
    all_results: Optional[List[dict]] = None,
) -> Tuple[str, List[dict]]:
    text = apply_label_pipeline(raw_text, label_map)
    issues = validate_bulgu_text(result, text)
    if result.get("type") in POSTHOC_FOR_PARENT and all_results:
        posthoc = find_posthoc_for_result(result, all_results or [])
        if posthoc and result.get("significant"):
            pairs = posthoc.get("significant_pairs") or []
            ph_label = {
                "tukey": "Tukey",
                "games_howell": "Games-Howell",
                "dunn": "Dunn",
            }.get(str(posthoc.get("type") or ""), "Post-hoc")
            if not pairs and ph_label.lower() not in text.lower():
                issues.append({
                    "severity": "uyari",
                    "rule": "posthoc_no_pairs",
                    "message": (
                        f"Tablo {result.get('table_number')}: Anlamlı ana etki var ancak "
                        f"{ph_label} post-hoc analizinde anlamlı çift bulunmamış; "
                        "bulgu metninde belirtilmelidir."
                    ),
                })
    return text, issues


def compact_result_summary(
    result: dict,
    bulgu: str = "",
    all_results: Optional[List[dict]] = None,
) -> dict:
    """Genel değerlendirme ve kalite kontrol için birleşik özet."""
    rtype = str(result.get("type") or "")
    vars_part = ""
    if result.get("var1") and result.get("var2"):
        vars_part = f"{result.get('var1')}×{result.get('var2')}"
    elif result.get("grouping_label") and result.get("outcome_label"):
        vars_part = f"{result.get('grouping_label')}×{result.get('outcome_label')}"
    elif result.get("variable"):
        vars_part = str(result.get("variable"))
    elif result.get("variables"):
        vars_part = "×".join(str(v) for v in result["variables"][:3])

    summary: dict = {
        "test": rtype,
        "vars": vars_part,
        "sig": bool(result.get("significant")),
    }
    if result.get("p") is not None:
        summary["p"] = fmt_p(result.get("p"))
    if result.get("hypothesis_id"):
        summary["hypothesis_id"] = result["hypothesis_id"]

    groups = result.get("groups") or []
    key = "median" if rtype in ("mann_whitney", "kruskal_wallis", "kruskal", "dunn") else "mean"
    highest = highest_group_name(groups, key)
    if highest and result.get("significant"):
        summary["direction"] = f"{highest} daha yüksek"

    if rtype in POSTHOC_FOR_PARENT and all_results:
        posthoc = find_posthoc_for_result(result, all_results)
        summary["posthoc_present"] = posthoc is not None
        if posthoc:
            pairs = posthoc.get("significant_pairs") or []
            summary["posthoc_sig_pairs"] = len(pairs)
            if pairs:
                summary["posthoc_pairs"] = [
                    f"{p.get('group_i')}–{p.get('group_j')}" for p in pairs[:3]
                ]

    if rtype == "cronbach":
        alpha = result.get("alpha")
        if alpha is not None:
            summary["alpha"] = fmt_r(alpha)
            summary["reliability"] = cronbach_tier(alpha)
        for s in result.get("merged_scales") or []:
            if s.get("alpha") is not None:
                summary.setdefault("scales", []).append({
                    "name": s.get("name"),
                    "alpha": fmt_r(s.get("alpha")),
                    "tier": cronbach_tier(s.get("alpha")),
                })

    if bulgu:
        summary["bulgu_snippet"] = bulgu[:200]

    return summary


def build_summaries_from_results(
    results: List[dict],
    bulgular: Optional[Dict[str, str]] = None,
) -> List[dict]:
    bulgular = bulgular or {}
    out: List[dict] = []
    for idx, result in enumerate(results or []):
        if not isinstance(result, dict) or not result.get("type"):
            continue
        bulgu = bulgular.get(str(idx)) or bulgular.get(idx) or ""
        out.append(compact_result_summary(result, bulgu, results))
    return out


def generate_template_summary(
    summaries: List[dict],
    hypotheses: Optional[List[dict]] = None,
) -> str:
    """LLM yokken veya doğrulama sonrası şablon genel değerlendirme."""
    if not summaries:
        return ""

    sig_items = [s for s in summaries if s.get("sig")]
    nonsig_items = [s for s in summaries if not s.get("sig")]

    parts: List[str] = []
    if sig_items:
        sig_desc = []
        for s in sig_items[:4]:
            var = s.get("vars") or s.get("test") or "analiz"
            direction = s.get("direction") or ""
            posthoc = s.get("posthoc_sig_pairs")
            note = f"{var} için anlamlı sonuç"
            if direction:
                note += f" ({direction})"
            if posthoc is not None:
                if posthoc == 0:
                    note += "; post-hoc analizde anlamlı çift bulunmamıştır"
                elif posthoc:
                    pairs = ", ".join(s.get("posthoc_pairs") or [])
                    note += f"; post-hoc analizde {pairs} çiftleri anlamlıdır"
            sig_desc.append(note)
        parts.append(
            "Araştırma bulgularına göre "
            + "; ".join(sig_desc)
            + "."
        )

    if nonsig_items and len(nonsig_items) <= len(sig_items) + 2:
        nonsig_vars = ", ".join(
            (s.get("vars") or s.get("test") or "analiz") for s in nonsig_items[:3]
        )
        parts.append(
            f"{nonsig_vars} için istatistiksel olarak anlamlı fark veya ilişki saptanmamıştır."
        )

    cronbach = [s for s in summaries if s.get("test") == "cronbach"]
    for c in cronbach:
        scales = c.get("scales") or []
        if scales:
            rel_parts = [
                f"{sc.get('name')} (α = {sc.get('alpha')}, {sc.get('tier')})"
                for sc in scales
            ]
            parts.append(
                "Ölçek güvenilirlik analizinde " + "; ".join(rel_parts) + " düzeyinde iç tutarlılık belirlenmiştir."
            )
        elif c.get("alpha"):
            parts.append(
                f"Ölçek güvenilirlik katsayısı α = {c['alpha']} ({c.get('reliability', '')}) düzeyindedir."
            )

    if hypotheses:
        hyp_ids = {str(h.get("id")) for h in hypotheses if h.get("id")}
        matched_sig = {
            str(s.get("hypothesis_id"))
            for s in summaries
            if s.get("hypothesis_id") and s.get("sig")
        }
        matched_nonsig = {
            str(s.get("hypothesis_id"))
            for s in summaries
            if s.get("hypothesis_id") and not s.get("sig")
        }
        for hid in sorted(matched_sig & hyp_ids):
            parts.append(hypothesis_phrase(hid, True))
        for hid in sorted(matched_nonsig & hyp_ids):
            parts.append(hypothesis_phrase(hid, False))
        unsupported = hyp_ids - matched_sig - matched_nonsig
        if unsupported:
            parts.append(
                f"{', '.join(sorted(unsupported))} için yeterli analiz sonucu üretilememiştir."
            )

    if not parts:
        return "Analiz sonuçları tablolarda sunulmuş olup genel değerlendirme için anlamlı bulgular özetlenmiştir."

    return " ".join(parts)


def validate_summary_text(summary: str, summaries: List[dict]) -> List[dict]:
    """Genel değerlendirme ile özet satırlarını karşılaştır."""
    issues: List[dict] = []
    if not summary:
        return issues
    lower = summary.lower()
    for s in summaries:
        if s.get("sig") and "saptanmamış" in lower and (s.get("vars") or "").lower() in lower:
            issues.append({
                "severity": "uyari",
                "rule": "summary_sig_mismatch",
                "message": f"Genel değerlendirme, {s.get('vars')} için anlamlı sonucu yansıtmıyor olabilir.",
            })
    return issues
