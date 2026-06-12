"""Sayısal sütunlarda tekrar eden kayıp veri kodlarını sezgisel tespit."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

import pandas as pd

_SENTINEL_CODES = {9, 99, 998, 999, 9999, -9, -99}


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

        low, high = valid.quantile(0.05), valid.quantile(0.95)
        plausible = valid[(valid >= low) & (valid <= high)]
        if plausible.empty:
            plausible = valid
        plausible_max = float(plausible.max())

        codes: List[str] = []
        for val, cnt in valid.value_counts().items():
            if cnt < 2:
                continue
            fval = float(val)
            iv: Optional[int] = int(fval) if fval.is_integer() else None
            is_sentinel = iv in _SENTINEL_CODES if iv is not None else False
            above_range = fval > plausible_max and fval >= max(plausible_max * 1.2, plausible_max + 3)
            if is_sentinel or above_range:
                code_str = str(iv) if iv is not None else str(val)
                codes.append(code_str)
                global_counter[code_str] += 1

        if codes:
            per_col[str(col)] = sorted(set(codes), key=lambda x: (len(x), x))

    global_code = global_counter.most_common(1)[0][0] if global_counter else None
    return per_col, global_code
