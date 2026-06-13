"""Sayısal sütunlarda tekrar eden kayıp veri kodlarını sezgisel tespit."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

import pandas as pd

_SENTINEL_CODES_ALWAYS = {99, 998, 999, 9999, -9, -99}
_SENTINEL_CODES_CONDITIONAL = {9}


def infer_missing_codes_from_dataframe(
    df: pd.DataFrame,
) -> Tuple[Dict[str, List[str]], Optional[str]]:
    """
    Her sayısal sütunda tekrar eden sentinel / aralık dışı değerleri bul.
    Döndürür: (sütun → kod listesi, en sık global kod).
    """
    per_col: Dict[str, List[str]] = {}
    global_counter: Counter = Counter()

    for col in df.columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        valid = numeric.dropna()
        if len(valid) < 10 or valid.nunique() < 3:
            continue

        core = valid.copy()
        for sentinel in _SENTINEL_CODES_ALWAYS | _SENTINEL_CODES_CONDITIONAL:
            core = core[core != sentinel]
        if len(core) < 10:
            core = valid

        low, high = core.quantile(0.05), core.quantile(0.95)
        plausible = core[(core >= low) & (core <= high)]
        if plausible.empty:
            plausible = valid
        plausible_max = float(plausible.max())
        plausible_min = float(plausible.min())

        codes: List[str] = []
        for val, cnt in valid.value_counts().items():
            if cnt < 2:
                continue
            fval = float(val)
            iv: Optional[int] = int(fval) if fval.is_integer() else None

            is_always_sentinel = iv in _SENTINEL_CODES_ALWAYS if iv is not None else False

            is_conditional_sentinel = False
            if iv in _SENTINEL_CODES_CONDITIONAL and iv is not None:
                is_conditional_sentinel = fval > plausible_max * 1.5 or fval < plausible_min * 0.5

            above_range = (
                fval > plausible_max
                and fval >= plausible_max * 2
                and fval >= plausible_max + 10
            )

            if is_always_sentinel or is_conditional_sentinel or above_range:
                code_str = str(iv) if iv is not None else str(val)
                codes.append(code_str)
                global_counter[code_str] += 1

        if codes:
            per_col[str(col)] = sorted(set(codes), key=lambda x: (len(x), x))

    global_code = global_counter.most_common(1)[0][0] if global_counter else None
    return per_col, global_code
