"""Deterministik test planlama ve token-verimli LLM seçimi."""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import pandas as pd

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from constants import (
    REASON_CODES,
    REASON_TEMPLATES,
    PLAN_TEST_SYSTEM,
    SCALE_SCORE_RE,
)
from data_cleaning import detect_scale_groups, is_numeric_continuous
from schemas import Variable
from stat_tests import assess_normality

_LABEL_MAX = 40
_MIN_GROUP_N = 10
_IMBALANCE_RATIO = 0.90


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


def build_candidate_tests(
    df: pd.DataFrame,
    variables: List[Variable],
    norm_map: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    norm_map = norm_map or {}
    active = [v for v in variables if v.included]
    cat_vars = [v for v in active if v.type == "categorical"]
    cont_vars = [v for v in active if v.type == "continuous"]
    grouping_cat = [v for v in cat_vars if v.role == "grouping"]
    outcome_cat = [v for v in cat_vars if v.role == "outcome"]
    grouping_cont = [v for v in cont_vars if v.role == "grouping"]
    outcome_cont = [v for v in cont_vars if v.role == "outcome"]
    all_cont = outcome_cont + grouping_cont

    scale_groups = detect_scale_groups(list(df.columns))
    candidates: List[dict] = []
    seq = 0

    def add(test: str, vars: List[str], **extra: Any) -> None:
        nonlocal seq
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

    if outcome_cont:
        add("normality", [v.name for v in outcome_cont])

    for v in grouping_cat + outcome_cat:
        if v.name in df.columns:
            add("frequency", [v.name])

    for cv in grouping_cat:
        if cv.name not in df.columns:
            continue
        for ov in outcome_cat:
            if ov.name not in df.columns:
                continue
            if SCALE_SCORE_RE.search(ov.name):
                continue
            add(
                "chi_square",
                [cv.name, ov.name],
                n_groups=int(df[cv.name].dropna().nunique()),
                min_group_n=_min_group_n(df, cv.name),
            )

    from stat_tests import _is_demographic_continuous

    cont_targets = [
        v for v in outcome_cont + grouping_cont
        if v.name in df.columns
        and is_numeric_continuous(df, v, norm_map)
        and not _is_demographic_continuous(v)
    ]
    for cv in grouping_cat:
        if cv.name not in df.columns:
            continue
        n_groups = int(df[cv.name].dropna().nunique())
        if n_groups < 2:
            continue
        min_n = _min_group_n(df, cv.name)
        for sv in cont_targets:
            parametric = norm_map.get(sv.name, {}).get("is_parametric", True)
            if n_groups == 2:
                test = "ttest" if parametric else "mann_whitney"
            else:
                test = "anova" if parametric else "kruskal_wallis"
            add(
                test,
                [cv.name, sv.name],
                n_groups=n_groups,
                min_group_n=min_n,
                parametric=bool(parametric),
            )

    corr_vars = [v for v in outcome_cont if is_numeric_continuous(df, v, norm_map)]
    if len(corr_vars) >= 2:
        add(
            "correlation",
            [v.name for v in corr_vars],
            parametric=all(
                norm_map.get(v.name, {}).get("is_parametric", True) for v in corr_vars
            ),
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
    vmap = _var_lookup(variables)
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

    flagged: List[dict] = []
    for c in candidates:
        item = dict(c)
        flag = "uygun"
        test, vars_ = item["test"], item.get("vars") or []

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
        for v in variables if v.included
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
) -> Tuple[dict, dict]:
    meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    if not uygun_candidates:
        return {"selected": [], "excluded": []}, meta
    if not ANTHROPIC_API_KEY:
        return {
            "selected": [c["id"] for c in uygun_candidates],
            "excluded": [],
        }, meta

    compact = _compact_candidates_for_llm(uygun_candidates)
    user_msg = (
        f"Amaç: {research_aim.strip()[:500]}\n"
        f"Etiketler: {json.dumps(labels, ensure_ascii=False)}\n"
        f"Adaylar: {json.dumps(compact, ensure_ascii=False)}"
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1000,
        system=PLAN_TEST_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    meta["llm_calls"] = 1
    if msg.usage:
        meta["approx_input_tokens"] = int(msg.usage.input_tokens or 0)
        meta["approx_output_tokens"] = int(msg.usage.output_tokens or 0)
    return _parse_llm_selection(msg.content[0].text), meta


def build_norm_map(df: pd.DataFrame, variables: List[Variable]) -> Dict[str, dict]:
    norm_map: Dict[str, dict] = {}
    for v in variables:
        if v.included and v.type == "continuous" and v.name in df.columns:
            try:
                norm_map[v.name] = assess_normality(df[v.name])
            except Exception:
                norm_map[v.name] = {"is_parametric": True, "normal": True, "n": 0}
    return norm_map


async def plan_tests(
    df: pd.DataFrame,
    variables: List[Variable],
    research_aim: str,
    use_ai: bool = True,
) -> Tuple[List[dict], List[dict], dict]:
    """Önerilen ve elenen test listeleri + meta döndürür."""
    norm_map = build_norm_map(df, variables)
    candidates = build_candidate_tests(df, variables, norm_map)
    candidates = apply_deterministic_flags(df, variables, candidates)
    by_id = {c["id"]: c for c in candidates}

    auto_excluded = [c for c in candidates if c["auto_flag"] != "uygun"]
    uygun = [c for c in candidates if c["auto_flag"] == "uygun"]

    llm_meta = {"llm_calls": 0, "approx_input_tokens": 0, "approx_output_tokens": 0}
    llm_selected: List[str] = []
    llm_excluded: List[dict] = []

    if use_ai and research_aim.strip():
        selection, llm_meta = await select_tests_with_llm(
            uygun, research_aim, _compact_labels(variables),
        )
        llm_selected = selection.get("selected") or []
        llm_excluded = selection.get("excluded") or []
    else:
        llm_selected = [c["id"] for c in uygun]

    selected_ids = set(llm_selected)
    if not selected_ids and uygun:
        selected_ids = {c["id"] for c in uygun}

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

    for item in llm_excluded:
        cid = item["id"]
        cand = by_id.get(cid)
        if not cand or cand["auto_flag"] != "uygun":
            continue
        code = item["reason_code"]
        excluded.append({
            **cand,
            "reason_code": code,
            "reason": format_reason(code, cand, variables),
            "selected": False,
            "label": candidate_display_label(cand, variables),
        })
        selected_ids.discard(cid)

    for c in uygun:
        if c["id"] in selected_ids:
            recommended.append({
                **c,
                "selected": True,
                "recommended": True,
                "label": candidate_display_label(c, variables),
                "count": 1,
            })
        elif not any(e["id"] == c["id"] for e in excluded):
            excluded.append({
                **c,
                "reason_code": "dusuk_oncelik",
                "reason": format_reason("dusuk_oncelik", c, variables),
                "selected": False,
                "label": candidate_display_label(c, variables),
            })

    return recommended, excluded, {
        "llm_calls": llm_meta["llm_calls"],
        "approx_input_tokens": llm_meta["approx_input_tokens"],
        "approx_output_tokens": llm_meta.get("approx_output_tokens", 0),
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
