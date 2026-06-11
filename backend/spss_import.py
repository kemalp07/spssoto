"""SPSS tablo içe aktarma."""
import io
import re
from typing import List, Tuple, Dict
import numpy as np
import pandas as pd
from formatting import TableCounter, make_result, fmt_p_display, fmt_num, apa_italicize_stats
from constants import STAT_COL_RE, LABEL_COL_RE, P_VALUE_COL_RE

def _flatten_columns(columns) -> List[str]:
    if isinstance(columns, pd.MultiIndex):
        out = []
        for i, col in enumerate(columns):
            parts = [str(p).strip() for p in col if str(p).strip() not in ("", "nan", "None")]
            out.append(" ".join(parts) if parts else f"col_{i}")
        return out
    return [str(c).strip() if str(c).strip() else f"col_{i}" for i, c in enumerate(columns)]

def _is_blank(val) -> bool:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return True
    s = str(val).strip()
    return s in ("", "nan", "None", "NaN", ",")

def _clean_stat_value(val) -> str:
    if _is_blank(val):
        return ""
    s = str(val).strip()
    m = re.search(r"=\s*(.+)$", s)
    return m.group(1).strip() if m else s

def _is_stat_column(col_name: str) -> bool:
    return bool(STAT_COL_RE.search(str(col_name)))

def _clean_spss_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = _flatten_columns(df.columns)

    # Yinelenen sütun başlıklarını benzersizleştir
    seen: Dict[str, int] = {}
    new_cols = []
    for col in df.columns:
        base = str(col)
        if base not in seen:
            seen[base] = 0
            new_cols.append(base)
        else:
            seen[base] += 1
            new_cols.append(f"{base}_{seen[base]}")
    df.columns = new_cols

    # Hayalet / tamamen boş sütunları kaldır
    keep = []
    for col in df.columns:
        if any(not _is_blank(v) for v in df[col]):
            keep.append(col)
    if keep:
        df = df[keep]

    # Birleştirilmiş hücreleri dağıt (forward fill)
    df = df.ffill(axis=0)

    # Test istatistikleri (χ², p, F) — genelde Toplam satırında; tüm satırlara yay
    for col in df.columns:
        if _is_stat_column(col):
            series = df[col].apply(_clean_stat_value)
            series = series.replace("", np.nan)
            df[col] = series.ffill().bfill()

    # Boş kategori adları → Kayıp Veri (ilk sütun + etiket sütunları)
    label_col_re = re.compile(r"grup|kategori|ölçek|değişken|\(i\)|\(j\)", re.I)
    label_cols = [df.columns[0]] if len(df.columns) else []
    for ci, col in enumerate(df.columns):
        if ci > 0 and label_col_re.search(str(col)):
            label_cols.append(col)
    for col in label_cols:
        for idx in df.index:
            if _is_blank(df.at[idx, col]):
                rest = [v for c, v in zip(df.columns, df.loc[idx]) if c != col]
                if any(not _is_blank(v) for v in rest):
                    df.at[idx, col] = "Kayıp Veri"

    # Post-hoc (I)/(J) grupları — (I) birleştirilmişse forward fill
    for col in df.columns:
        cl = str(col).lower()
        if "(i)" in cl or cl.startswith("i grup") or cl == "i":
            df[col] = df[col].ffill()

    # Tamamen boş satırları kaldır
    mask = df.apply(lambda row: all(_is_blank(v) for v in row), axis=1)
    df = df[~mask].reset_index(drop=True)

    return df

def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    cols = [apa_italicize_stats(str(c)) for c in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join([":---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        cells = []
        for j, v in enumerate(row):
            if _is_blank(v):
                cells.append(format_category_value(v) if j == 0 else "")
            elif j == 0:
                cells.append(format_category_value(v))
            else:
                cells.append(str(v).strip())
        if len(cells) != len(cols):
            continue
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

def _parse_spss_input(content: str) -> List[pd.DataFrame]:
    content = content.strip()
    if not content:
        raise ValueError("Boş içerik")
    if "<table" in content.lower():
        dfs = pd.read_html(io.StringIO(content))
    else:
        sep = "\t" if content.count("\t") > content.count(",") else ","
        try:
            dfs = [pd.read_csv(io.StringIO(content), sep=sep, engine="python", on_bad_lines="skip")]
        except Exception:
            dfs = pd.read_html(io.StringIO(content))
    return [df for df in dfs if df is not None and not df.empty]

def convert_spss_table(content: str) -> str:
    parts = []
    for df in _parse_spss_input(content):
        cleaned = _clean_spss_dataframe(df)
        if not cleaned.empty:
            parts.append(_dataframe_to_markdown(cleaned))
    if not parts:
        raise ValueError("Tablo ayrıştırılamadı")
    return "\n\n".join(parts)

def _markdown_tables_to_apa_results(markdown: str) -> List[dict]:
    tc = TableCounter()
    results = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        lines = [ln.strip() for ln in block.splitlines() if "|" in ln]
        if len(lines) < 2:
            continue
        headers = [c.strip() for c in lines[0].strip("|").split("|")]
        data_lines = [ln for ln in lines[2:] if not re.match(r"^\|[\s\-:|]+\|$", ln)]
        rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in data_lines]
        if not headers or not rows:
            continue
        no, title = tc.next("SPSS Analiz Tablosu")
        results.append(make_result(
            "spss_import", no, title, headers, rows,
            "Not. * p < .05.",
        ))
    return results

def convert_spss_to_apa_results(content: str) -> Tuple[List[dict], dict]:
    """Ham SPSS yapıştırmasını hayalet temizliği + APA 7 tablo nesnelerine dönüştür."""
    results = []
    tc = TableCounter()
    for i, df in enumerate(_parse_spss_input(content)):
        cleaned = _clean_spss_dataframe(df)
        if cleaned.empty:
            continue
        suffix = _infer_spss_title_suffix(cleaned, i)
        results.append(_dataframe_to_apa_result(tc, cleaned, suffix))
    if not results:
        raise ValueError("Tablo ayrıştırılamadı")
    return results, {"source": "spss", "intro": "", "table_count": len(results)}

