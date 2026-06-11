"""Deterministik veri profili — Gemini zenginleştirmesi ve Claude kararı için girdi."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pandas as pd

from data_cleaning import detect_scale_groups
from schemas import Variable


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
