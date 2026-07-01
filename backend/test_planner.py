"""Deterministik test planlama ve token-verimli LLM seçimi.

Not: Kural/sezgisel fonksiyonlar büyüdükçe plan_rules.py modülüne taşınabilir.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from scipy.stats import levene as scipy_levene

from data_profile import profile_from_dataframe, profile_json
from llm_router import (
    claude_decide,
    format_enrichment_block,
    gemini_enrich_profile,
    has_claude,
    merge_meta,
)
from constants import (
    REASON_CODES,
    REASON_TEMPLATES,
    PLAN_TEST_SYSTEM,
    SCALE_SCORE_RE,
    _ITEM_COL_RE,
    _TR_ASCII,
)
from data_cleaning import detect_scale_groups, is_numeric_continuous
from hypothesis_engine import apply_hypothesis_to_catalog, build_test_hypothesis_map
from layout_config import DEFAULT_LAYOUT_CONFIG, LayoutConfig
from schemas import Variable
from stat_tests import assess_normality
from table_budget import (
    PLAN_PROFILES,
    apply_table_budget,
    core_candidate_ids,
    enrich_catalog_metadata,
    estimate_table_count,
)

def build_plan(
    catalog: List[dict],
    profile: str,
    layout_config: Optional[LayoutConfig] = None,
) -> Tuple[List[dict], int]:
    """Profil bütçesine göre varsayılan seçimleri uygular."""
    return apply_table_budget(catalog, profile, layout_config)

_LABEL_MAX = 40
_MIN_GROUP_N = 10
_IMBALANCE_RATIO = 0.90

_DERIVED_CAT_SUFFIX_RE = re.compile(
    r"_(binary|grupu?|grubu|groups?|kategori|category|sinif|class|level|duzey|düzey|risk)$",
    re.I,
)
_AGE_BINNED_RE = re.compile(
    r"(yas|age).*(grup|group|kategori|category|bin|aralik|aralık)"
    r"|(grup|group|kategori|category).*(yas|age)",
    re.I,
)
_BINNED_DEMO_RE = re.compile(
    r"(grup|group|kategori|category|sinif|class|level|duzey|düzey)",
    re.I,
)
_MAX_AUTO_GROUPING_CHI = 6
_MAX_THESIS_RECOMMENDED = 28
_MAX_CHI_SQUARE = 5
_MAX_FREQ_TABLES = 10
_MAX_KESIN_FREQ = 3  # bolum, cinsiyet, yas — sadece ana demografikler
_MAX_KESIN_CHI = 3
_VISIBLE_CANDIDATE_CAP = 12

_COMPARISON_KEYWORDS = frozenset({
    "karsilastir", "karsilastirma", "fark", "gruplar", "gruplar arasi", "gruplararas",
    "farklilik", "etkisi",
    "sigara", "alkol", "gelir", "medeni", "egitim", "ilac",
})
_CORRELATION_KEYWORDS = ("iliski", "korelasyon", "baglanti")
_REGRESSION_KEYWORDS = ("yordama", "etki", "tahmin", "regresyon")
_COMPARISON_TESTS = frozenset({
    "ttest", "mann_whitney", "anova", "kruskal_wallis", "chi_square",
})
_LIFESTYLE_VARS = frozenset({"dbf_sk", "dbf_ak", "dbf_ik", "dbf_kh"})
_CORRELATION_TESTS = frozenset({"correlation"})

_TEST_DISPLAY_PLANNER = {
    "ttest": "bağımsız örneklem t-testi",
    "mann_whitney": "Mann-Whitney U testi",
    "anova": "tek yönlü ANOVA",
    "kruskal_wallis": "Kruskal-Wallis H testi",
    "chi_square": "ki-kare bağımsızlık testi",
    "correlation": "Pearson/Spearman korelasyon analizi",
    "descriptive": "tanımlayıcı istatistikler",
    "frequency": "frekans analizi",
    "cronbach": "Cronbach alfa güvenirlik analizi",
}

TIER_KESIN = "kesin_onerilen"
TIER_ONERILEN = "onerilen"
TIER_ONERILMEYEN = "onerilmeyen"

_logger = logging.getLogger(__name__)

# test_adı: (min_grup, max_grup, bagimsiz_tip, bagimli_tip)
TEST_RULES: Dict[str, Tuple[Optional[int], Optional[int], Optional[str], Optional[str]]] = {
    "ttest": (2, 2, "categorical", "continuous"),
    "welch": (2, 2, "categorical", "continuous"),
    "mann_whitney": (2, 2, "categorical", "continuous"),
    "anova": (3, 99, "categorical", "continuous"),
    "kruskal_wallis": (3, 99, "categorical", "continuous"),
    "chi_square": (2, 99, "categorical", "categorical"),
    "correlation": (None, None, "continuous", "continuous"),
    "paired_ttest": (2, 2, "categorical", "continuous"),
    "wilcoxon": (2, 2, "categorical", "continuous"),
    "regression": (None, None, "continuous", "continuous"),
    "cronbach": (None, None, None, "continuous"),
    "frequency": (None, None, None, "categorical"),
    "descriptive": (None, None, None, "continuous"),
}


def _is_plan_excluded(var: Variable) -> bool:
    """Classify'da exclude / dahil etme işaretli değişken."""
    if not var.included:
        return True
    return (var.role or "").strip().lower() == "exclude"


def _plan_active_variables(variables: List[Variable]) -> List[Variable]:
    return [v for v in variables if not _is_plan_excluded(v)]


def _raw_age_unique_count(df: pd.DataFrame, var_name: str) -> int:
    if var_name not in df.columns:
        return 0
    return int(pd.to_numeric(df[var_name], errors="coerce").dropna().nunique())


def _skip_raw_age_frequency(
    df: pd.DataFrame,
    var: Variable,
    has_binned_age: bool = False,
) -> bool:
    """Ham yaş >10 benzersiz değer → frekans yerine tanımlayıcı istatistik."""
    if not is_raw_age_var(var.name, var.label or ""):
        return False
    if has_binned_age:
        return True
    return _raw_age_unique_count(df, var.name) > 10


def validate_test_selection(
    test: str,
    grouping_var: Optional[Variable],
    outcome_var: Variable,
    n_groups: Optional[int] = None,
) -> Tuple[bool, str]:
    """Test seçiminin istatistiksel olarak geçerli olup olmadığını kontrol et."""
    for var in (grouping_var, outcome_var):
        if var and _is_plan_excluded(var):
            return False, f"'{var.name}' analiz dışı bırakıldı"

    rule = TEST_RULES.get(test)
    if not rule:
        return False, f"Bilinmeyen test: {test}"

    min_g, max_g, req_indep, req_dep = rule

    if req_dep and outcome_var.type != req_dep:
        return False, (
            f"{test} için bağımlı değişken {req_dep} olmalı, "
            f"'{outcome_var.name}' {outcome_var.type} tipinde"
        )

    if req_indep:
        if not grouping_var:
            return False, f"{test} için bağımsız değişken gerekli"
        if grouping_var.type != req_indep:
            return False, (
                f"{test} için bağımsız değişken {req_indep} olmalı, "
                f"'{grouping_var.name}' {grouping_var.type} tipinde"
            )

    gname = grouping_var.name if grouping_var else "—"
    if min_g and n_groups is not None and n_groups < min_g:
        return False, (
            f"{test} için en az {min_g} grup gerekli, "
            f"'{gname}' {n_groups} gruba sahip"
        )
    if max_g and n_groups is not None and n_groups > max_g:
        return False, (
            f"{test} için en fazla {max_g} grup olabilir, "
            f"'{gname}' {n_groups} gruba sahip → ANOVA kullan"
        )

    return True, ""


def _validate_candidate_for_add(
    test: str,
    vars: List[str],
    vmap: Dict[str, Variable],
    n_groups: Optional[int] = None,
) -> Tuple[bool, str]:
    """build_candidate_tests add() öncesi kural doğrulaması."""
    if not vars:
        return False, "Değişken listesi boş"

    for vname in vars:
        var = vmap.get(vname)
        if var and _is_plan_excluded(var):
            return False, f"'{vname}' analiz dışı bırakıldı"

    if test == "cronbach":
        for vname in vars:
            var = vmap.get(vname)
            if var is None:
                continue
            ok, msg = validate_test_selection(test, None, var, n_groups)
            if not ok:
                return ok, msg
        return True, ""

    if test in ("descriptive", "frequency"):
        var = vmap.get(vars[0])
        if var is None:
            return True, ""
        return validate_test_selection(test, None, var, n_groups)

    if test == "correlation":
        v1 = vmap.get(vars[0])
        v2 = vmap.get(vars[-1]) if len(vars) > 1 else None
        if v1 and v2:
            return validate_test_selection(test, v1, v2, n_groups)
        return True, ""

    if len(vars) >= 2:
        grouping = vmap.get(vars[0])
        outcome = vmap.get(vars[-1])
        if grouping and outcome:
            return validate_test_selection(test, grouping, outcome, n_groups)

    var = vmap.get(vars[0])
    if var:
        return validate_test_selection(test, None, var, n_groups)
    return True, ""


def _norm_var(name: str) -> str:
    return (name or "").lower().translate(_TR_ASCII).replace("_", "")


def _norm_text(name: str, label: str = "") -> str:
    return _norm_var(f"{name} {label or ''}")


def is_derived_categorical_name(name: str) -> bool:
    return bool(_DERIVED_CAT_SUFFIX_RE.search(name or ""))


def _scale_stem(name: str) -> str:
    lower = (name or "").lower()
    for suffix in ("_toplam", "_total", "_puan", "_skor", "_score", "_sum"):
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    m = _DERIVED_CAT_SUFFIX_RE.search(name or "")
    if m:
        return name[: m.start()]
    stem_match = re.match(r"^([a-zA-Z][a-zA-Z0-9]*)", name or "", re.I)
    return stem_match.group(1) if stem_match else name


def _has_related_total(stem: str, col_names: set, scale_groups: Dict[str, List[str]]) -> bool:
    stem_l = stem.lower()
    if stem_l in scale_groups:
        return True
    for col in col_names:
        if _scale_stem(col).lower() == stem_l and _is_total_score(col):
            return True
    return False


def is_redundant_derived_categorical(
    name: str,
    col_names: set,
    scale_groups: Dict[str, List[str]],
) -> bool:
    """İkili kodlama, aynı kökte çok kategorili türev varken gereksizdir."""
    if not is_derived_categorical_name(name):
        return False
    stem = _scale_stem(name)
    n = _norm_var(name)
    if "binary" not in n:
        return False
    for col in col_names:
        if col == name:
            continue
        if _scale_stem(col).lower() != stem.lower():
            continue
        cn = _norm_var(col)
        if any(k in cn for k in ("grup", "group", "kategori", "category")) and is_derived_categorical_name(col):
            return True
    return False


def is_derived_scale_split(
    name: str,
    col_names: set,
    scale_groups: Dict[str, List[str]],
) -> bool:
    """Ölçek toplamından türetilmiş grup/kategori değişkeni."""
    if not is_derived_categorical_name(name):
        return False
    return _has_related_total(_scale_stem(name), col_names, scale_groups)


def is_binned_age_var(name: str, label: str = "") -> bool:
    text = _norm_text(name, label)
    if _AGE_BINNED_RE.search(text):
        return True
    return bool(_BINNED_DEMO_RE.search(name or "")) and bool(
        re.search(r"yas|age", text, re.I)
    )


def is_raw_age_var(name: str, label: str = "") -> bool:
    if is_binned_age_var(name, label):
        return False
    return bool(re.search(r"\b(yas|age)\b", _norm_text(name, label), re.I))


def is_scale_item_name(name: str, scale_groups: Dict[str, List[str]]) -> bool:
    prefix = _scale_prefix(name)
    if name in scale_groups.get(prefix, []):
        return True
    return bool(_ITEM_COL_RE.search(name or ""))


def _column_names(variables: List[Variable]) -> set:
    return {v.name for v in variables if not _is_plan_excluded(v)}


def _var_by_name(variables: List[Variable]) -> Dict[str, Variable]:
    return {v.name: v for v in variables if not _is_plan_excluded(v)}


def should_include_frequency(
    var: Variable,
    col_names: set,
    scale_groups: Dict[str, List[str]],
    df: Optional[pd.DataFrame] = None,
    has_binned_age: bool = False,
) -> bool:
    if df is not None and _skip_raw_age_frequency(df, var, has_binned_age):
        return False
    if is_redundant_derived_categorical(var.name, col_names, scale_groups):
        return False
    if is_derived_scale_split(var.name, col_names, scale_groups):
        return False
    if is_derived_categorical_name(var.name):
        return False
    return True


def is_categorical_factor_var(
    var: Variable,
    col_names: set,
    scale_groups: Dict[str, List[str]],
) -> bool:
    if var.type != "categorical" or var.name not in col_names:
        return False
    if var.role != "grouping":
        return False
    if is_redundant_derived_categorical(var.name, col_names, scale_groups):
        return False
    if is_derived_scale_split(var.name, col_names, scale_groups):
        return False
    if is_derived_categorical_name(var.name):
        return False
    return True


def chi_square_allowed(
    left: Variable,
    right: Variable,
    col_names: set,
    scale_groups: Dict[str, List[str]],
) -> bool:
    if is_redundant_derived_categorical(left.name, col_names, scale_groups):
        return False
    if is_redundant_derived_categorical(right.name, col_names, scale_groups):
        return False
    if is_derived_scale_split(left.name, col_names, scale_groups):
        return False
    if is_derived_scale_split(right.name, col_names, scale_groups):
        return False
    if left.role == "outcome" and right.role == "outcome":
        return False
    if left.role == "grouping" and right.role == "grouping":
        return False
    if left.role != "grouping" and right.role != "grouping":
        return False
    stem_l, stem_r = _scale_stem(left.name).lower(), _scale_stem(right.name).lower()
    if (
        stem_l == stem_r
        and is_derived_categorical_name(left.name)
        and is_derived_categorical_name(right.name)
    ):
        return False
    return True


def _grouping_rank(variables: List[Variable]) -> Dict[str, int]:
    """Gruplandırıcıları tanım sırasına göre sırala (çoklu gruplandırıcı önceliği)."""
    grouping = [
        v.name for v in variables
        if not _is_plan_excluded(v) and v.role == "grouping" and v.type == "categorical"
    ]
    return {name: idx for idx, name in enumerate(grouping)}


def is_supplementary_grouping(name: str, rank_map: Dict[str, int]) -> bool:
    """Çok sayıda gruplandırıcı varken sonrakiler düşük öncelikli sayılır."""
    if name not in rank_map:
        return False
    return rank_map[name] >= _MAX_AUTO_GROUPING_CHI


def make_candidate_id(test: str, vars: List[str]) -> str:
    if test in ("descriptive", "normality", "correlation"):
        return test
    if test == "cronbach":
        return f"cronbach:{':'.join(sorted(vars))}"
    if test == "frequency" and len(vars) == 1:
        return f"frequency:{vars[0]}"
    if len(vars) >= 2:
        return f"{test}:{vars[0]}:{vars[1]}"
    return f"{test}:{':'.join(vars)}"


def _truncate_label(label: str) -> str:
    label = (label or "").strip()
    if len(label) <= _LABEL_MAX:
        return label
    return label[: _LABEL_MAX - 1] + "…"


def _var_lookup(variables: List[Variable]) -> Dict[str, Variable]:
    return {v.name: v for v in variables if v.included}


def _min_group_n(df: pd.DataFrame, grouping: str) -> int:
    counts = df[grouping].dropna().value_counts()
    return int(counts.min()) if len(counts) else 0


def _is_imbalanced(df: pd.DataFrame, grouping: str) -> bool:
    series = df[grouping].dropna()
    if len(series) == 0:
        return False
    return float(series.value_counts().max() / len(series)) > _IMBALANCE_RATIO


def _scale_prefix(name: str) -> str:
    m = re.match(r"^([a-zA-Z]+)", name or "", re.I)
    return m.group(1).lower() if m else ""


def _is_total_score(name: str) -> bool:
    lower = (name or "").lower()
    if SCALE_SCORE_RE.search(name or ""):
        return True
    return any(m in lower for m in ("toplam", "total", "puan", "skor", "score", "sum"))


def _is_tautological_pair(v1: str, v2: str, scale_groups: Dict[str, List[str]]) -> bool:
    p1, p2 = _scale_prefix(v1), _scale_prefix(v2)
    if not p1 or p1 != p2:
        return False
    items = scale_groups.get(p1, [])
    if not items:
        return False
    one_total = _is_total_score(v1) or _is_total_score(v2)
    one_item = v1 in items or v2 in items
    return one_total and one_item


def _normality_test_key(norm_info: dict) -> str:
    test = str(norm_info.get("test") or norm_info.get("method") or "").lower()
    if "shapiro" in test:
        return "shapiro-wilk"
    return "lilliefors"


def _outcome_measure_type(
    var: Variable,
    measure_map: Optional[Dict[str, str]] = None,
) -> str:
    measure = str((measure_map or {}).get(var.name, "")).lower()
    if measure == "ordinal":
        return "ordinal"
    if measure == "nominal":
        return "nominal"
    if var.type == "categorical":
        return "nominal"
    return "continuous"


def _levene_assessment(
    df: pd.DataFrame,
    grouping: str,
    outcome: str,
) -> Tuple[Optional[float], Optional[bool]]:
    groups = df.groupby(grouping)[outcome].apply(
        lambda x: pd.to_numeric(x, errors="coerce").dropna().tolist()
    )
    group_lists = [g for g in groups if len(g) >= 2]
    if len(group_lists) < 2:
        return None, None
    _, lev_p = scipy_levene(*group_lists)
    p_val = round(float(lev_p), 3)
    return p_val, bool(p_val >= 0.05)


def _planner_test_display(test: str, welch: bool = False) -> str:
    base = _TEST_DISPLAY_PLANNER.get(test, test)
    if welch and test == "ttest":
        return "Welch düzeltmeli bağımsız örneklem t-testi"
    if welch and test == "anova":
        return "Welch ANOVA ve Games-Howell post-hoc testi"
    return base


def _build_comparison_decision_log(
    df: pd.DataFrame,
    grouping: Variable,
    outcome: Variable,
    norm_map: Dict[str, dict],
    n_groups: int,
    measure_map: Optional[Dict[str, str]] = None,
) -> Tuple[str, dict]:
    ov_type = _outcome_measure_type(outcome, measure_map)
    outcome_label = _truncate_label(outcome.label or outcome.name)

    if ov_type == "ordinal":
        test = "mann_whitney" if n_groups == 2 else "kruskal_wallis"
        display = _planner_test_display(test)
        reason = (
            f"{outcome_label} sıralı (ordinal) ölçüm düzeyindedir; "
            f"parametrik varsayımlar uygulanmadı → {display} seçildi"
        )
        return test, {
            "normality_test": None,
            "normality_p": None,
            "normality_passed": None,
            "levene_p": None,
            "levene_passed": None,
            "selected_test": test,
            "reason": reason,
        }

    norm_info = norm_map.get(outcome.name, {})
    norm_key = _normality_test_key(norm_info)
    norm_p = norm_info.get("p")
    normal = bool(norm_info.get("normal", True))
    is_parametric = bool(norm_info.get("is_parametric", normal))
    n_obs = int(norm_info.get("n", 0))
    p_str = f"{norm_p:.3f}" if norm_p is not None else "—"
    norm_label = "Shapiro-Wilk" if norm_key == "shapiro-wilk" else "Lilliefors düzeltmeli KS"

    # n>200'de assess_normality p değerini değil çarpıklık/basıklık kriterini kullanır.
    # p<0.05 olsa bile CLT gereği normal=True dönebilir → reason çelişkili görünür.
    clt_override = (
        n_obs > 200
        and normal
        and norm_p is not None
        and float(norm_p) < 0.05
    )
    if clt_override:
        skew = norm_info.get("skewness")
        kurt = norm_info.get("kurtosis")
        skew_str = f"{skew:.3f}" if skew is not None else "?"
        kurt_str = f"{kurt:.3f}" if kurt is not None else "?"
        norm_reason = (
            f"n={n_obs} > 200, Merkezi Limit Teoremi gereği normallik varsayımı "
            f"karşılandı (çarpıklık={skew_str}, basıklık={kurt_str})"
        )
    else:
        p_display = f"p={p_str}" if norm_p is not None else ""
        norm_verdict = (
            "normallik sağlandı" if normal else "normallik varsayımı sağlanamadı"
        )
        norm_reason = (
            f"{norm_label} {p_display}, {norm_verdict}"
            if p_display else f"{norm_label}, {norm_verdict}"
        )

    if not is_parametric:
        test = "mann_whitney" if n_groups == 2 else "kruskal_wallis"
        display = _planner_test_display(test)
        reason = f"{norm_reason} → {display} seçildi"
        return test, {
            "normality_test": norm_key,
            "normality_p": norm_p,
            "normality_passed": False,
            "levene_p": None,
            "levene_passed": None,
            "selected_test": test,
            "reason": reason,
        }

    levene_p, levene_passed = _levene_assessment(df, grouping.name, outcome.name)
    welch = levene_passed is False
    test = "ttest" if n_groups == 2 else "anova"
    display = _planner_test_display(test, welch=welch)
    reason = norm_reason
    if levene_p is not None:
        lev_verdict = (
            "varyans homojenliği sağlandı"
            if levene_passed else "varyans homojenliği sağlanamadı"
        )
        reason += f"; Levene p={levene_p:.3f}, {lev_verdict}"
    reason += f" → {display} seçildi"
    return test, {
        "normality_test": norm_key,
        "normality_p": norm_p,
        "normality_passed": normal,
        "levene_p": levene_p,
        "levene_passed": levene_passed,
        "selected_test": test,
        "welch": welch,
        "reason": reason,
    }


def _build_chi_square_decision_log(outcome: Variable) -> dict:
    outcome_label = _truncate_label(outcome.label or outcome.name)
    return {
        "normality_test": None,
        "normality_p": None,
        "normality_passed": None,
        "levene_p": None,
        "levene_passed": None,
        "selected_test": "chi_square",
        "reason": (
            f"{outcome_label} nominal kategorik bağımlı değişkendir "
            f"→ ki-kare bağımsızlık testi seçildi"
        ),
    }


def format_methodology_paragraph(
    decision_log: dict,
    label_map: Optional[Dict[str, str]] = None,
    vars_: Optional[List[str]] = None,
) -> str:
    """APA 7 uyumlu metodoloji paragrafı — decision_log'dan deterministik üretim."""
    if not decision_log:
        return ""
    label_map = label_map or {}
    var_label = ""
    if vars_ and len(vars_) >= 2:
        var_label = label_map.get(vars_[1], vars_[1])
    elif vars_:
        var_label = label_map.get(vars_[0], vars_[0])

    parts: List[str] = []
    norm_test = decision_log.get("normality_test")
    if norm_test and var_label:
        norm_name = "Shapiro-Wilk" if norm_test == "shapiro-wilk" else "Lilliefors düzeltmeli KS"
        norm_p = decision_log.get("normality_p")
        p_disp = f"{norm_p:.3f}" if norm_p is not None else "—"
        parts.append(
            f"{var_label} için normallik {norm_name} testi ile incelendi (p = {p_disp})"
        )
        if decision_log.get("normality_passed") is True:
            parts.append("Normallik varsayımı sağlandı")
        elif decision_log.get("normality_passed") is False:
            parts.append("Normallik varsayımı sağlanamadı")

    levene_p = decision_log.get("levene_p")
    if levene_p is not None:
        if decision_log.get("levene_passed"):
            parts.append(
                f"Varyans homojenliği Levene testi ile kontrol edildi (p = {levene_p:.3f})"
            )
        else:
            parts.append(
                f"Varyans homojenliği Levene testi ile kontrol edildi (p = {levene_p:.3f}); "
                f"homojenlik varsayımı sağlanamadı"
            )

    selected = decision_log.get("selected_test", "")
    welch = decision_log.get("welch")
    test_name = _planner_test_display(str(selected), welch=bool(welch))
    if not parts:
        reason = str(decision_log.get("reason") or "").strip()
        if reason:
            return reason if reason.endswith(".") else f"{reason}."
        return f"Bu nedenle {test_name} uygulandı."

    text = ". ".join(parts) + f". Bu nedenle {test_name} uygulandı."
    return text if text.endswith(".") else f"{text}."


def score_candidates_from_context(
    candidates: List[dict],
    etik_text: str,
    variable_labels: Dict[str, str],
) -> List[dict]:
    """Kural tabanlı aday puanlama — AI yerine etik belge bağlamı."""
    etik_blob = _norm_var(etik_text or "")
    no_context = not etik_blob.strip()

    scored: List[dict] = []
    for cand in candidates:
        item = dict(cand)
        score = 0
        vars_ = item.get("vars") or []
        test = str(item.get("test") or "")

        if no_context:
            score = 2
        else:
            for var_name in vars_:
                name_norm = _norm_var(var_name)
                label_norm = _norm_var(variable_labels.get(var_name, var_name))
                if name_norm and name_norm in etik_blob:
                    score += 2
                    break
                if label_norm and len(label_norm) >= 2 and label_norm in etik_blob:
                    score += 2
                    break

            if any(k in etik_blob for k in _COMPARISON_KEYWORDS) and test in _COMPARISON_TESTS:
                score += 1
            if any(k in etik_blob for k in _CORRELATION_KEYWORDS) and test in _CORRELATION_TESTS:
                score += 1
            if any(k in etik_blob for k in _REGRESSION_KEYWORDS):
                score += 1

        vars_lower = {str(v).lower() for v in vars_}
        if vars_lower & _LIFESTYLE_VARS:
            score = max(score, 1)

        if score >= 2:
            relevance_flag = "uygun"
        elif score == 1:
            relevance_flag = "olası"
        else:
            relevance_flag = "düşük_öncelik"

        item["relevance_score"] = score
        item["relevance_flag"] = relevance_flag
        scored.append(item)

    return scored


def partition_scored_candidates(
    scored: List[dict],
    cap: int = _VISIBLE_CANDIDATE_CAP,
) -> Tuple[List[dict], List[dict]]:
    """Birincil (max cap) ve accordion (düşük öncelik + taşan) adayları ayır."""
    ranked = sorted(
        [c for c in scored if c.get("relevance_flag") in ("uygun", "olası")],
        key=lambda c: (-int(c.get("relevance_score", 0)), str(c.get("seq", ""))),
    )
    primary = ranked[:cap]
    primary_ids = {c["id"] for c in primary}
    accordion = [
        c for c in ranked[cap:]
        if c["id"] not in primary_ids
    ]
    accordion.extend(
        c for c in scored
        if c.get("relevance_flag") == "düşük_öncelik" and c["id"] not in primary_ids
    )
    seen: set = set()
    deduped_accordion: List[dict] = []
    for c in accordion:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        deduped_accordion.append(c)
    return primary, deduped_accordion


def build_candidate_tests(
    df: pd.DataFrame,
    variables: List[Variable],
    norm_map: Optional[Dict[str, dict]] = None,
    variable_measure: Optional[Dict[str, str]] = None,
) -> List[dict]:
    norm_map = norm_map or {}
    active = _plan_active_variables(variables)
    cat_vars = [v for v in active if v.type == "categorical"]
    cont_vars = [v for v in active if v.type == "continuous"]
    grouping_cat = [v for v in cat_vars if v.role == "grouping"]
    outcome_cat = [v for v in cat_vars if v.role == "outcome"]
    grouping_cont = [v for v in cont_vars if v.role == "grouping"]
    outcome_cont = [v for v in cont_vars if v.role == "outcome"]
    all_cont = outcome_cont + grouping_cont

    scale_groups = detect_scale_groups(list(df.columns))
    col_names = _column_names(variables)
    vmap = _var_by_name(variables)
    has_binned_age = any(
        is_binned_age_var(v.name, v.label or "") for v in active
    )
    candidates: List[dict] = []
    seq = 0

    def add(test: str, vars: List[str], **extra: Any) -> None:
        nonlocal seq
        n_groups = extra.get("n_groups")
        ok, reason = _validate_candidate_for_add(test, vars, vmap, n_groups)
        if not ok:
            _logger.warning(
                "[TEST VALIDATOR] Geçersiz aday reddedildi: %s %s (%s)",
                test, vars, reason,
            )
            return
        seq += 1
        cid = make_candidate_id(test, vars)
        candidates.append({
            "id": cid,
            "seq": f"t{seq}",
            "test": test,
            "vars": vars,
            "auto_flag": "uygun",
            **extra,
        })

    if outcome_cont:
        add("descriptive", [v.name for v in outcome_cont])

    grouping_rank = _grouping_rank(variables)
    primary_groupings = [
        v for v in grouping_cat
        if not is_supplementary_grouping(v.name, grouping_rank)
    ]

    for v in grouping_cat + outcome_cat:
        if v.name not in df.columns:
            continue
        if not should_include_frequency(v, col_names, scale_groups, df, has_binned_age):
            continue
        add("frequency", [v.name])

    chi_outcomes = [
        v for v in outcome_cat
        if v.name in df.columns and v.type == "categorical"
    ]
    chi_count = 0
    for cv in primary_groupings:
        if cv.name not in df.columns:
            continue
        for ov in chi_outcomes:
            if ov.name == cv.name:
                continue
            if chi_count >= _MAX_CHI_SQUARE:
                break
            if not chi_square_allowed(cv, ov, col_names, scale_groups):
                continue
            chi_log = _build_chi_square_decision_log(ov)
            add(
                "chi_square",
                [cv.name, ov.name],
                n_groups=int(df[cv.name].dropna().nunique()),
                min_group_n=_min_group_n(df, cv.name),
                decision_log=chi_log,
                reason=chi_log["reason"],
            )
            chi_count += 1
        if chi_count >= _MAX_CHI_SQUARE:
            break

    from stat_tests import _is_demographic_continuous

    cont_targets = [
        v for v in outcome_cont + grouping_cont
        if v.name in df.columns
        and is_numeric_continuous(df, v, norm_map)
        and not _is_demographic_continuous(v)
        and not is_scale_item_name(v.name, scale_groups)
        # recommended field'ı burada kullanılmamalı
    ]
    model_groupings = [
        v for v in grouping_cat
        if is_categorical_factor_var(v, col_names, scale_groups)
        and not is_supplementary_grouping(v.name, grouping_rank)
    ]

    for cv in model_groupings:
        if cv.name not in df.columns:
            continue
        n_groups = int(df[cv.name].dropna().nunique())
        if n_groups < 2:
            continue
        min_n = _min_group_n(df, cv.name)
        for sv in cont_targets:
            test, decision_log = _build_comparison_decision_log(
                df, cv, sv, norm_map, n_groups, variable_measure,
            )
            add(
                test,
                [cv.name, sv.name],
                n_groups=n_groups,
                min_group_n=min_n,
                parametric=test in ("ttest", "anova"),
                decision_log=decision_log,
                reason=decision_log.get("reason", ""),
            )

    corr_vars = [v for v in outcome_cont if is_numeric_continuous(df, v, norm_map)]
    if len(corr_vars) >= 2:
        parametric = all(
            norm_map.get(v.name, {}).get("is_parametric", True) for v in corr_vars
        )
        corr_log = {
            "normality_test": None,
            "normality_p": None,
            "normality_passed": None,
            "levene_p": None,
            "levene_passed": None,
            "selected_test": "correlation",
            "reason": (
                "Sürekli değişkenler arası ilişki için "
                + ("Pearson" if parametric else "Spearman")
                + " korelasyon analizi seçildi"
            ),
        }
        add(
            "correlation",
            [v.name for v in corr_vars],
            parametric=parametric,
            decision_log=corr_log,
            reason=corr_log["reason"],
        )

    for cols in scale_groups.values():
        if len(cols) >= 2 and all(c in df.columns for c in cols):
            add("cronbach", cols)

    return candidates


def apply_deterministic_flags(
    df: pd.DataFrame,
    variables: List[Variable],
    candidates: List[dict],
) -> List[dict]:
    vmap = _var_by_name(variables)
    col_names = _column_names(variables)
    scale_groups = detect_scale_groups(list(df.columns))
    chi_pairs = {
        (c["vars"][0], c["vars"][1])
        for c in candidates
        if c["test"] == "chi_square" and len(c["vars"]) >= 2
    }
    grp_pairs = {
        (c["vars"][0], c["vars"][1])
        for c in candidates
        if c["test"] in (
            "ttest", "mann_whitney", "anova", "kruskal_wallis",
        ) and len(c["vars"]) >= 2
    }
    double_test_pairs = chi_pairs & grp_pairs

    grouping_rank = _grouping_rank(variables)
    has_binned_age = any(
        is_binned_age_var(v.name, v.label or "")
        for v in variables if not _is_plan_excluded(v)
    )

    flagged: List[dict] = []
    for c in candidates:
        item = dict(c)
        flag = "uygun"
        test, vars_ = item["test"], item.get("vars") or []

        if (
            flag == "uygun"
            and test == "frequency"
            and len(vars_) == 1
            and vars_[0] in vmap
            and is_raw_age_var(vars_[0], vmap[vars_[0]].label or "")
        ):
            if has_binned_age or _raw_age_unique_count(df, vars_[0]) > 10:
                flag = "tekrarli_demografi"
        if flag == "uygun" and test in (
            "ttest", "mann_whitney", "anova", "kruskal_wallis", "chi_square",
        ) and len(vars_) >= 2:
            grouping = vars_[0]
            g_var = vmap.get(grouping)
            if g_var and is_supplementary_grouping(grouping, grouping_rank):
                flag = "ikincil_gruplandirma"
            elif any(
                is_derived_scale_split(v, col_names, scale_groups)
                for v in vars_[:2]
            ):
                flag = "turetilmis_tekrar"

        if item.get("min_group_n", _MIN_GROUP_N) < _MIN_GROUP_N:
            flag = "yetersiz_n"
        if (
            flag == "uygun"
            and len(vars_) >= 1
            and item["test"] not in ("descriptive", "normality", "correlation", "cronbach")
        ):
            grouping = vars_[0]
            if grouping in df.columns and _is_imbalanced(df, grouping):
                flag = "dengesiz_grup"
        if flag == "uygun" and test == "correlation" and len(vars_) >= 2:
            for i in range(len(vars_)):
                for j in range(i + 1, len(vars_)):
                    if _is_tautological_pair(vars_[i], vars_[j], scale_groups):
                        flag = "totoloji"
                        break
                if flag != "uygun":
                    break
        if (
            flag == "uygun"
            and test in ("ttest", "mann_whitney", "anova", "kruskal_wallis", "chi_square")
            and len(vars_) >= 2
            and (vars_[0], vars_[1]) in double_test_pairs
        ):
            flag = "cift_test"

        item["auto_flag"] = flag
        flagged.append(item)
    return flagged


def _compact_labels(variables: List[Variable]) -> Dict[str, str]:
    return {
        v.name: _truncate_label(v.label or v.name)
        for v in variables if not _is_plan_excluded(v)
    }


def _compact_candidates_for_llm(candidates: List[dict]) -> List[dict]:
    return [
        {
            "id": c["id"],
            "test": c["test"],
            "vars": c["vars"],
            "n_groups": c.get("n_groups"),
            "min_group_n": c.get("min_group_n"),
            "parametric": c.get("parametric"),
            "auto_flag": c["auto_flag"],
        }
        for c in candidates
        if c["auto_flag"] == "uygun"
    ]


def format_reason(
    reason_code: str,
    candidate: dict,
    variables: List[Variable],
) -> str:
    template = REASON_TEMPLATES.get(reason_code, "")
    vmap = _var_lookup(variables)
    vars_ = candidate.get("vars") or []
    ctx = {
        "n": candidate.get("min_group_n", "—"),
        "var_label": _truncate_label(vmap[vars_[0]].label) if vars_ and vars_[0] in vmap else vars_[0] if vars_ else "—",
        "var1_label": _truncate_label(vmap[vars_[0]].label) if vars_ and vars_[0] in vmap else "",
        "var2_label": _truncate_label(vmap[vars_[1]].label) if len(vars_) > 1 and vars_[1] in vmap else "",
    }
    try:
        return template.format(**ctx)
    except KeyError:
        return template


def candidate_display_label(candidate: dict, variables: List[Variable]) -> str:
    vmap = _var_lookup(variables)
    test = candidate["test"]
    vars_ = candidate.get("vars") or []
    labels = [_truncate_label(vmap[v].label) if v in vmap else v for v in vars_]
    names = {
        "descriptive": "Tanımlayıcı İstatistikler",
        "normality": "Normallik Testi",
        "frequency": f"Frekans — {labels[0]}" if labels else "Frekans",
        "chi_square": f"Ki-Kare — {' × '.join(labels)}",
        "ttest": f"t-Testi — {' × '.join(labels)}",
        "mann_whitney": f"Mann-Whitney — {' × '.join(labels)}",
        "anova": f"ANOVA — {' × '.join(labels)}",
        "kruskal_wallis": f"Kruskal-Wallis — {' × '.join(labels)}",
        "correlation": "Korelasyon Matrisi",
        "cronbach": f"Cronbach α — {len(vars_)} madde",
    }
    return names.get(test, f"{test} — {', '.join(labels)}")


def _var_role(variables: List[Variable], name: str) -> str:
    for v in variables:
        if not _is_plan_excluded(v) and v.name == name:
            return v.role or ""
    return ""


def pick_kesin_core_ids(
    uygun: List[dict],
    variables: List[Variable],
) -> List[str]:
    """Tez için vazgeçilmez çekirdek (~10–12 test) — kesin önerilen katmanı."""
    if not uygun:
        return []
    grouping_rank = _grouping_rank(variables)
    primary = {
        name for name, rank in grouping_rank.items()
        if rank == 0
    }
    if not primary:
        primary = {
            name for name, rank in grouping_rank.items()
            if rank < _MAX_AUTO_GROUPING_CHI
        }
    by_test: Dict[str, List[dict]] = {}
    for c in uygun:
        by_test.setdefault(c["test"], []).append(c)

    picked: List[str] = []

    for test in ("descriptive", "correlation", "cronbach"):
        for c in by_test.get(test, [])[:1]:
            picked.append(c["id"])

    freq_pool = sorted(
        by_test.get("frequency", []),
        key=lambda c: (
            0 if _var_role(variables, c["vars"][0]) == "grouping" else 1,
            grouping_rank.get(c["vars"][0], 99),
        ),
    )
    for c in freq_pool[:_MAX_KESIN_FREQ]:
        picked.append(c["id"])

    for test in ("ttest", "mann_whitney", "anova", "kruskal_wallis"):
        for c in by_test.get(test, []):
            if c["vars"] and c["vars"][0] in primary:
                picked.append(c["id"])

    for c in by_test.get("chi_square", [])[:_MAX_KESIN_CHI]:
        if c["vars"] and c["vars"][0] in primary:
            picked.append(c["id"])

    return list(dict.fromkeys(picked))


def pick_thesis_core_ids(
    uygun: List[dict],
    variables: List[Variable],
) -> List[str]:
    """Tez için geniş çekirdek paket (LLM yoksa veya aşırı seçimde)."""
    if not uygun:
        return []
    grouping_rank = _grouping_rank(variables)
    primary = {
        name for name, rank in grouping_rank.items()
        if rank < _MAX_AUTO_GROUPING_CHI
    }
    by_test: Dict[str, List[dict]] = {}
    for c in uygun:
        by_test.setdefault(c["test"], []).append(c)

    picked: List[str] = []

    def take(test: str, limit: int, pred=None) -> None:
        nonlocal picked
        for c in by_test.get(test, []):
            if limit <= 0:
                break
            if pred and not pred(c):
                continue
            picked.append(c["id"])
            limit -= 1

    take("descriptive", 1)
    take("correlation", 1)
    take("cronbach", 3)

    freq_pool = sorted(
        by_test.get("frequency", []),
        key=lambda c: (
            0 if _var_role(variables, c["vars"][0]) == "grouping" else 1,
            grouping_rank.get(c["vars"][0], 99),
        ),
    )
    for c in freq_pool[:_MAX_FREQ_TABLES]:
        picked.append(c["id"])

    for test in ("ttest", "mann_whitney", "anova", "kruskal_wallis"):
        for c in by_test.get(test, []):
            if c["vars"] and c["vars"][0] in primary:
                picked.append(c["id"])

    for c in by_test.get("chi_square", [])[:_MAX_CHI_SQUARE]:
        if c["vars"] and c["vars"][0] in primary:
            picked.append(c["id"])

    return list(dict.fromkeys(picked))


def _cap_selection(
    selected_ids: set,
    uygun: List[dict],
    variables: List[Variable],
) -> set:
    if len(selected_ids) <= _MAX_THESIS_RECOMMENDED:
        return selected_ids
    core = pick_thesis_core_ids(
        [c for c in uygun if c["id"] in selected_ids] or uygun,
        variables,
    )
    return set(core) if core else selected_ids


def _parse_llm_selection(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"selected": [], "excluded": []}
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {"selected": [], "excluded": []}
    selected = [str(x) for x in data.get("selected") or []]
    excluded = []
    for item in data.get("excluded") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("reason_code", "amac_disi"))
        if code not in REASON_CODES:
            code = "amac_disi"
        excluded.append({"id": str(item.get("id", "")), "reason_code": code})
    return {"selected": selected, "excluded": excluded}


async def select_tests_with_llm(
    uygun_candidates: List[dict],
    research_aim: str,
    labels: Dict[str, str],
    df: Optional[pd.DataFrame] = None,
    variables: Optional[List[Variable]] = None,
) -> Tuple[dict, dict]:
    meta: dict = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not uygun_candidates:
        return {"selected": [], "excluded": []}, meta
    if not has_claude():
        return {
            "selected": pick_thesis_core_ids(uygun_candidates, variables or []),
            "excluded": [],
        }, meta

    enrichment: dict = {}
    enrich_meta: dict = {}
    profile_block = ""
    if df is not None and variables:
        profile = profile_from_dataframe(df, variables)
        enrichment, enrich_meta = gemini_enrich_profile(
            "plan_tests", profile, research_aim,
        )
        profile_block = f"\nVeri profili:\n{profile_json(profile)}"

    compact = _compact_candidates_for_llm(uygun_candidates)
    user_msg = (
        f"Amaç: {research_aim.strip()[:500]}\n"
        f"Etiketler: {json.dumps(labels, ensure_ascii=False)}\n"
        f"{profile_block}"
        f"{format_enrichment_block(enrichment)}\n"
        f"Adaylar: {json.dumps(compact, ensure_ascii=False)}"
    )
    try:
        text, decide_meta = claude_decide(PLAN_TEST_SYSTEM, user_msg, max_tokens=2000)
        meta = merge_meta(enrich_meta, decide_meta)
        return _parse_llm_selection(text), meta
    except RuntimeError:
        return {
            "selected": pick_thesis_core_ids(uygun_candidates, variables or []),
            "excluded": [],
        }, meta


def build_norm_map(df: pd.DataFrame, variables: List[Variable]) -> Dict[str, dict]:
    norm_map: Dict[str, dict] = {}
    for v in variables:
        if v.included and v.type == "continuous" and v.name in df.columns:
            try:
                norm_map[v.name] = assess_normality(df[v.name])
            except Exception:
                norm_map[v.name] = {"is_parametric": True, "normal": True, "n": 0}
    return norm_map


RULE_EXCLUDED_CODES = frozenset({
    "ikincil_gruplandirma",
    "turetilmis_tekrar",
    "tekrarli_demografi",
    "yetersiz_n",
    "dengesiz_grup",
    "totoloji",
    "cift_test",
})


def build_test_catalog(
    uygun: List[dict],
    selected_ids: set,
    excluded: List[dict],
    variables: List[Variable],
    primary_ids: Optional[set] = None,
    accordion_ids: Optional[set] = None,
) -> List[dict]:
    """Kurallara uygun tüm adaylar — 3 katman: kesin / önerilen / önerilmeyen."""
    kesin_ids = set(pick_kesin_core_ids(uygun, variables))
    reason_by_id = {
        e["id"]: e
        for e in excluded
        if str(e.get("reason_code") or "") not in RULE_EXCLUDED_CODES
    }
    primary_ids = primary_ids or set()
    accordion_ids = accordion_ids or set()
    catalog: List[dict] = []
    for c in uygun:
        cid = c["id"]
        exc = reason_by_id.get(cid, {})
        relevance = c.get("relevance_flag", "uygun")
        in_accordion = cid in accordion_ids or relevance == "düşük_öncelik"

        if cid in kesin_ids:
            tier = TIER_KESIN
            enabled_default = True
            reason, reason_code = c.get("reason", ""), ""
        elif cid in selected_ids:
            tier = TIER_ONERILEN
            enabled_default = relevance == "uygun"
            reason = c.get("reason") or ""
            reason_code = ""
        elif in_accordion:
            tier = TIER_ONERILMEYEN
            enabled_default = False
            reason_code = "dusuk_oncelik"
            reason = c.get("reason") or format_reason(reason_code, c, variables)
        else:
            tier = TIER_ONERILMEYEN
            enabled_default = False
            reason_code = str(exc.get("reason_code") or "dusuk_oncelik")
            reason = c.get("reason") or exc.get("reason") or format_reason(reason_code, c, variables)

        catalog.append({
            **c,
            "label": candidate_display_label(c, variables),
            "count": 1,
            "tier": tier,
            "enabled_default": enabled_default,
            "reason": reason,
            "reason_code": reason_code,
            "selected": tier != TIER_ONERILMEYEN,
            "display_section": "accordion" if in_accordion and cid not in kesin_ids else "primary",
            "relevance_flag": relevance,
            "relevance_score": c.get("relevance_score", 0),
        })
    return catalog


async def plan_tests(
    df: pd.DataFrame,
    variables: List[Variable],
    research_aim: str,
    use_ai: bool = True,
    profile: str = "standart",
    layout_config: Optional[LayoutConfig] = None,
    hypotheses: Optional[List[dict]] = None,
    variable_measure: Optional[Dict[str, str]] = None,
    document_context: Optional[dict] = None,
) -> Tuple[List[dict], List[dict], List[dict], dict]:
    """Önerilen ve elenen test listeleri + meta döndürür."""
    from document_parser import apply_scale_test_requirements, resolve_scale_test_requirements
    from hypothesis_engine import translate_decision_reasons

    variables = _plan_active_variables(variables)

    norm_map = build_norm_map(df, variables)
    candidates = build_candidate_tests(df, variables, norm_map, variable_measure)
    if document_context:
        requirements = resolve_scale_test_requirements(
            document_context, list(df.columns), variables,
        )
        candidates = apply_scale_test_requirements(candidates, requirements, df)
    candidates = apply_deterministic_flags(df, variables, candidates)
    if not hypotheses and document_context:
        from etik_parser import parse_etik_to_hypotheses
        from document_context import effective_research_text

        etik = document_context.get("etik_kurul") or {}
        if not etik.get("parse_error"):
            etik_text = effective_research_text(document_context, "")
            uygun_for_etik = [c for c in candidates if c.get("auto_flag") == "uygun"]
            if etik_text.strip() and uygun_for_etik:
                from hypothesis_engine import filter_ai_hypothesis_matches

                raw_hyps = parse_etik_to_hypotheses(
                    etik_text, variables, uygun_for_etik,
                )
                hypotheses = filter_ai_hypothesis_matches(
                    raw_hyps, variables, uygun_for_etik,
                )
    by_id = {c["id"]: c for c in candidates}

    auto_excluded = [c for c in candidates if c["auto_flag"] != "uygun"]
    uygun = [c for c in candidates if c["auto_flag"] == "uygun"]

    labels = _compact_labels(variables)
    scored = score_candidates_from_context(uygun, research_aim, labels)
    primary_scored, accordion_scored = partition_scored_candidates(scored)
    primary_ids = {c["id"] for c in primary_scored}
    accordion_ids = {c["id"] for c in accordion_scored}

    llm_meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if use_ai and scored:
        reason_targets = primary_scored + accordion_scored
        reasons = [
            (c.get("decision_log") or {}).get("reason") or c.get("reason", "")
            for c in reason_targets
        ]
        translated, llm_meta = await translate_decision_reasons(reasons)
        for cand, tr_reason in zip(reason_targets, translated):
            if tr_reason:
                cand["reason"] = tr_reason
                if cand.get("decision_log"):
                    cand["decision_log"] = {**cand["decision_log"], "reason": tr_reason}

    kesin_ids = set(pick_kesin_core_ids(uygun, variables))
    selected_ids = {
        c["id"] for c in scored
        if c.get("relevance_flag") == "uygun" or c["id"] in kesin_ids
    }
    if not selected_ids and uygun:
        selected_ids = set(pick_thesis_core_ids(uygun, variables))

    recommended: List[dict] = []
    excluded: List[dict] = []

    for c in auto_excluded:
        excluded.append({
            **c,
            "reason_code": c["auto_flag"],
            "reason": format_reason(c["auto_flag"], c, variables),
            "selected": False,
            "label": candidate_display_label(c, variables),
        })

    scored_by_id = {c["id"]: c for c in scored}
    for c in uygun:
        enriched = scored_by_id.get(c["id"], c)
        if enriched["id"] in selected_ids:
            recommended.append({
                **enriched,
                "selected": True,
                "recommended": True,
                "label": candidate_display_label(enriched, variables),
                "count": 1,
            })
        elif not any(e["id"] == enriched["id"] for e in excluded):
            excluded.append({
                **enriched,
                "reason_code": "dusuk_oncelik",
                "reason": enriched.get("reason") or format_reason("dusuk_oncelik", enriched, variables),
                "selected": False,
                "label": candidate_display_label(enriched, variables),
            })

    catalog = build_test_catalog(
        scored, selected_ids, excluded, variables, primary_ids, accordion_ids,
    )
    cfg = layout_config or DEFAULT_LAYOUT_CONFIG
    core_ids = core_candidate_ids(uygun)
    enrich_catalog_metadata(catalog, cfg, core_ids)
    if hypotheses:
        apply_hypothesis_to_catalog(catalog, hypotheses, core_ids)
    catalog, estimated_tables = build_plan(catalog, profile, cfg)
    recommended = [c for c in catalog if c.get("enabled_default")]
    hyp_linked = sum(1 for c in catalog if c.get("hypothesis_id"))
    return recommended, excluded, catalog, {
        "llm_calls": llm_meta.get("llm_calls", 0),
        "approx_input_tokens": llm_meta.get("approx_input_tokens", 0),
        "approx_output_tokens": llm_meta.get("approx_output_tokens", 0),
        "llm_provider": llm_meta.get("llm_provider", ""),
        "llm_model": llm_meta.get("llm_model", ""),
        "enrich_provider": llm_meta.get("enrich_provider", ""),
        "enrich_model": llm_meta.get("enrich_model", ""),
        "total_candidates": len(candidates),
        "uygun_count": len(uygun),
        "kesin_count": sum(1 for c in catalog if c.get("tier") == TIER_KESIN),
        "onerilen_count": sum(1 for c in catalog if c.get("tier") == TIER_ONERILEN),
        "onerilmeyen_count": sum(1 for c in catalog if c.get("tier") == TIER_ONERILMEYEN),
        "recommended_count": sum(1 for c in catalog if c.get("enabled_default")),
        "optional_count": sum(1 for c in catalog if c.get("tier") == TIER_ONERILMEYEN),
        "rule_excluded_count": sum(
            1 for e in excluded if str(e.get("reason_code") or "") in RULE_EXCLUDED_CODES
        ),
        "catalog_count": len(catalog),
        "ai_used": bool(use_ai and scored),
        "scoring_used": True,
        "primary_visible_count": len(primary_scored),
        "accordion_count": len(accordion_scored),
        "profile": profile if profile in PLAN_PROFILES else "standart",
        "table_budget": PLAN_PROFILES.get(profile, PLAN_PROFILES["standart"]),
        "estimated_tables": estimated_tables,
        "hypothesis_count": len(hypotheses or []),
        "hypothesis_linked_count": hyp_linked,
        "norm_map": {
            k: {"is_parametric": v.get("is_parametric"), "normal": v.get("normal")}
            for k, v in norm_map.items()
        },
    }


def uses_granular_enabled_tests(enabled_tests: Optional[List[str]]) -> bool:
    if not enabled_tests:
        return False
    legacy = any(
        e.startswith("chi_square_") or e.startswith("ttest_anova_")
        for e in enabled_tests
    )
    if legacy:
        return False
    granular_markers = (
        ":", "descriptive", "normality", "correlation", "frequency", "cronbach",
        "ttest", "mann_whitney", "anova", "kruskal_wallis", "chi_square",
    )
    return any(
        any(m in e for m in granular_markers) for e in enabled_tests
    )


def granular_test_enabled(
    test: str,
    vars: List[str],
    enabled_tests: Optional[List[str]],
) -> bool:
    if enabled_tests is None:
        return True
    cid = make_candidate_id(test, vars)
    return cid in enabled_tests
