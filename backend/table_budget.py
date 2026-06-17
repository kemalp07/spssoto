"""Tablo bütçesi tahmini — table_layout birleştirme kurallarıyla uyumlu."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from layout_config import DEFAULT_LAYOUT_CONFIG, LayoutConfig

PLAN_PROFILES: Dict[str, int] = {
    "oz": 15,
    "standart": 30,
    "kapsamli": 50,
}

MERGE_GROUP_TEST_TYPES = ("ttest", "mann_whitney", "anova")

_LIFESTYLE_VARS = frozenset({"dbf_sk", "dbf_ak", "dbf_ik", "dbf_kh"})


def _is_lifestyle_candidate(item: dict) -> bool:
    vars_lower = {str(v).lower() for v in (item.get("vars") or [])}
    return bool(vars_lower & _LIFESTYLE_VARS)


def grouping_merge_key_result(result: dict) -> Tuple[str, str]:
    """table_layout._merge_by_grouping ile aynı anahtar."""
    rtype = str(result.get("type") or "")
    grouping = (
        result.get("grouping_name")
        or result.get("grouping_label")
        or result.get("grouping")
        or ""
    )
    if not grouping and rtype in ("frequency", "demographics"):
        grouping = str(result.get("variable") or "")
    return rtype, str(grouping).strip().lower()


def candidate_merge_key(
    candidate: dict,
    layout_config: Optional[LayoutConfig] = None,
) -> str:
    """Frontend yerel sayaç ve backend tahmini için ortak anahtar."""
    cfg = layout_config or DEFAULT_LAYOUT_CONFIG
    test = str(candidate.get("test") or "")
    cid = str(candidate.get("id") or test)
    vars_ = candidate.get("vars") or []

    if test == "frequency":
        return "frequency:__demographics__"
    if test == "cronbach":
        return "cronbach:__merged__"
    if test in MERGE_GROUP_TEST_TYPES and cfg.merge_group_comparisons:
        grouping = vars_[0] if vars_ else ""
        return f"{test}:{str(grouping).strip().lower()}"
    return cid


def estimate_table_count(
    candidates: List[dict],
    layout_config: Optional[LayoutConfig] = None,
) -> int:
    """Seçili adaylardan birleştirme sonrası tablo sayısını tahmin eder."""
    cfg = layout_config or DEFAULT_LAYOUT_CONFIG
    if not candidates:
        return 0

    pool = list(candidates)
    total = 0

    cronbach = [c for c in pool if c.get("test") == "cronbach"]
    if cronbach:
        total += 1
        pool = [c for c in pool if c.get("test") != "cronbach"]

    frequencies = [c for c in pool if c.get("test") == "frequency"]
    if frequencies:
        total += 1 if cfg.merge_demographics else len(frequencies)
        pool = [c for c in pool if c.get("test") != "frequency"]

    if cfg.merge_group_comparisons:
        for test_type in MERGE_GROUP_TEST_TYPES:
            items = [c for c in pool if c.get("test") == test_type]
            if not items:
                continue
            buckets: Dict[str, int] = {}
            for c in items:
                g = (c.get("vars") or [""])[0]
                key = f"{test_type}:{str(g).strip().lower()}"
                buckets[key] = buckets.get(key, 0) + 1
            total += len(buckets)
            pool = [c for c in pool if c.get("test") != test_type]
    else:
        for test_type in MERGE_GROUP_TEST_TYPES:
            items = [c for c in pool if c.get("test") == test_type]
            total += len(items)
            pool = [c for c in pool if c.get("test") != test_type]

    total += len(pool)
    return total


_PRIMARY_DEMO_FREQ = frozenset({
    "bolum", "cinsiyet", "gender", "yas", "age",
    "dbf_cinsiyet", "dbf_yas", "department", "dept",
})


def _is_primary_demographic_frequency(c: dict) -> bool:
    var_name = ((c.get("vars") or [""])[0] or "").lower()
    return (
        var_name in _PRIMARY_DEMO_FREQ
        or "bolum" in var_name
        or "cinsiyet" in var_name
    )


def core_candidate_ids(uygun: List[dict]) -> set:
    """Her profilde zorunlu çekirdek aday kimlikleri."""
    ids: set = set()
    has_cronbach = any(c.get("test") == "cronbach" for c in uygun)
    has_correlation = any(c.get("test") == "correlation" for c in uygun)
    for c in uygun:
        test = c.get("test")
        if test == "descriptive":
            ids.add(c["id"])
        elif test == "frequency" and _is_primary_demographic_frequency(c):
            ids.add(c["id"])
        elif test == "cronbach" and has_cronbach:
            ids.add(c["id"])
        elif test == "correlation" and has_correlation:
            ids.add(c["id"])
    return ids


def enrich_catalog_metadata(
    catalog: List[dict],
    layout_config: Optional[LayoutConfig] = None,
    core_ids: Optional[set] = None,
) -> None:
    cfg = layout_config or DEFAULT_LAYOUT_CONFIG
    core_ids = core_ids or set()
    for item in catalog:
        item["merge_key"] = candidate_merge_key(item, cfg)
        item["cekirdek"] = item["id"] in core_ids
        item.setdefault("butce_disi", False)


def apply_table_budget(
    catalog: List[dict],
    profile: str,
    layout_config: Optional[LayoutConfig] = None,
) -> Tuple[List[dict], int]:
    """Profil bütçesine göre varsayılan seçimleri ayarlar."""
    cfg = layout_config or DEFAULT_LAYOUT_CONFIG
    budget = PLAN_PROFILES.get(profile, PLAN_PROFILES["standart"])
    tier_order = {"kesin_onerilen": 0, "onerilen": 1, "onerilmeyen": 2}

    enabled: List[dict] = []

    for item in catalog:
        if item.get("cekirdek"):
            item["enabled_default"] = True
            item["butce_disi"] = False
            enabled.append(item)

    for item in sorted(
        [c for c in catalog if not c.get("cekirdek")],
        key=lambda c: (
            0 if c.get("hypothesis_id") else 1,
            tier_order.get(c.get("tier", ""), 9),
            c.get("id", ""),
        ),
    ):
        trial = enabled + [item]
        if estimate_table_count(trial, cfg) <= budget:
            item["enabled_default"] = True
            item["butce_disi"] = False
            enabled.append(item)
        else:
            item["enabled_default"] = False
            if _is_lifestyle_candidate(item):
                item["butce_disi"] = False
                item["display_section"] = "accordion"
            else:
                item["butce_disi"] = True

    return catalog, estimate_table_count(enabled, cfg)
