"""Eksik değer ve kategorik veri temizleme."""
import re
from typing import List, Optional, Dict, Tuple
import pandas as pd
import numpy as np
from schemas import Variable
from formatting import format_display_label, fmt_num
from constants import DEFAULT_MISSING_CODES, DEMO_LABEL_KEYWORDS, SCALE_SCORE_RE

def parse_missing_codes(codes: Optional[List[str]]) -> set:
    if not codes:
        return set(DEFAULT_MISSING_CODES)
    parsed = {str(c).strip() for c in codes if str(c).strip()}
    return parsed or set(DEFAULT_MISSING_CODES)

def matches_missing_code(val, codes: set) -> bool:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return False
    s = str(val).strip()
    if s in codes:
        return True
    try:
        num = float(s.replace(",", "."))
        if num == int(num) and str(int(num)) in codes:
            return True
    except ValueError:
        pass
    return False

def format_category_value(val) -> str:
    """Boş kategori veya eksik veri kodu → Kayıp Veri."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "Kayıp Veri"
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN", "<NA>", "NaT"):
        return "Kayıp Veri"
    if matches_missing_code(val, DEFAULT_MISSING_CODES):
        return "Kayıp Veri"
    return s

def apply_missing_codes(
    df: pd.DataFrame, variables: List[Variable], codes: Optional[List[str]] = None
) -> pd.DataFrame:
    """SPSS eksik veri kodlarını (99 vb.) NaN'a çevir."""
    code_set = parse_missing_codes(codes)
    df = df.copy()
    for v in variables:
        if v.name not in df.columns:
            continue
        if v.type != "categorical":
            continue
        mask = df[v.name].apply(lambda x: matches_missing_code(x, code_set))
        df.loc[mask, v.name] = np.nan
    return df


def apply_missing_codes_to_columns(
    df: pd.DataFrame,
    columns: List[str],
    codes: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Belirtilen sütunlarda eksik veri kodlarını (99 vb.) NaN'a çevir."""
    code_set = parse_missing_codes(codes)
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        mask = df[col].apply(lambda x: matches_missing_code(x, code_set))
        df.loc[mask, col] = np.nan
    return df

def is_missing_value(val, code_set: Optional[set] = None) -> bool:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return True
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN", "<NA>", "NaT"):
        return True
    codes = code_set if code_set is not None else set(DEFAULT_MISSING_CODES)
    return matches_missing_code(val, codes)

def _map_value_label(val, value_labels: Dict[str, str]):
    if pd.isna(val):
        return val
    key = str(val).strip()
    if key in value_labels:
        return value_labels[key]
    try:
        num = float(key.replace(",", "."))
        if num == int(num):
            int_key = str(int(num))
            if int_key in value_labels:
                return value_labels[int_key]
    except ValueError:
        pass
    return val

def _ordered_category_labels(value_labels: Optional[Dict[str, str]]) -> List[str]:
    if not value_labels:
        return []
    keys = sorted(
        value_labels.keys(),
        key=lambda x: int(float(x)) if str(x).replace(".", "", 1).replace("-", "", 1).isdigit() else str(x),
    )
    return [str(value_labels[k]) for k in keys]

def normalize_categorical_columns(
    df: pd.DataFrame, variables: List[Variable]
) -> pd.DataFrame:
    """Boş / geçersiz metin değerlerini kategorik sütunlarda NaN yap; value_labels ile kodları etiketle."""
    df = df.copy()
    for v in variables:
        if v.type != "categorical" or v.name not in df.columns:
            continue
        col = df[v.name]
        blank = col.apply(
            lambda x: x is None
            or (isinstance(x, float) and np.isnan(x))
            or str(x).strip() in ("", "nan", "None", "NaN", "<NA>", "NaT")
        )
        df.loc[blank, v.name] = np.nan
        if v.value_labels:
            vl = v.value_labels
            df[v.name] = df[v.name].apply(
                lambda x, labels=vl: _map_value_label(x, labels) if pd.notna(x) else x
            )
    return df

def _infer_valid_categories(series: pd.Series, code_set: set) -> set:
    """Beklenen kategori kümesini frekans profiline göre çıkar; nadir hatalı kodları dışla."""
    valid_s = series.dropna()
    valid_s = valid_s[~valid_s.apply(lambda x: matches_missing_code(x, code_set))]
    if len(valid_s) == 0:
        return set()

    counts = valid_s.value_counts()
    threshold = max(2, int(len(valid_s) * 0.005))

    numeric_map: Dict[float, object] = {}
    for val in counts.index:
        try:
            num = float(str(val).strip().replace(",", "."))
            if num == int(num):
                numeric_map[int(num)] = val
        except ValueError:
            pass

    if numeric_map and len(numeric_map) == len(counts):
        ints = sorted(numeric_map.keys())
        if ints == [1, 2]:
            return {str(numeric_map[i]).strip() for i in ints}
        if 1 in ints and 2 in ints:
            main_count = int(counts[numeric_map[1]]) + int(counts[numeric_map[2]])
            if main_count / len(valid_s) >= 0.95:
                return {str(numeric_map[1]).strip(), str(numeric_map[2]).strip()}
        valid_keys = set()
        for i in ints:
            raw = numeric_map[i]
            if int(counts[raw]) >= threshold:
                valid_keys.add(str(raw).strip())
        return valid_keys

    return {str(v).strip() for v, c in counts.items() if int(c) >= threshold}

def sanitize_invalid_categorical_codes(
    df: pd.DataFrame,
    variables: List[Variable],
    codes: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Beklenen kategori dışındaki hatalı girişleri (örn. Evet/Hayır'da 3) NaN yap."""
    code_set = parse_missing_codes(codes)
    df = df.copy()
    for v in variables:
        if v.type != "categorical" or v.name not in df.columns:
            continue
        if v.categories:
            valid = {str(c).strip() for c in v.categories}
        else:
            valid = _infer_valid_categories(df[v.name], code_set)
        if not valid:
            continue
        mask = df[v.name].notna() & ~df[v.name].apply(
            lambda x: is_missing_value(x, code_set)
            or str(x).strip() in valid
        )
        df.loc[mask, v.name] = np.nan
    return df

def detect_scale_groups(columns: List[str]) -> Dict[str, List[str]]:
    """NEQ_1, OYS1 gibi madde sütunlarını prefix gruplarına ayır.

    Türetilmiş sütunlar (_TOPLAM, _RISK, _BINARY, _GRUBU, _KATEGORI, vb.)
    madde olarak sayılmaz.
    """
    pattern = re.compile(r"^([a-zA-Z][a-zA-Z0-9]*)_(\d+)([a-z]*)$", re.IGNORECASE)
    derived_suffix = re.compile(
        r"_(toplam|total|puan|score|sum|risk|binary|grubu?|kategori|category|mean|ort|avg)$",
        re.I,
    )
    groups: Dict[str, List[str]] = {}
    for col in columns:
        if derived_suffix.search(col):
            continue
        m = pattern.match(col)
        if m:
            groups.setdefault(m.group(1).lower(), []).append(col)

    result: Dict[str, List[str]] = {}
    for prefix, cols in groups.items():
        base_cols = [c for c in cols if not derived_suffix.search(c)]
        if len(base_cols) >= 2:
            result[prefix] = sorted(
                base_cols,
                key=lambda x: int(re.search(r"\d+", x).group()),
            )
    return result


# Madde türev ekleri — ters/kodlanmış versiyonlar ayrı madde sayılmaz
ITEM_DERIV_SUFFIXES = (
    "_reversed", "_recoded", "_inverted",
    "_ters", "_rev", "_rc", "_inv",
    "_t", "_r",
)

ITEM_DERIV_PREFIXES = (
    "recoded_", "rev_", "inv_",
)

_ITEM_DERIV_SUFFIX_RE = (
    r"(?:_reversed|_recoded|_inverted|_ters|_rev|_rc|_inv|_t|_r)?"
)
_ITEM_DERIV_PREFIX_RE = r"(?:recoded_|rev_|inv_)?"
ITEM_COLUMN_PATTERN = re.compile(
    rf"^{_ITEM_DERIV_PREFIX_RE}[a-zA-Z_]{{1,20}}\d{{1,3}}{_ITEM_DERIV_SUFFIX_RE}$",
    re.I,
)

REVERSED_SUFFIX = re.compile(r"(_ters|_t|_rev|_r|_reversed|_rc|_inv)$", re.I)


def prefer_reversed_items(cols: List[str], all_cols: Optional[List[str]] = None) -> List[str]:
    """_ters/_T suffix'li sütunu orijinal yerine tercih et (SPSS ters puanlı sütun)."""
    source = all_cols if all_cols is not None else cols
    reversed_bases = {
        REVERSED_SUFFIX.sub("", c).lower()
        for c in source
        if REVERSED_SUFFIX.search(c)
    }
    result: List[str] = []
    seen: set = set()
    for col in cols:
        base = REVERSED_SUFFIX.sub("", col).lower()
        if not REVERSED_SUFFIX.search(col) and base in reversed_bases:
            continue
        if col not in seen:
            result.append(col)
            seen.add(col)
    return result


def prefer_original_items(cols: List[str], all_cols: Optional[List[str]] = None) -> List[str]:
    """Geriye uyumluluk — ters puanlanmış sütunu tercih eder."""
    return prefer_reversed_items(cols, all_cols)


def normalize_item_root(name: str) -> str:
    """Türev ön/son ekleri temizlenmiş madde kökü."""
    n = (name or "").strip().lower()
    for suffix in ITEM_DERIV_SUFFIXES:
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    for prefix in ITEM_DERIV_PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    return n


def has_item_deriv_affix(name: str) -> bool:
    n = (name or "").strip().lower()
    return any(n.endswith(s) for s in ITEM_DERIV_SUFFIXES) or any(
        n.startswith(p) for p in ITEM_DERIV_PREFIXES
    )


def is_item_column_name(name: str) -> bool:
    return bool(ITEM_COLUMN_PATTERN.match(name or ""))


def group_item_variants(columns: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for col in columns:
        groups.setdefault(normalize_item_root(col), []).append(col)
    return groups


def partition_item_variants(
    item_columns: List[str],
) -> Tuple[List[str], List[str], int]:
    """
    Madde listesi → (gösterim, cronbach, benzersiz madde sayısı).

    Türev sütunlar listede gösterilmez; cronbach'ta türev varsa o kullanılır.
    """
    if not item_columns:
        return [], [], 0

    display: List[str] = []
    cronbach: List[str] = []
    for _, cols in sorted(group_item_variants(item_columns).items()):
        cols_sorted = sorted(set(cols))
        bases = [c for c in cols_sorted if not has_item_deriv_affix(c)]
        derivs = [c for c in cols_sorted if has_item_deriv_affix(c)]

        if bases:
            display.append(bases[0])
        elif len(cols_sorted) == 1:
            display.append(cols_sorted[0])

        if derivs:
            cronbach.append(derivs[0])
        elif bases:
            cronbach.append(bases[0])
        elif cols_sorted:
            cronbach.append(cols_sorted[0])

    return display, cronbach, len(group_item_variants(item_columns))


def apply_scale_item_resolution(items: List[str]) -> dict:
    """Ölçek maddelerini gösterim ve cronbach için ayır."""
    display, cronbach, count = partition_item_variants(items)
    cronbach = prefer_reversed_items(cronbach, items)
    variant_map: Dict[str, str] = {}
    for _, cols in group_item_variants(items).items():
        group_display, group_cronbach, _ = partition_item_variants(cols)
        group_cronbach = prefer_reversed_items(group_cronbach, cols)
        if group_display and group_cronbach:
            variant_map[group_display[0]] = group_cronbach[0]
        elif group_display:
            variant_map[group_display[0]] = group_display[0]
    return {
        "items": display,
        "cronbach_items": cronbach,
        "item_count": count,
        "all_items": list(items),
        "item_variant_map": variant_map,
    }


def extract_item_number(col: str) -> Optional[int]:
    """Madde numarasını sütun adından çıkar (sbito_10_ters → 10)."""
    base = normalize_item_root(col)
    match = re.search(r"(\d+)$", base)
    if match:
        return int(match.group(1))
    match = re.search(r"_(\d+)", col or "")
    return int(match.group(1)) if match else None


def resolve_cronbach_column(col: str, df_columns: List[str]) -> str:
    """Veri setindeki gerçek sütun adını bul (büyük/küçük harf duyarsız)."""
    col_set = {str(c): c for c in df_columns}
    if col in col_set:
        return col_set[col]
    lower_map = {str(c).lower(): c for c in df_columns}
    return lower_map.get(str(col).lower(), col)


def pick_cronbach_column(
    col: str,
    df_columns: List[str],
    reverse_set: set,
) -> str:
    """
    Madde sütunu seç — çift ters önlenir.

    Ters madde + _ters/_T türevi varsa: hazır puanlı türevi kullan (formül yok).
    Aksi halde orijinal sütun; ters kodlama ayrıca uygulanır.
    """
    actual = resolve_cronbach_column(col, df_columns)
    if has_item_deriv_affix(actual):
        return actual
    num = extract_item_number(actual)
    if num is not None and num in reverse_set:
        root = normalize_item_root(actual)
        derivs = sorted(
            c for c in df_columns
            if normalize_item_root(c) == root and has_item_deriv_affix(c)
        )
        if derivs:
            return derivs[0]
    return actual


def build_cronbach_dataframe(
    df: pd.DataFrame,
    items: List[str],
    reverse_items: Optional[List[int]] = None,
    scale_range: Optional[List[float]] = None,
    missing_codes: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Cronbach veri matrisi.

    Liste düzeyinde ters puanlanmış (_ters/_T) maddeler tercih edilir; formül uygulanmaz.
    """
    reverse_set = {int(x) for x in (reverse_items or []) if x is not None}
    df_columns = list(df.columns)

    picked = prefer_reversed_items(items, df_columns)
    resolved: List[str] = []
    seen_roots: set = set()
    for col in picked:
        actual = pick_cronbach_column(col, df_columns, reverse_set)
        root = normalize_item_root(actual)
        if root in seen_roots or actual not in df_columns:
            continue
        seen_roots.add(root)
        resolved.append(actual)

    if len(resolved) < 2:
        return pd.DataFrame(), []

    work = df.copy()
    for col in resolved:
        work[col] = pd.to_numeric(
            work[col].astype(str).str.replace(",", ".", regex=False),
            errors="coerce",
        )

    work = apply_missing_codes_to_columns(work, resolved, missing_codes)
    items_df = work[resolved].copy()

    return items_df.dropna(), resolved


def _likert_bounds_from_scale_info(si: dict) -> Tuple[Optional[float], Optional[float]]:
    item_count = si.get("item_count")
    if not item_count:
        return None, None
    try:
        n_items = int(item_count)
    except (TypeError, ValueError):
        return None, None
    if n_items <= 0:
        return None, None
    likert_max = 5
    if si.get("likert"):
        m = re.search(r"(\d+)", str(si["likert"]))
        if m:
            likert_max = int(m.group(1))
    return float(n_items), float(n_items * likert_max)

def infer_theoretical_range(
    variable: Variable,
    df: pd.DataFrame,
    scale_info: Optional[dict] = None,
) -> Optional[str]:
    si = resolve_scale_info(variable, scale_info)
    if si and si.get("min_score") is not None and si.get("max_score") is not None:
        return f"{fmt_num(si['min_score'])} – {fmt_num(si['max_score'])}"
    if si:
        inferred_min, inferred_max = _likert_bounds_from_scale_info(si)
        if inferred_min is not None and inferred_max is not None:
            return f"{fmt_num(inferred_min)} – {fmt_num(inferred_max)}"
    if variable.scale_min is not None and variable.scale_max is not None:
        return f"{fmt_num(variable.scale_min)} – {fmt_num(variable.scale_max)}"

    prefix = re.match(r"^([a-zA-Z]+)", variable.name or "", re.I)
    prefix_key = prefix.group(1).lower() if prefix else ""
    groups = detect_scale_groups(list(df.columns))
    items = groups.get(prefix_key, [])
    if items:
        n_items = len(items)
        likert_max = 5
        if si and si.get("likert"):
            m = re.search(r"(\d+)", str(si["likert"]))
            if m:
                likert_max = int(m.group(1))
        return f"{fmt_num(n_items)} – {fmt_num(n_items * likert_max)}"
    return None

def filter_chi_square_data(
    df: pd.DataFrame,
    v1: Variable,
    v2: Variable,
    codes: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, int]:
    """Ki-kare matrisine yalnızca her iki değişkende de geçerli değeri olan satırları al."""
    code_set = parse_missing_codes(codes)
    sub = df[[v1.name, v2.name]].copy()
    invalid_mask = sub.apply(
        lambda row: is_missing_value(row[v1.name], code_set)
        or is_missing_value(row[v2.name], code_set)
        or format_category_value(row[v1.name]) == "Kayıp Veri"
        or format_category_value(row[v2.name]) == "Kayıp Veri",
        axis=1,
    )
    excluded = int(invalid_mask.sum())
    return sub.loc[~invalid_mask], excluded

def normalize_variable_labels(variables: List[Variable]) -> List[Variable]:
    return [
        v.model_copy(update={"label": format_display_label(v.name, v.label)})
        for v in variables
    ]

def _normalize_scale_key(s: str) -> str:
    tr = str(s).upper()
    for src, dst in [("Ö", "O"), ("Ş", "S"), ("İ", "I"), ("Ü", "U"), ("Ğ", "G"), ("Ç", "C")]:
        tr = tr.replace(src, dst)
    return tr

def resolve_scale_info(variable: Variable, scale_info: Optional[dict]) -> Optional[dict]:
    if not scale_info:
        return None
    if variable.label in scale_info:
        return scale_info[variable.label]
    if variable.name in scale_info:
        return scale_info[variable.name]
    name_upper = variable.name.upper()
    name_prefix = _normalize_scale_key(name_upper.split("_")[0])[:4]
    for short_name, info in scale_info.items():
        if not isinstance(info, dict):
            continue
        short_norm = _normalize_scale_key(short_name)[:4]
        full = info.get("full_name") or ""
        if full and variable.label == full:
            return info
        if name_prefix and short_norm and (
            name_prefix.startswith(short_norm[:3])
            or short_norm.startswith(name_prefix[:3])
        ):
            if "TOPLAM" in name_upper or variable.role == "outcome":
                return info
    return None

def apply_scale_info_to_variables(
    variables: List[Variable], scale_info: Optional[dict]
) -> List[Variable]:
    if not scale_info:
        return variables
    out: List[Variable] = []
    for v in variables:
        si = resolve_scale_info(v, scale_info)
        if not si:
            out.append(v)
            continue
        min_s, max_s = si.get("min_score"), si.get("max_score")
        if min_s is None or max_s is None:
            inferred_min, inferred_max = _likert_bounds_from_scale_info(si)
            if inferred_min is not None:
                min_s, max_s = inferred_min, inferred_max
        if min_s is not None and max_s is not None:
            v = v.model_copy(update={
                "scale_min": float(min_s),
                "scale_max": float(max_s),
            })
        out.append(v)
    return out

def normalize_continuous_columns(df: pd.DataFrame, variables: List[Variable]) -> pd.DataFrame:
    df = df.copy()
    for v in variables:
        if v.type != "continuous" or v.name not in df.columns:
            continue
        df[v.name] = (
            df[v.name].astype(str)
            .str.strip()
            .str.replace(",", ".", regex=False)
        )
        df[v.name] = pd.to_numeric(df[v.name], errors="coerce")
    return df

def is_numeric_continuous(df: pd.DataFrame, v: Variable, norm_map: dict) -> bool:
    """Gerçekten sayısal sürekli mi? Kategorik kodlanmış değilse."""
    if v.name not in df.columns:
        return False
    series = df[v.name].dropna()
    if len(series) < 3:
        return False
    unique_count = series.nunique()
    if unique_count < 10:
        return False
    return True

def missing_data_report(df: pd.DataFrame, variables: List[Variable]) -> list:
    total = len(df)
    report = []
    for v in variables:
        if v.name not in df.columns:
            continue
        col = df[v.name]
        missing = col.isna() | (col.astype(str).str.strip().isin(["", "nan", "None", "NaN"]))
        pct = round(float(missing.sum()) / total * 100, 1) if total else 0.0
        warning = "none"
        if pct > 30:
            warning = "high"
        elif pct > 10:
            warning = "medium"
        report.append({
            "column": v.label, "name": v.name,
            "missing_pct": pct, "missing_n": int(missing.sum()), "warning": warning,
        })
    return report


def prepare_analysis_df(
    df: pd.DataFrame,
    variables: List[Variable],
    missing_codes: Optional[List[str]] = None,
) -> pd.DataFrame:
    df = normalize_continuous_columns(df, variables)
    df = normalize_categorical_columns(df, variables)
    df = apply_missing_codes(df, variables, missing_codes)
    df = sanitize_invalid_categorical_codes(df, variables, missing_codes)
    for v in variables:
        if re.match(r"^vki$", v.name, re.I) and v.name in df.columns:
            max_val = df[v.name].max()
            if pd.notna(max_val) and max_val > 1000:
                df[v.name] = pd.to_numeric(df[v.name], errors="coerce")
    return df

