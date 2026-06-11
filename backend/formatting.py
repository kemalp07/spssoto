"""APA sayı formatlama ve tablo yardımcıları."""
import re
import math
from typing import List, Tuple, Optional, Dict
import numpy as np
import pandas as pd
from constants import ANTHROPOMETRIC_META, LABEL_COL_RE, P_VALUE_COL_RE
from schemas import Variable

class TableCounter:
    def __init__(self):
        self.n = 0

    def next(self, title_suffix: str) -> Tuple[int, str]:
        self.n += 1
        return self.n, f"Tablo {self.n}. {title_suffix}"

def fmt_num(x: float, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{float(x):.{decimals}f}"

def fmt_p(p: float) -> str:
    if p is None:
        return "—"
    p = float(p)
    if p < 0.001:
        return "< .001"
    return f"{p:.3f}".lstrip("0")

def p_stars(p: float) -> str:
    if p is None:
        return ""
    p = float(p)
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""

def fmt_p_display(p: float) -> str:
    return f"{fmt_p(p)}{p_stars(p)}"

def fmt_r(x: float, decimals: int = 3) -> str:
    """Korelasyon / η² — baştaki sıfır olmadan (.137)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    s = f"{abs(float(x)):.{decimals}f}"
    if s.startswith("0."):
        s = s[1:]
    sign = "−" if float(x) < 0 else ""
    return f"{sign}{s}"

def academic_short_label(v: Variable) -> str:
    return format_display_label(v.name, v.label)

def academic_group_target(v: Variable) -> str:
    label = format_display_label(v.name, v.label)
    return f"{label} Gruplarına"

def build_group_comparison_title(cv: Variable, sv: Variable, test_name: str) -> str:
    group_part = academic_group_target(cv)
    sv_label = academic_short_label(sv)
    return (
        f"Katılımcıların {sv_label} Değerlerinin "
        f"{group_part} Göre Karşılaştırılması ({test_name})"
    )

def build_measure_analysis_title(sv: Variable, suffix: str) -> str:
    return f"Katılımcıların {academic_short_label(sv)} Değerlerinin {suffix}"

def apply_academic_text_rules(text: str) -> str:
    if not text:
        return text
    result = _strip_apa_html(str(text))
    replacements = [
        (re.compile(r"\bBMI\b", re.I), "BKİ"),
        (re.compile(r"\bVKİ\b"), "BKİ"),
        (re.compile(r"\bVKI\b", re.I), "BKİ"),
    ]
    for pattern, repl in replacements:
        result = pattern.sub(repl, result)
    return result

def format_display_label(name: str, label: str) -> str:
    if label and label.strip() and label.strip().upper() != name.strip().upper():
        return label.strip()
    cleaned = name.replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else name

def build_resolved_label_map(custom: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    if custom:
        for code, label in custom.items():
            if label and label.strip():
                resolved[code.upper()] = label.strip()
    return resolved

def substitute_variable_codes(text: str, label_map: Dict[str, str]) -> str:
    if not text or not label_map:
        return str(text) if text else ""
    result = _strip_apa_html(str(text))
    for code in sorted(label_map.keys(), key=len, reverse=True):
        result = re.sub(re.escape(code), label_map[code], result, flags=re.I)
    return result

def apa_italicize_stats(text: str) -> str:
    """İstatistiksel sembolleri APA 7 için italik (HTML em) yap."""
    if not text or "<em>" in str(text):
        return str(text) if text is not None else ""
    result = str(text)
    shields: List[str] = []

    def _shield(m: re.Match) -> str:
        shields.append(m.group())
        return f"\x00S{len(shields) - 1}\x00"

    for phrase in ("Kayıp Veri", "Belirtilmeyen"):
        result = re.sub(re.escape(phrase), _shield, result)
    patterns = [
        (r"χ²", "<em>χ²</em>"),
        (r"η²", "<em>η²</em>"),
        (r"ρ", "<em>ρ</em>"),
        (r"n \(%\)", "<em>n</em> (%)"),
        (r"Cohen's d", "Cohen's <em>d</em>"),
        (r"\bdf\b", "<em>df</em>"),
        (r"\bF\b", "<em>F</em>"),
        (r"\bt\b", "<em>t</em>"),
        (r"\bU\b", "<em>U</em>"),
        (r"\bH\b", "<em>H</em>"),
        (r"\bR²\b", "<em>R²</em>"),
        (r"\bR\b", "<em>R</em>"),
        (r"\br\b", "<em>r</em>"),
        (r"\bz\b", "<em>z</em>"),
        (r"\bN\b", "<em>N</em>"),
        (r"(?<![a-zA-Z])n(?![a-zA-Z])", "<em>n</em>"),
        (r"(?<![a-zA-Z])p(?![a-zA-Z])", "<em>p</em>"),
    ]
    for pattern, repl in patterns:
        result = re.sub(pattern, repl, result)
    result = re.sub(r"<em><em>", "<em>", result)
    result = re.sub(r"</em></em>", "</em>", result)
    for i, phrase in enumerate(shields):
        result = result.replace(f"\x00S{i}\x00", phrase)
    return result

def make_result(
    rtype: str, table_no: int, title: str, headers: list, rows: list, note: str, **extra
) -> dict:
    fmt_headers = [apa_italicize_stats(h) for h in headers]
    fmt_rows = [[apa_italicize_stats(c) for c in row] for row in rows]
    fmt_note = apa_italicize_stats(note) if note else note
    fmt_title = apa_italicize_stats(title)
    return {
        "type": rtype,
        "table_number": table_no,
        "title": fmt_title,
        "headers": fmt_headers,
        "rows": fmt_rows,
        "note": fmt_note,
        **extra,
    }

def _is_label_column(col_name: str, idx: int) -> bool:
    if idx == 0:
        return True
    return bool(LABEL_COL_RE.search(str(col_name)))

def _normalize_spss_header(h: str) -> str:
    h = str(h).strip()
    h = h.replace("x̄", "M").replace("X̄", "M")
    h = re.sub(r"\bSS\b", "SD", h)
    if h.startswith("col_"):
        return h
    return format_display_label(h, h)

def _apa_format_spss_cell(val, col_name: str) -> str:
    if _is_blank(val):
        return ""
    s = str(val).strip()
    col_l = _strip_apa_html(str(col_name)).lower()

    inner = s
    eq = re.search(r"=\s*(.+)$", s)
    if eq:
        inner = eq.group(1).strip()

    if P_VALUE_COL_RE.search(col_l) or re.match(r"^p\s*=", s, re.I):
        try:
            p_str = inner.replace(",", ".").lstrip("<").strip()
            if p_str.startswith("."):
                p_str = "0" + p_str
            return fmt_p_display(float(p_str))
        except ValueError:
            pass

    num_candidate = inner.replace(",", ".")
    if re.match(r"^-?0\.\d+$", num_candidate):
        sign = "−" if num_candidate.startswith("-") else ""
        return f"{sign}{num_candidate.lstrip('-')[1:]}"
    if re.match(r"^0\.\d+$", num_candidate):
        return num_candidate[1:]

    return s

def _infer_spss_title_suffix(df: pd.DataFrame, index: int) -> str:
    if len(df.columns):
        lead = _normalize_spss_header(df.columns[0])
        if lead and not lead.startswith("col_"):
            return f"{lead} Analiz Sonuçları"
    return f"SPSS Analiz Tablosu {index + 1}"

def _build_spss_note(df: pd.DataFrame) -> str:
    parts = ["Not. * p < .05"]
    cols = " ".join(str(c) for c in df.columns).lower()
    if "η" in cols or "eta" in cols or "r²" in cols or "r2" in cols:
        parts.append("** p < .01")
    return "; ".join(parts) + "."

def _dataframe_to_apa_result(tc: TableCounter, df: pd.DataFrame, title_suffix: str) -> dict:
    headers = [_normalize_spss_header(c) for c in df.columns]
    rows = []
    for _, row in df.iterrows():
        cells = []
        for j, col in enumerate(df.columns):
            val = row[col]
            if _is_label_column(col, j):
                cells.append(format_category_value(val))
            else:
                cells.append(_apa_format_spss_cell(val, col))
        rows.append(cells)
    no, title = tc.next(title_suffix)
    return make_result(
        "spss_import", no, title, headers, rows, _build_spss_note(df),
    )

def _join_labels_tr(labels: List[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} ve {labels[1]}"
    return ", ".join(labels[:-1]) + f" ve {labels[-1]}"


def _normality_basis_phrase(assessed: List[Variable], norm_map: Dict[str, dict]) -> str:
    test_names: List[str] = []
    uses_skew_kurt = False
    for v in assessed:
        nm = norm_map.get(v.name, {})
        n = nm.get("n", 0)
        if n > 200:
            uses_skew_kurt = True
        else:
            test = nm.get("test")
            if test and test not in ("insufficient_data",):
                if test not in test_names:
                    test_names.append(test)

    parts: List[str] = []
    if test_names:
        if len(test_names) == 1:
            parts.append(f"{test_names[0]} testi")
        else:
            parts.append(
                ", ".join(test_names[:-1]) + f" ve {test_names[-1]} testleri"
            )
    if uses_skew_kurt:
        parts.append(
            "çarpıklık ve basıklık değerlerinin ±2,0 sınırları içinde kalması ölçütü"
        )
    if not parts:
        return "dağılım özellikleri"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} ile {parts[1]}"


def build_intro(
    n_total: int,
    norm_map: Dict[str, dict],
    outcome_cont: List[Variable],
) -> str:
    base = (
        f"Araştırmanın örneklemini toplam {n_total} katılımcı (N = {n_total}) "
        f"oluşturmaktadır. "
    )

    assessed = [
        v for v in outcome_cont
        if v.name in norm_map and norm_map[v.name].get("n", 0) >= 3
    ]
    if not assessed:
        return (
            base
            + "Analizler öncesinde sonuç değişkenlerinin dağılım özellikleri "
            "incelenmiştir. Bu doğrultuda araştırmanın amaçları kapsamında "
            "uygun istatistiksel testler uygulanmıştır."
        )

    basis = _normality_basis_phrase(assessed, norm_map)
    intro_mid = (
        f"Analizler öncesinde sonuç değişkenlerinin dağılım özellikleri incelenmiş; "
        f"normallik değerlendirmesinde {basis} kullanılmıştır. "
    )

    normal_labels = [
        v.label for v in assessed
        if norm_map[v.name].get("is_parametric", norm_map[v.name].get("normal", True))
    ]
    non_normal_labels = [
        v.label for v in assessed
        if not norm_map[v.name].get("is_parametric", norm_map[v.name].get("normal", True))
    ]

    if normal_labels and not non_normal_labels:
        return (
            base + intro_mid
            + "Tüm sonuç değişkenlerinin normal dağılım gösterdiği saptanmıştır. "
            "Bu doğrultuda, araştırmanın amaçları kapsamında parametrik test "
            "yöntemlerinin uygulanmasına karar verilmiştir."
        )

    if non_normal_labels and not normal_labels:
        labels_str = _join_labels_tr(non_normal_labels)
        return (
            base + intro_mid
            + f"{labels_str} değişkenlerinin normal dağılım göstermediği saptanmıştır. "
            "Bu doğrultuda non-parametrik test yöntemleri uygulanmıştır."
        )

    normal_str = _join_labels_tr(normal_labels)
    non_str = _join_labels_tr(non_normal_labels)
    return (
        base + intro_mid
        + f"{normal_str} değişkenlerinin normal dağılım gösterdiği; "
        f"{non_str} değişkenlerinin normal dağılım göstermediği saptanmıştır. "
        "İlgili değişkenlere uygun parametrik ve non-parametrik testler uygulanmıştır."
    )

