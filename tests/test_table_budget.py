"""Tablo bütçesi ve merge_key tutarlılık testleri."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from layout_config import DEFAULT_LAYOUT_CONFIG
from table_budget import (
    PLAN_PROFILES,
    apply_table_budget,
    candidate_merge_key,
    core_candidate_ids,
    enrich_catalog_metadata,
    estimate_table_count,
)
from table_layout import normalize_table_layout
from test_planner import TIER_KESIN, TIER_ONERILEN, TIER_ONERILMEYEN, build_plan


def _ttest_candidate(outcome: str, grouping: str = "cinsiyet") -> dict:
    return {
        "id": f"ttest:{grouping}:{outcome}",
        "test": "ttest",
        "vars": [grouping, outcome],
    }


def test_estimate_ttest_same_grouping_merges_to_one_table():
    candidates = [
        _ttest_candidate("sonuc1"),
        _ttest_candidate("sonuc2"),
        _ttest_candidate("sonuc3"),
    ]
    assert estimate_table_count(candidates) == 1
    keys = {candidate_merge_key(c) for c in candidates}
    assert len(keys) == 1


def test_profile_budgets_not_exceeded_on_synthetic_catalog():
    uygun = [
        {"id": "descriptive", "test": "descriptive", "vars": ["o1", "o2"]},
        {"id": "correlation", "test": "correlation", "vars": ["o1", "o2", "o3"]},
    ]
    for i in range(6):
        uygun.append({"id": f"frequency:v{i}", "test": "frequency", "vars": [f"v{i}"]})
    for i in range(6):
        uygun.append(_ttest_candidate(f"out{i}"))
    for i in range(6):
        uygun.append({
            "id": f"chi_square:g:o{i}",
            "test": "chi_square",
            "vars": ["cinsiyet", f"cat{i}"],
        })

    core_ids = core_candidate_ids(uygun)
    tiers = [TIER_KESIN, TIER_ONERILEN, TIER_ONERILMEYEN]
    catalog = []
    for idx, c in enumerate(uygun):
        catalog.append({
            **c,
            "tier": tiers[min(idx // 7, 2)],
            "enabled_default": False,
        })

    enrich_catalog_metadata(catalog, DEFAULT_LAYOUT_CONFIG, core_ids)

    for profile, limit in (("oz", 8), ("standart", 12)):
        working = [dict(c) for c in catalog]
        _, estimated = build_plan(working, profile)
        assert estimated <= limit, f"{profile} profili {estimated} tablo (> {limit})"
        enabled = [c for c in working if c.get("enabled_default")]
        assert estimate_table_count(enabled) <= limit


def test_core_tables_present_in_every_profile():
    uygun = [
        {"id": "descriptive", "test": "descriptive", "vars": ["o1"]},
        {"id": "frequency:cinsiyet", "test": "frequency", "vars": ["cinsiyet"]},
        {"id": "correlation", "test": "correlation", "vars": ["o1", "o2"]},
        {"id": "cronbach:neq", "test": "cronbach", "vars": ["i1", "i2", "i3"]},
        _ttest_candidate("o1"),
    ]
    core_ids = core_candidate_ids(uygun)
    assert "descriptive" in core_ids
    assert "frequency:cinsiyet" in core_ids
    assert "correlation" in core_ids
    assert "cronbach:neq" in core_ids

    catalog = [{**c, "tier": TIER_ONERILMEYEN, "enabled_default": False} for c in uygun]
    enrich_catalog_metadata(catalog, DEFAULT_LAYOUT_CONFIG, core_ids)

    for profile in PLAN_PROFILES:
        working = [dict(c) for c in catalog]
        apply_table_budget(working, profile)
        for cid in core_ids:
            item = next(c for c in working if c["id"] == cid)
            assert item.get("cekirdek") is True
            assert item.get("enabled_default") is True
            assert item.get("butce_disi") is False


def _candidates_to_mock_results(candidates: list) -> list:
    results = []
    for c in candidates:
        test = c["test"]
        vars_ = c.get("vars") or []
        if test == "descriptive":
            results.append({"type": "descriptive", "title": "Tanımlayıcı İstatistikler"})
        elif test == "frequency":
            var = vars_[0]
            results.append({
                "type": "frequency",
                "variable": var,
                "is_demographic": True,
                "rows": [
                    [var, "Kadın", 20, "50.0"],
                    [var, "Erkek", 20, "50.0"],
                ],
            })
        elif test == "cronbach":
            results.append({
                "type": "cronbach",
                "title": f"Cronbach — {vars_[0]}",
                "headers": ["Ölçek", "Madde Sayısı", "Geçerli n", "Cronbach α", "Değerlendirme"],
                "rows": [[vars_[0], len(vars_), 40, ".85", "İyi"]],
            })
        elif test == "correlation":
            results.append({"type": "correlation_matrix", "title": "Korelasyon"})
        elif test == "ttest":
            grouping = vars_[0]
            outcome = vars_[1] if len(vars_) > 1 else "—"
            results.append({
                "type": "ttest",
                "grouping_name": grouping,
                "outcome_label": outcome,
                "rows": [
                    [outcome, "Grup1", 20, "M=3.50", 1.20, 38, ".050", ".40"],
                    ["", "Grup2", 20, "M=3.10", "", "", "", ""],
                ],
            })
        elif test == "mann_whitney":
            results.append({"type": "mann_whitney", "grouping_name": vars_[0]})
        elif test == "anova":
            results.append({"type": "anova", "grouping_name": vars_[0]})
        elif test == "chi_square":
            results.append({"type": "chi_square", "title": "Ki-Kare"})
        elif test == "kruskal_wallis":
            results.append({"type": "kruskal_wallis", "grouping_name": vars_[0]})
    return results


def test_estimate_matches_normalize_table_layout():
    selected = [
        {"id": "descriptive", "test": "descriptive", "vars": ["o1", "o2"]},
        {"id": "frequency:cinsiyet", "test": "frequency", "vars": ["cinsiyet"]},
        {"id": "frequency:bolum", "test": "frequency", "vars": ["bolum"]},
        _ttest_candidate("sonuc1"),
        _ttest_candidate("sonuc2"),
        _ttest_candidate("sonuc3"),
        {"id": "correlation", "test": "correlation", "vars": ["o1", "o2"]},
        {"id": "chi_square:cinsiyet:cat1", "test": "chi_square", "vars": ["cinsiyet", "cat1"]},
    ]
    estimated = estimate_table_count(selected)
    mock = _candidates_to_mock_results(selected)
    normalized = normalize_table_layout(mock, DEFAULT_LAYOUT_CONFIG)
    assert estimated == len(normalized), (
        f"tahmin={estimated}, normalize={len(normalized)}"
    )
