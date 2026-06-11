"""Analiz sonuçları için akademik tablo düzeni — tüm veri setlerinde deterministik."""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

from formatting import TableCounter, fmt_p_display, fmt_r, make_result
from layout_config import DEFAULT_LAYOUT_CONFIG, LayoutConfig

_CRONBACH_HEADERS = [
    "Ölçek",
    "Madde Sayısı",
    "Geçerli n",
    "Cronbach α",
    "Değerlendirme",
]
_CRONBACH_NOTE = (
    "Not. α = Cronbach alfa iç tutarlılık katsayısı. Kabul edilebilir sınır: α ≥ .70."
)
_DEMOGRAPHICS_TITLE = "Katılımcıların Sosyodemografik Özelliklerine Göre Dağılımı"
_DEMOGRAPHICS_HEADERS = ["Özellik", "f", "%"]
_DEMOGRAPHICS_NOTE = (
    "Not. Değerler frekans (f) ve yüzde (%) olarak verilmiştir. "
    "Kategori yüzdeleri ilgili değişkenin geçerli örneklem sayısı üzerinden hesaplanmıştır."
)

_ITEM_PREFIX_RE = re.compile(r"^(.+?)_\d+(?:_ters|_t)?$", re.I)
_TITLE_NUM_RE = re.compile(r"^Tablo\s+\d+\.\s*(.+)$", re.I | re.DOTALL)
_DECIMAL_TOKEN_RE = re.compile(
    r"(?<![\d,.])(-?\d*\.\d+)(?![\d,.])|(?<![\d,.])(\.\d+)(?![\d,.])",
)

_TYPE_SORT_ORDER: Dict[str, int] = {
    "demographics": 10,
    "descriptive": 20,
    "normality": 25,
    "cronbach": 30,
    "frequency": 35,
    "correlation_matrix": 40,
    "correlation": 40,
    "chi_square": 50,
    "fisher_exact": 50,
    "ttest": 60,
    "mann_whitney": 60,
    "paired_ttest": 60,
    "paired_wilcoxon": 60,
    "anova": 70,
    "kruskal_wallis": 70,
    "tukey": 80,
    "dunn": 80,
    "regression": 90,
    "multiple_regression": 90,
    "spss_import": 100,
}


def scale_label_from_items(items: List[str]) -> str:
    if not items:
        return "Ölçek"
    for item in items:
        m = _ITEM_PREFIX_RE.match(str(item))
        if m:
            return m.group(1).replace("_", " ").strip()
    return str(items[0])


def _title_suffix(title: str) -> str:
    if not title:
        return "Analiz Tablosu"
    m = _TITLE_NUM_RE.match(str(title).strip())
    return m.group(1).strip() if m else str(title).strip()


def _strip_html(text: str) -> str:
    return re.sub(r"</?em>", "", str(text))


def _type_sort_key(result: dict, index: int) -> Tuple[int, int]:
    rtype = result.get("type") or ""
    if rtype == "frequency" and result.get("is_demographic"):
        order = _TYPE_SORT_ORDER["demographics"]
    else:
        order = _TYPE_SORT_ORDER.get(rtype, 200)
    return (order, index)


def _parse_cronbach_row(result: dict) -> Optional[Dict[str, Any]]:
    headers = [_strip_html(h) for h in (result.get("headers") or [])]
    rows = result.get("rows") or []
    if not rows:
        return None
    row = rows[0]
    if len(row) < 4:
        return None

    scale_name = result.get("scale_label") or result.get("scale_name")
    k: Any
    n: Any
    alpha: Any
    interp: Any

    if headers and headers[0] == "Ölçek":
        scale_name = scale_name or row[0]
        k, n, alpha, interp = row[1], row[2], row[3], row[4] if len(row) > 4 else ""
    else:
        scale_name = scale_name or scale_label_from_items(result.get("items") or [])
        k, n, alpha, interp = row[0], row[1], row[2], row[3] if len(row) > 3 else ""

    if scale_name is None:
        scale_name = "Ölçek"

    alpha_raw = result.get("alpha")
    if alpha_raw is None:
        try:
            alpha_raw = float(_strip_html(str(alpha)).replace(",", "."))
        except (TypeError, ValueError):
            alpha_raw = None

    n_items = result.get("n_items")
    if n_items is None:
        try:
            n_items = int(_strip_html(str(k)))
        except (TypeError, ValueError):
            n_items = k

    return {
        "name": str(scale_name),
        "n_items": n_items,
        "n": n,
        "alpha": alpha_raw,
        "alpha_display": str(alpha),
        "interpretation": str(
            result.get("interpretation") or interp or "",
        ).strip(),
        "items": list(result.get("items") or []),
    }


def _dedupe_scales(scales: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for s in scales:
        key = re.sub(r"\s+", " ", s["name"].strip().lower())
        if key not in seen:
            seen[key] = s
    return list(seen.values())


def merge_cronbach_results(cronbach_tables: List[dict]) -> Optional[dict]:
    if not cronbach_tables:
        return None

    parsed = [p for p in (_parse_cronbach_row(r) for r in cronbach_tables) if p]
    if not parsed:
        return None

    if len(parsed) == 1 and len(cronbach_tables) == 1:
        single = dict(cronbach_tables[0])
        scale = parsed[0]
        single.setdefault("scale_label", scale["name"])
        single["merged_scales"] = [scale]
        if _strip_html(str((single.get("headers") or [""])[0])) != "Ölçek":
            single["headers"] = _CRONBACH_HEADERS
            single["rows"] = [[
                scale["name"],
                scale["n_items"],
                scale["n"],
                scale["alpha_display"],
                scale["interpretation"],
            ]]
        return single

    scales = _dedupe_scales(parsed)
    rows = [
        [s["name"], s["n_items"], s["n"], s["alpha_display"], s["interpretation"]]
        for s in scales
    ]
    first_no = cronbach_tables[0].get("table_number")
    return make_result(
        "cronbach",
        int(first_no) if first_no else 1,
        "Ölçeklerin Güvenilirlik Analizi (Cronbach α)",
        _CRONBACH_HEADERS,
        rows,
        _CRONBACH_NOTE,
        merged_scales=scales,
        combined=True,
    )


def _is_demographic_frequency(result: dict) -> bool:
    if result.get("type") != "frequency":
        return False
    if result.get("is_demographic") is True:
        return True
    if result.get("frequency_role") == "grouping":
        return True
    return False


def _parse_frequency_rows(result: dict) -> Tuple[str, List[List[str]]]:
    variable = str(result.get("variable") or "")
    rows: List[List[str]] = []
    for row in result.get("rows") or []:
        if len(row) < 4:
            continue
        cat = _strip_html(str(row[1])).strip()
        if cat.lower() in ("toplam", "total"):
            continue
        rows.append([cat, str(row[2]), str(row[3])])
    if not variable and result.get("rows"):
        variable = _strip_html(str(result["rows"][0][0]))
    return variable, rows


def merge_demographic_frequencies(freq_tables: List[dict]) -> Optional[dict]:
    if not freq_tables:
        return None

    merged_rows: List[List[str]] = []
    source_vars: List[str] = []
    total_n = 0

    for table in freq_tables:
        var_label, cat_rows = _parse_frequency_rows(table)
        if not cat_rows:
            continue
        source_vars.append(var_label)
        merged_rows.append([var_label, "", ""])
        for cat, n_val, pct in cat_rows:
            if cat == "Kayıp Veri":
                merged_rows.append([f"  {cat}", n_val, pct])
                continue
            merged_rows.append([f"  {cat}", n_val, pct])
            try:
                total_n = max(total_n, int(n_val))
            except (TypeError, ValueError):
                pass

    if not merged_rows:
        return None

    first_no = freq_tables[0].get("table_number")
    note = _DEMOGRAPHICS_NOTE
    if total_n:
        note += f" Geçerli örneklem: N = {total_n}."

    return make_result(
        "demographics",
        int(first_no) if first_no else 1,
        _DEMOGRAPHICS_TITLE,
        _DEMOGRAPHICS_HEADERS,
        merged_rows,
        note,
        combined=True,
        source_variables=source_vars,
        is_demographic=True,
    )


def correlation_lower_triangle(result: dict) -> dict:
    if result.get("type") not in ("correlation_matrix", "correlation"):
        return result
    if result.get("lower_triangle"):
        return result

    headers = list(result.get("headers") or [])
    if len(headers) < 3:
        return result

    # ["Değişken", "1", "2", ..., "n"]
    n_cols = len(headers) - 2  # exclude "Değişken" and trailing "n"
    if n_cols < 1:
        return result

    out = copy.deepcopy(result)
    new_rows: List[List[str]] = []
    for i, row in enumerate(result.get("rows") or []):
        if len(row) < len(headers):
            continue
        label = row[0]
        values = row[1 : 1 + n_cols]
        trailing = row[1 + n_cols :]
        formatted: List[str] = []
        for j, cell in enumerate(values):
            if j > i:
                formatted.append("")
            elif j == i:
                formatted.append("—")
            else:
                formatted.append(cell)
        new_rows.append([label] + formatted + trailing)

    out["rows"] = new_rows
    out["lower_triangle"] = True
    note = out.get("note") or ""
    if "alt üçgen" not in note.lower():
        out["note"] = (
            note.rstrip(".")
            + ". Korelasyon matrisi yalnızca alt üçgende gösterilmiştir."
        )
    return out


def sort_tables_by_priority(results: List[dict]) -> List[dict]:
    indexed = list(enumerate(results))
    indexed.sort(key=lambda pair: _type_sort_key(pair[1], pair[0]))
    return [item for _, item in indexed]


def _format_decimal_token(token: str, config: LayoutConfig) -> str:
    is_neg = str(token).startswith("-")
    num_str = str(token).lstrip("-")
    num = float("0" + num_str) if num_str.startswith(".") else float(token)
    decimals = len(num_str.split(".")[1]) if "." in num_str else 0
    abs_val = abs(num)
    formatted = f"{abs_val:.{decimals}f}"
    if config.leading_zero:
        if abs_val < 1 and not formatted.startswith("0"):
            formatted = "0" + formatted
    elif abs_val < 1 and formatted.startswith("0."):
        formatted = formatted[1:]
    if config.decimal_separator != ".":
        formatted = formatted.replace(".", config.decimal_separator)
    if is_neg and num != 0:
        formatted = "-" + formatted.lstrip("-")
    return formatted


def _apply_locale_to_text(text: str, config: LayoutConfig) -> str:
    if not text or config.locale != "tr":
        return text

    def _repl(match: re.Match) -> str:
        token = match.group(1) or match.group(2)
        if not token:
            return match.group(0)
        return _format_decimal_token(token, config)

    return _DECIMAL_TOKEN_RE.sub(_repl, str(text))


def apply_locale_to_result(result: dict, config: LayoutConfig) -> dict:
    if config.locale != "tr":
        return result
    out = copy.deepcopy(result)
    out["title"] = _apply_locale_to_text(out.get("title", ""), config)
    out["note"] = _apply_locale_to_text(out.get("note", ""), config)
    out["headers"] = [_apply_locale_to_text(h, config) for h in (out.get("headers") or [])]
    out["rows"] = [
        [_apply_locale_to_text(str(cell), config) for cell in row]
        for row in (out.get("rows") or [])
    ]
    return out


def renumber_tables(results: List[dict], config: LayoutConfig) -> List[dict]:
    out: List[dict] = []
    for i, r in enumerate(results, start=1):
        item = dict(r)
        suffix = _title_suffix(item.get("title", ""))
        item["table_number"] = i
        if config.title_style == "tr_classic":
            item["title"] = f"Tablo {i}. {suffix}"
        else:
            item["title"] = f"Table {i}\n{suffix}"
        out.append(item)
    return out


def _grouping_merge_key(result: dict) -> Tuple[str, str]:
    rtype = str(result.get("type") or "")
    grouping = (
        result.get("grouping_name")
        or result.get("grouping_label")
        or ""
    )
    return rtype, str(grouping).strip().lower()


def _parse_ttest_rows(result: dict) -> Optional[Dict[str, Any]]:
    rows = result.get("rows") or []
    if len(rows) < 2:
        return None
    groups = []
    for row in rows[:2]:
        if len(row) < 4:
            return None
        groups.append({
            "label": _strip_html(str(row[1])),
            "n": row[2],
            "desc": _strip_html(str(row[3])),
        })
    stats_row = rows[0]
    return {
        "outcome_label": result.get("outcome_label") or _strip_html(str(stats_row[0])),
        "groups": groups,
        "t": stats_row[4] if len(stats_row) > 4 else "",
        "df": stats_row[5] if len(stats_row) > 5 else "",
        "p": stats_row[6] if len(stats_row) > 6 else "",
        "d": stats_row[7] if len(stats_row) > 7 else "",
        "meta": {
            "t": result.get("t"),
            "p": result.get("p"),
            "cohens_d": result.get("cohens_d"),
            "df": result.get("df"),
            "significant": result.get("significant"),
            "groups": result.get("groups"),
        },
    }


def merge_ttest_tables(tables: List[dict]) -> Optional[dict]:
    parsed = [_parse_ttest_rows(t) for t in tables]
    parsed = [p for p in parsed if p]
    if len(parsed) < 2:
        return None

    grouping = tables[0].get("grouping_label") or "Gruplandırıcı"
    g1_name = parsed[0]["groups"][0]["label"]
    g2_name = parsed[0]["groups"][1]["label"]
    headers = [
        "Bağımlı Değişken",
        f"{g1_name} (n, M±SS)",
        f"{g2_name} (n, M±SS)",
        "t",
        "df",
        "p",
        "Cohen's d",
    ]
    merged_rows = []
    summaries = []
    for item, src in zip(parsed, tables):
        g1, g2 = item["groups"]
        merged_rows.append([
            item["outcome_label"],
            f"{g1['n']}, {g1['desc']}",
            f"{g2['n']}, {g2['desc']}",
            item["t"],
            item["df"],
            item["p"],
            item["d"],
        ])
        summaries.append({
            "outcome_label": item["outcome_label"],
            **(item["meta"] or {}),
            "grouping_label": grouping,
        })

    title = (
        f"Katılımcıların Ölçek Puanlarının {grouping} Gruplarına Göre "
        f"Karşılaştırılması (Bağımsız Örneklem t-Testi)"
    )
    first_no = tables[0].get("table_number")
    return make_result(
        "ttest",
        int(first_no) if first_no else 1,
        title,
        headers,
        merged_rows,
        tables[0].get("note") or "Not. * p < .05.",
        combined=True,
        grouping_label=grouping,
        comparison_summaries=summaries,
    )


def _parse_mann_whitney_rows(result: dict) -> Optional[Dict[str, Any]]:
    rows = result.get("rows") or []
    if len(rows) < 2:
        return None
    groups = []
    for row in rows[:2]:
        if len(row) < 4:
            return None
        groups.append({
            "label": _strip_html(str(row[1])),
            "n": row[2],
            "desc": _strip_html(str(row[3])),
        })
    stats_row = rows[0]
    return {
        "outcome_label": result.get("outcome_label") or _strip_html(str(stats_row[0])),
        "groups": groups,
        "u": stats_row[4] if len(stats_row) > 4 else "",
        "z": stats_row[5] if len(stats_row) > 5 else "",
        "p": stats_row[6] if len(stats_row) > 6 else "",
        "r": stats_row[7] if len(stats_row) > 7 else "",
        "meta": {
            "U": result.get("U"),
            "z": result.get("z"),
            "p": result.get("p"),
            "r": result.get("r"),
            "significant": result.get("significant"),
            "groups": result.get("groups"),
        },
    }


def merge_mann_whitney_tables(tables: List[dict]) -> Optional[dict]:
    parsed = [_parse_mann_whitney_rows(t) for t in tables]
    parsed = [p for p in parsed if p]
    if len(parsed) < 2:
        return None

    grouping = tables[0].get("grouping_label") or "Gruplandırıcı"
    g1_name = parsed[0]["groups"][0]["label"]
    g2_name = parsed[0]["groups"][1]["label"]
    headers = [
        "Bağımlı Değişken",
        f"{g1_name} (n, Medyan)",
        f"{g2_name} (n, Medyan)",
        "U",
        "z",
        "p",
        "r",
    ]
    merged_rows = []
    summaries = []
    for item in parsed:
        g1, g2 = item["groups"]
        merged_rows.append([
            item["outcome_label"],
            f"{g1['n']}, {g1['desc']}",
            f"{g2['n']}, {g2['desc']}",
            item["u"],
            item["z"],
            item["p"],
            item["r"],
        ])
        summaries.append({
            "outcome_label": item["outcome_label"],
            **(item["meta"] or {}),
            "grouping_label": grouping,
        })

    title = (
        f"Katılımcıların Ölçek Puanlarının {grouping} Gruplarına Göre "
        f"Karşılaştırılması (Mann-Whitney U)"
    )
    first_no = tables[0].get("table_number")
    return make_result(
        "mann_whitney",
        int(first_no) if first_no else 1,
        title,
        headers,
        merged_rows,
        tables[0].get("note") or "Not. * p < .05. Non-parametrik test.",
        combined=True,
        grouping_label=grouping,
        comparison_summaries=summaries,
    )


def merge_anova_tables(tables: List[dict]) -> Optional[dict]:
    if len(tables) < 2:
        return None

    grouping = tables[0].get("grouping_label") or "Gruplandırıcı"
    headers = ["Bağımlı Değişken", "F", "df", "p", "η²"]
    merged_rows = []
    summaries = []
    for t in tables:
        outcome = t.get("outcome_label") or "—"
        f_val = t.get("f", "—")
        df1, df2 = t.get("df1"), t.get("df2")
        df_txt = f"({df1}, {df2})" if df1 is not None and df2 is not None else "—"
        p_val = t.get("p")
        p_txt = fmt_p_display(float(p_val)) if p_val is not None else "—"
        eta = t.get("eta_squared")
        eta_txt = fmt_r(float(eta)) if eta is not None else "—"
        merged_rows.append([outcome, str(f_val), df_txt, p_txt, str(eta_txt)])
        summaries.append({
            "outcome_label": outcome,
            "f": f_val,
            "p": p_val,
            "eta_squared": eta,
            "significant": t.get("significant"),
            "grouping_label": grouping,
        })

    title = (
        f"Katılımcıların Ölçek Puanlarının {grouping} Gruplarına Göre "
        f"Karşılaştırılması (Tek Yönlü ANOVA)"
    )
    first_no = tables[0].get("table_number")
    note = (
        "Not. Grup ortalamaları ve post-hoc sonuçları anlamlı modeller için "
        "ilgili ayrıntı tablolarında sunulmuştur."
    )
    return make_result(
        "anova",
        int(first_no) if first_no else 1,
        title,
        headers,
        merged_rows,
        note,
        combined=True,
        grouping_label=grouping,
        comparison_summaries=summaries,
    )


def _merge_by_grouping(
    results: List[dict],
    test_type: str,
    merge_fn,
) -> List[dict]:
    from collections import defaultdict

    buckets: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, r in enumerate(results):
        if r.get("type") != test_type or r.get("combined"):
            continue
        key = _grouping_merge_key(r)
        if not key[1]:
            continue
        buckets[key].append(i)

    drop: set = set()
    inserts: List[Tuple[int, dict]] = []
    for indices in buckets.values():
        if len(indices) < 2:
            continue
        merged = merge_fn([results[i] for i in indices])
        if not merged:
            continue
        drop.update(indices)
        inserts.append((min(indices), merged))

    if not drop:
        return results

    rebuilt: List[dict] = []
    inserted_at: set = set()
    for i, r in enumerate(results):
        if i in drop:
            for pos, item in inserts:
                if pos == i and pos not in inserted_at:
                    rebuilt.append(item)
                    inserted_at.add(pos)
            continue
        rebuilt.append(r)
    return rebuilt


def move_normality_to_descriptive_footnote(results: List[dict]) -> List[dict]:
    norm_idx = [i for i, r in enumerate(results) if r.get("type") == "normality"]
    if not norm_idx:
        return results

    parts: List[str] = []
    for idx in norm_idx:
        table = results[idx]
        for row in table.get("rows") or []:
            if len(row) < 4:
                continue
            var = _strip_html(str(row[0]))
            stat = _strip_html(str(row[1]))
            df_val = _strip_html(str(row[2]))
            p_val = _strip_html(str(row[3]))
            parts.append(f"{var} ({stat}, df = {df_val}, p = {p_val})")

    if not parts:
        return results

    footnote = "Normallik analizi: " + "; ".join(parts) + "."

    desc_idx = next(
        (i for i, r in enumerate(results) if r.get("type") == "descriptive"),
        None,
    )
    if desc_idx is None:
        return results

    desc = dict(results[desc_idx])
    base_note = (desc.get("note") or "").rstrip(".")
    desc["note"] = f"{base_note}. {footnote}" if base_note else footnote
    desc["normality_footnote"] = footnote
    results[desc_idx] = desc

    return [r for i, r in enumerate(results) if i not in norm_idx]


def _rebuild_excluding_indices(results: List[dict], drop: set, insert_at: int, new_item: dict) -> List[dict]:
    rebuilt: List[dict] = []
    inserted = False
    for i, r in enumerate(results):
        if i in drop:
            if not inserted and i >= insert_at:
                rebuilt.append(new_item)
                inserted = True
            continue
        rebuilt.append(r)
    if not inserted:
        rebuilt.insert(min(insert_at, len(rebuilt)), new_item)
    return rebuilt


def normalize_table_layout(
    results: List[dict],
    config: Optional[LayoutConfig] = None,
) -> List[dict]:
    """Akademik tablo düzeni: birleştirme, sıralama, yerelleştirme."""
    if not results:
        return []

    cfg = config or DEFAULT_LAYOUT_CONFIG
    results = copy.deepcopy(results)

    cronbach_idx = [i for i, r in enumerate(results) if r.get("type") == "cronbach"]
    if cronbach_idx:
        merged = merge_cronbach_results([results[i] for i in cronbach_idx])
        if merged:
            results = _rebuild_excluding_indices(results, set(cronbach_idx), cronbach_idx[0], merged)

    if cfg.merge_demographics:
        demo_idx = [i for i, r in enumerate(results) if _is_demographic_frequency(r)]
        if len(demo_idx) >= 2:
            merged_demo = merge_demographic_frequencies([results[i] for i in demo_idx])
            if merged_demo:
                results = _rebuild_excluding_indices(
                    results, set(demo_idx), demo_idx[0], merged_demo,
                )
        elif len(demo_idx) == 1:
            single = dict(results[demo_idx[0]])
            single["type"] = "demographics"
            single["title"] = _DEMOGRAPHICS_TITLE
            results[demo_idx[0]] = single

    if cfg.merge_group_comparisons:
        results = _merge_by_grouping(results, "ttest", merge_ttest_tables)
        results = _merge_by_grouping(results, "mann_whitney", merge_mann_whitney_tables)
        results = _merge_by_grouping(results, "anova", merge_anova_tables)

    if cfg.suppress_normality_to_footnote:
        results = move_normality_to_descriptive_footnote(results)

    if cfg.correlation_lower_triangle:
        results = [
            correlation_lower_triangle(r)
            if r.get("type") in ("correlation_matrix", "correlation")
            else r
            for r in results
        ]

    results = sort_tables_by_priority(results)
    results = renumber_tables(results, cfg)
    results = [apply_locale_to_result(r, cfg) for r in results]
    return results
