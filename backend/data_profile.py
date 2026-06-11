"""Deterministik veri profili — Gemini zenginleştirmesi ve Claude kararı için girdi."""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from scipy import stats

from data_cleaning import detect_scale_groups
from schemas import Variable

_DERIVED_SUFFIXES = (
    "_kategori", "_kat", "_grup", "_grubu", "_grp", "_binary", "_bin",
    "_risk", "_sinif", "_level", "_class", "_cut",
)

_STEM_SIMILARITY_MIN = 0.85
_CORR_MIN = 0.80
_LOW_CARDINALITY_MAX = 8
_WIDE_RANGE_MIN_UNIQUE = 9


def _normalize_var_stem(name: str) -> str:
    n = (name or "").lower().strip()
    for suffix in _DERIVED_SUFFIXES:
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    return re.sub(r"[_\s-]+", "", n)


def _stem_similarity(left: str, right: str) -> float:
    sa, sb = _normalize_var_stem(left), _normalize_var_stem(right)
    if not sa or not sb:
        return 0.0
    if sa == sb:
        return 1.0
    return SequenceMatcher(None, sa, sb).ratio()


def _numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _unique_count(series: pd.Series) -> int:
    return int(series.dropna().nunique())


def _is_wide_range_continuous(series: pd.Series) -> bool:
    numeric = _numeric_series(series).dropna()
    if len(numeric) < 5:
        return False
    span = float(numeric.max()) - float(numeric.min())
    return _unique_count(numeric) >= _WIDE_RANGE_MIN_UNIQUE and span > 3


def _is_low_cardinality(series: pd.Series) -> bool:
    return _unique_count(series) <= _LOW_CARDINALITY_MAX


def _spearman_abs(source: pd.Series, derived: pd.Series) -> Optional[float]:
    sub = pd.DataFrame({"s": _numeric_series(source), "d": _numeric_series(derived)}).dropna()
    if len(sub) < 10:
        sub = pd.DataFrame({"s": source, "d": derived}).dropna()
    if len(sub) < 10:
        return None
    try:
        r, _ = stats.spearmanr(sub["s"], sub["d"], nan_policy="omit")
    except Exception:
        return None
    if r is None or pd.isna(r):
        return None
    return abs(float(r))


def find_derived_variables(
    df: pd.DataFrame,
    variables: List[Variable],
) -> List[dict]:
    """Türev değişkenleri tespit eder — isim benzerliği + Spearman korelasyonu."""
    active = [v.name for v in variables if v.included and v.name in df.columns]
    hits: Dict[str, dict] = {}

    for i, left in enumerate(active):
        for right in active[i + 1:]:
            if _stem_similarity(left, right) < _STEM_SIMILARITY_MIN:
                continue
            s_left, s_right = df[left], df[right]
            if _is_wide_range_continuous(s_left) and _is_low_cardinality(s_right) and not _is_wide_range_continuous(s_right):
                derived, source = right, left
            elif _is_wide_range_continuous(s_right) and _is_low_cardinality(s_left) and not _is_wide_range_continuous(s_left):
                derived, source = left, right
            else:
                continue
            entry = hits.setdefault(derived, {
                "name": derived,
                "source": source,
                "rule_name": False,
                "rule_corr": False,
            })
            entry["rule_name"] = True
            entry["source"] = source

    for derived in active:
        d_series = df[derived]
        if not _is_low_cardinality(d_series):
            continue
        for source in active:
            if source == derived:
                continue
            if not _is_wide_range_continuous(df[source]):
                continue
            corr = _spearman_abs(df[source], d_series)
            if corr is None or corr <= _CORR_MIN:
                continue
            entry = hits.setdefault(derived, {
                "name": derived,
                "source": source,
                "rule_name": False,
                "rule_corr": False,
            })
            entry["rule_corr"] = True
            if not entry.get("source"):
                entry["source"] = source

    results: List[dict] = []
    for derived, info in hits.items():
        source = info["source"]
        d_series = df[derived]
        s_series = df[source]
        n_unique = _unique_count(d_series)
        is_binary = n_unique == 2 and _is_wide_range_continuous(s_series)
        confidence = "high" if info["rule_name"] and info["rule_corr"] else "medium"

        if is_binary:
            action = "exclude"
            recommended_role = None
            kind = "binary"
        else:
            action = "move_to_grouping"
            recommended_role = "grouping"
            kind = "categorical"

        results.append({
            "name": derived,
            "source": source,
            "confidence": confidence,
            "kind": kind,
            "action": action,
            "recommended_role": recommended_role,
            "unique_n": n_unique,
            "spearman_r": round(_spearman_abs(s_series, d_series) or 0, 3),
        })

    return sorted(results, key=lambda x: x["name"])


def _numeric_stats(series: pd.Series) -> dict:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) == 0:
        return {"n_valid": 0}
    return {
        "n_valid": int(len(clean)),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "mean": round(float(clean.mean()), 4),
        "unique": int(clean.nunique()),
    }


def profile_from_samples(
    columns: List[str],
    samples: Dict[str, List[Any]],
    labels: Optional[Dict[str, str]] = None,
    variable_measure: Optional[Dict[str, str]] = None,
    n_rows: Optional[int] = None,
) -> dict:
    """Sınıflandırma / ölçek tespiti için sütun düzeyi profil."""
    labels = labels or {}
    variable_measure = variable_measure or {}
    cols: List[dict] = []
    for col in columns:
        vals = samples.get(col, []) or []
        series = pd.Series(vals)
        numeric = _numeric_stats(series)
        uniq = list(dict.fromkeys(str(v) for v in vals if v is not None and str(v) != ""))[:12]
        entry: dict = {
            "name": col,
            "label": labels.get(col, col),
            "spss_measure": variable_measure.get(col),
            "sample_values": uniq,
            "sample_n": len(vals),
        }
        if numeric.get("n_valid", 0) > 0:
            entry["numeric"] = numeric
        cols.append(entry)

    scale_groups = detect_scale_groups(columns)
    return {
        "n_rows_hint": n_rows,
        "n_columns": len(columns),
        "columns": cols,
        "scale_prefix_groups": {
            k: v for k, v in scale_groups.items() if len(v) >= 2
        },
    }


def profile_from_dataframe(
    df: pd.DataFrame,
    variables: List[Variable],
) -> dict:
    """Test planı için zengin profil."""
    active = [v for v in variables if v.included and v.name in df.columns]
    cols: List[dict] = []
    for v in active:
        series = df[v.name]
        missing = int(series.isna().sum())
        entry: dict = {
            "name": v.name,
            "label": v.label or v.name,
            "type": v.type,
            "role": v.role,
            "missing_n": missing,
            "missing_pct": round(100 * missing / max(len(df), 1), 1),
        }
        if v.type == "categorical":
            vc = series.dropna().astype(str).value_counts()
            entry["categories"] = int(vc.shape[0])
            entry["top_categories"] = [
                {"value": str(k), "n": int(n)}
                for k, n in vc.head(8).items()
            ]
            if len(vc):
                entry["largest_group_pct"] = round(
                    100 * float(vc.max()) / float(vc.sum()), 1
                )
        else:
            entry["numeric"] = _numeric_stats(series)
        cols.append(entry)

    grouping = [c["name"] for c in cols if c.get("role") == "grouping"]
    outcomes = [c["name"] for c in cols if c.get("role") == "outcome"]
    return {
        "n_rows": int(len(df)),
        "n_columns": len(cols),
        "grouping_vars": grouping,
        "outcome_vars": outcomes,
        "columns": cols,
        "scale_prefix_groups": detect_scale_groups(list(df.columns)),
    }


def profile_json(profile: dict, max_chars: int = 12000) -> str:
    text = json.dumps(profile, ensure_ascii=False, indent=2)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n... (kısaltıldı)"


def build_spearman_summary(
    df: pd.DataFrame,
    column_names: List[str],
    min_r: float = 0.50,
    max_pairs: int = 50,
) -> List[dict]:
    """Kompakt Spearman özeti — yüksek korelasyonlu çiftler (ham veri Gemini'ye gitmez)."""
    numeric_cols = []
    for col in column_names:
        if col not in df.columns:
            continue
        s = _numeric_series(df[col]).dropna()
        if len(s) >= 10 and s.nunique() >= 3:
            numeric_cols.append(col)
    if len(numeric_cols) < 2:
        return []

    pairs: List[dict] = []
    for i, left in enumerate(numeric_cols):
        for right in numeric_cols[i + 1:]:
            sub = pd.DataFrame({
                "a": _numeric_series(df[left]),
                "b": _numeric_series(df[right]),
            }).dropna()
            if len(sub) < 10:
                continue
            try:
                r, _ = stats.spearmanr(sub["a"], sub["b"], nan_policy="omit")
            except Exception:
                continue
            if r is None or pd.isna(r):
                continue
            abs_r = abs(float(r))
            if abs_r >= min_r:
                pairs.append({
                    "a": left,
                    "b": right,
                    "r": round(float(r), 3),
                    "abs_r": round(abs_r, 3),
                })

    pairs.sort(key=lambda p: p["abs_r"], reverse=True)
    return pairs[:max_pairs]
