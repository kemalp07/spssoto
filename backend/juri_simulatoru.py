"""Word export öncesi kalite kontrol — Python kuralları + Claude jüri incelemesi."""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from bulgu_templates import _higher_group_name
from formatting import fmt_p
from llm_router import _parse_json_object, claude_decide, has_claude, merge_meta

PARAMETRIC_TYPES = frozenset({
    "ttest", "anova", "tukey", "paired_ttest", "regression", "correlation",
})
NON_PARAMETRIC_TYPES = frozenset({
    "mann_whitney", "kruskal_wallis", "kruskal", "dunn", "paired_wilcoxon",
})
SIG_POSTHOC_PARENTS = frozenset({"anova", "kruskal_wallis", "kruskal"})

JURI_CLAUDE_SYSTEM = """Sen tez jürisi perspektifinden istatistik tutarlılık denetçisisin.
Python kural motorunun bulgularını ve tablo özetlerini incele; gözden kaçan mantık sorunlarını ekle.
Her bulgu için kısa jüri-dili Türkçe açıklama yaz.

SADECE JSON döndür:
{
  "findings": [
    {"severity": "hata|uyari", "table_no": 4, "message": "..."}
  ],
  "overall": "temiz|sorunlu"
}

Kurallar:
- Python'un tespit ettiği hataları koru, mesajı netleştir
- Yeni bulgu ekleme: yalnızca mantıksal tutarsızlık varsa
- overall: findings boşsa temiz, aksi halde sorunlu
- table_no yoksa null kullan"""


def _norm_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _groups_means(result: dict) -> Dict[str, float]:
    groups = result.get("groups") or []
    key = "median" if str(result.get("type") or "") in NON_PARAMETRIC_TYPES else "mean"
    out: Dict[str, float] = {}
    for g in groups:
        name = str(g.get("name") or "").strip()
        if not name:
            continue
        val = g.get(key)
        if val is None:
            val = g.get("mean")
        if val is not None:
            out[name] = float(val)
    return out


def _grouping_total_n(result: dict) -> Optional[int]:
    groups = result.get("groups") or []
    if not groups:
        return None
    try:
        return int(sum(int(g.get("n") or 0) for g in groups))
    except (TypeError, ValueError):
        return None


def _highest_group_name(groups: Dict[str, float]) -> Optional[str]:
    if not groups:
        return None
    return max(groups.items(), key=lambda item: item[1])[0]


def _vars_compact(result: dict) -> str:
    if result.get("var1") and result.get("var2"):
        return f"{result['var1']}×{result['var2']}"
    g = result.get("grouping_label") or result.get("grouping_name") or ""
    o = (
        result.get("outcome_label")
        or result.get("outcome_name")
        or result.get("variable")
        or ""
    )
    if g and o:
        return f"{g}×{o}"
    if result.get("variables"):
        return "×".join(str(v) for v in result["variables"][:3])
    return str(result.get("variable") or result.get("type") or "")


def _extract_claimed_higher(bulgu: str, result: dict) -> Optional[str]:
    text = (bulgu or "").strip()
    if text:
        for pattern in (
            r"([^.;\]]+?) grubunun ortalaması daha yüksektir",
            r"([^.;\]]+?) grubunun medyanı daha yüksektir",
        ):
            m = re.search(pattern, text, re.I)
            if m:
                claim = m.group(1).strip()
                if claim:
                    return claim
    if result.get("significant"):
        groups = result.get("groups") or []
        key = "median" if result.get("type") in NON_PARAMETRIC_TYPES else "mean"
        return _higher_group_name(groups, key)
    return None


def _posthoc_present(result: dict, all_results: List[dict]) -> bool:
    rtype = str(result.get("type") or "")
    if rtype == "anova":
        want = "tukey"
    elif rtype in ("kruskal_wallis", "kruskal"):
        want = "dunn"
    else:
        return True
    g_name = result.get("grouping_name")
    o_name = result.get("outcome_name")
    for other in all_results:
        if other.get("type") != want:
            continue
        if g_name and other.get("grouping_name") != g_name:
            continue
        if o_name and other.get("outcome_name") and other.get("outcome_name") != o_name:
            continue
        return True
    return False


def _intro_mode(intro: str) -> str:
    text = (intro or "").lower()
    if "parametrik test yöntemlerinin uygulanmasına" in text:
        return "all_parametric"
    if "non-parametrik test yöntemleri uygulanmıştır" in text:
        if "parametrik ve non-parametrik" not in text:
            return "all_nonparametric"
    if "parametrik ve non-parametrik testler uygulanmıştır" in text:
        return "mixed"
    return "unknown"


def compact_quality_row(
    result: dict,
    bulgu: str = "",
    all_results: Optional[List[dict]] = None,
) -> dict:
    """Tek tablo için kompakt kalite özeti — ham tablo yok."""
    all_results = all_results or []
    rtype = str(result.get("type") or "")
    row: dict = {
        "table_no": result.get("table_number"),
        "type": rtype,
        "vars": _vars_compact(result),
        "sig": bool(result.get("significant")),
    }
    if result.get("p") is not None:
        row["p"] = fmt_p(result.get("p"))
    if result.get("f") is not None:
        row["F"] = round(float(result["f"]), 3)
    if result.get("t") is not None:
        row["t"] = round(float(result["t"]), 3)
    if result.get("H") is not None:
        row["H"] = round(float(result["H"]), 3)
    if result.get("hypothesis_id"):
        row["hypothesis_id"] = result["hypothesis_id"]
    if result.get("grouping_name"):
        row["grouping_name"] = result["grouping_name"]

    groups = _groups_means(result)
    if groups:
        row["groups"] = {k: round(v, 2) for k, v in groups.items()}

    total_n = _grouping_total_n(result)
    if total_n is not None:
        row["group_total_n"] = total_n

    if rtype in SIG_POSTHOC_PARENTS:
        row["posthoc_present"] = _posthoc_present(result, all_results)

    claimed = _extract_claimed_higher(bulgu, result)
    if claimed:
        row["claimed_higher"] = claimed

    return row


def build_compact_input(
    results: List[dict],
    bulgular: Optional[Dict[str, str]] = None,
) -> List[dict]:
    bulgular = bulgular or {}
    rows: List[dict] = []
    for idx, result in enumerate(results or []):
        if not isinstance(result, dict):
            continue
        bulgu = bulgular.get(str(idx)) or bulgular.get(idx) or ""
        rows.append(compact_quality_row(result, bulgu, results))
    return rows


def _finding(
    severity: str,
    message: str,
    table_no: Optional[int] = None,
    rule: str = "",
) -> dict:
    item = {"severity": severity, "table_no": table_no, "message": message}
    if rule:
        item["rule"] = rule
    return item


def run_python_checks(
    compact_rows: List[dict],
    intro: str,
    hypotheses: List[dict],
    n_total: Optional[int] = None,
) -> List[dict]:
    """Deterministik denetim kuralları."""
    findings: List[dict] = []
    grouping_ns: Dict[str, List[Tuple[int, int]]] = {}

    for row in compact_rows:
        table_no = row.get("table_no")
        rtype = str(row.get("type") or "")

        if (
            row.get("sig")
            and rtype in SIG_POSTHOC_PARENTS
            and not row.get("posthoc_present")
        ):
            findings.append(_finding(
                "uyari",
                f"Tablo {table_no}: Anlamlı {rtype.upper()} sonucu var ancak post-hoc tablosu yok.",
                table_no,
                "posthoc_missing",
            ))

        claimed = row.get("claimed_higher")
        groups = row.get("groups") or {}
        if claimed and groups and row.get("sig"):
            highest = _highest_group_name(groups)
            if highest and _norm_name(claimed) != _norm_name(highest):
                findings.append(_finding(
                    "hata",
                    f"Tablo {table_no}: '{claimed}' yüksek grubu olarak belirtilmiş; "
                    f"grup ortalamalarına göre en yüksek '{highest}'.",
                    table_no,
                    "claimed_higher_mismatch",
                ))

        g_key = row.get("grouping_name") or str(row.get("vars") or "").split("×")[0].strip()
        g_n = row.get("group_total_n")
        if g_key and g_n and rtype in PARAMETRIC_TYPES | NON_PARAMETRIC_TYPES:
            grouping_ns.setdefault(g_key, []).append((int(table_no or 0), int(g_n)))

    for g_key, entries in grouping_ns.items():
        if len(entries) < 2:
            continue
        ns = [n for _, n in entries]
        avg = sum(ns) / len(ns)
        if avg <= 0:
            continue
        for table_no, n in entries:
            if abs(n - avg) / avg > 0.05:
                findings.append(_finding(
                    "uyari",
                    f"Tablo {table_no}: '{g_key}' gruplandırmasında geçerli n ({n}), "
                    f"diğer tablolardan %{int(abs(n - avg) / avg * 100)} sapıyor — "
                    "kayıp veri farkı notu eklenmesi önerilir.",
                    table_no,
                    "group_n_drift",
                ))
                break

    hyp_ids_in_results = {
        str(r.get("hypothesis_id"))
        for r in compact_rows
        if r.get("hypothesis_id")
    }
    for hyp in hypotheses or []:
        hid = str(hyp.get("id") or "").strip()
        if hid and hid not in hyp_ids_in_results:
            findings.append(_finding(
                "uyari",
                f"{hid} hipotezi için eşleşen analiz sonucu bulunamadı.",
                None,
                "hypothesis_without_result",
            ))

    mode = _intro_mode(intro)
    used_types = {str(r.get("type") or "") for r in compact_rows}
    has_nonparam = bool(used_types & NON_PARAMETRIC_TYPES)
    has_param = bool(used_types & PARAMETRIC_TYPES)

    if mode == "all_parametric" and has_nonparam:
        findings.append(_finding(
            "hata",
            "Giriş metni yalnızca parametrik test uygulandığını belirtiyor; "
            "tablolarda non-parametrik testler var.",
            None,
            "intro_parametric_mismatch",
        ))
    if mode == "all_nonparametric" and has_param:
        findings.append(_finding(
            "hata",
            "Giriş metni yalnızca non-parametrik test uygulandığını belirtiyor; "
            "tablolarda parametrik testler var.",
            None,
            "intro_nonparametric_mismatch",
        ))

    return findings


def _dedupe_findings(items: List[dict]) -> List[dict]:
    seen = set()
    out: List[dict] = []
    for item in items:
        key = (item.get("severity"), item.get("table_no"), item.get("message", "")[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _normalize_output(findings: List[dict]) -> dict:
    cleaned = []
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "uyari").lower()
        if sev not in ("hata", "uyari"):
            sev = "uyari"
        cleaned.append({
            "severity": sev,
            "table_no": item.get("table_no"),
            "message": str(item.get("message") or "").strip(),
            **({"rule": item["rule"]} if item.get("rule") else {}),
        })
    cleaned = [f for f in cleaned if f["message"]]
    cleaned = _dedupe_findings(cleaned)
    overall = "temiz" if not cleaned else "sorunlu"
    return {"findings": cleaned, "overall": overall}


def run_claude_review(
    python_findings: List[dict],
    compact_rows: List[dict],
    intro: str,
    hypotheses: List[dict],
    n_total: Optional[int],
) -> Tuple[dict, dict]:
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not has_claude():
        return {}, meta

    user = (
        f"Toplam n: {n_total}\n\n"
        f"Giriş metni:\n{(intro or '')[:1200]}\n\n"
        f"Hipotezler:\n{json.dumps(hypotheses or [], ensure_ascii=False)[:2000]}\n\n"
        f"Tablo özetleri:\n{json.dumps(compact_rows, ensure_ascii=False)[:6000]}\n\n"
        f"Python bulguları:\n{json.dumps(python_findings, ensure_ascii=False)[:3000]}"
    )
    try:
        raw, decide_meta = claude_decide(JURI_CLAUDE_SYSTEM, user, max_tokens=800)
        meta = merge_meta(meta, decide_meta)
        parsed = _parse_json_object(raw)
        return parsed if parsed else {}, meta
    except RuntimeError:
        return {}, meta


def run_quality_check(
    results: List[dict],
    intro: str = "",
    hypotheses: Optional[List[dict]] = None,
    n_total: Optional[int] = None,
    bulgular: Optional[Dict[str, str]] = None,
) -> Tuple[dict, dict]:
    """Tam kalite kontrol akışı."""
    meta: dict = {
        "llm_calls": 0,
        "approx_input_tokens": 0,
        "approx_output_tokens": 0,
        "python_only": False,
    }
    compact_rows = build_compact_input(results, bulgular)
    python_findings = run_python_checks(
        compact_rows, intro, hypotheses or [], n_total,
    )

    claude_out, claude_meta = run_claude_review(
        python_findings, compact_rows, intro, hypotheses or [], n_total,
    )
    meta = merge_meta(meta, claude_meta)

    if claude_out.get("findings"):
        merged = _dedupe_findings(python_findings + list(claude_out.get("findings") or []))
    else:
        merged = python_findings
        if not claude_meta.get("llm_calls"):
            meta["python_only"] = True

    output = _normalize_output(merged)
    output["compact_rows"] = compact_rows
    output["has_errors"] = any(f["severity"] == "hata" for f in output["findings"])
    return output, meta
