"""scale_registry.py birim testleri."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from scale_registry import (
    clear_registry_cache,
    get_cutoff,
    load_registry,
    match_by_item_text,
    match_by_prefix,
    match_scale,
    resolve_scale_id,
    validate_turkish,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_registry_cache()
    yield
    clear_registry_cache()


def test_load_registry_missing_file(tmp_path, monkeypatch):
    missing = tmp_path / "missing.json"
    monkeypatch.setattr("scale_registry._REGISTRY_PATH", missing)
    clear_registry_cache()
    assert load_registry() == []


def test_resolve_scale_id_nutrition_scales():
    assert resolve_scale_id("Sağlıklı Beslenmeye İlişkin Tutum Ölçeği") == "ashn"
    assert resolve_scale_id("SBİTO") == "ashn"
    assert resolve_scale_id("SBITO") == "ashn"
    assert resolve_scale_id("Gece Yeme Anketi") == "neq"
    assert resolve_scale_id("GYA") == "neq"
    assert resolve_scale_id("Online Yemek Siparişlerine Yönelik Tutum Ölçeği") == "oysto"
    assert resolve_scale_id("BES") == "bes"


def test_match_by_prefix_oysto():
    cols = ["oys_1", "oys_2", "oys_3", "oys_4", "oys_5"]
    matches = match_by_prefix(cols)
    ids = {m["scale"]["id"] for m in matches}
    assert "oysto" in ids
    oys = next(m for m in matches if m["scale"]["id"] == "oysto")
    assert oys["confidence"] == "high"
    assert len(oys["matched_cols"]) == 5


def test_match_by_prefix_neq_gya():
    cols = ["neq_1", "neq_2", "gya_3", "gya_4"]
    matches = match_by_prefix(cols)
    ids = {m["scale"]["id"] for m in matches}
    assert "neq" in ids
    neq = next(m for m in matches if m["scale"]["id"] == "neq")
    assert set(neq["matched_cols"]) >= {"neq_1", "neq_2", "gya_3", "gya_4"}


def test_match_by_prefix_prefers_reversed_over_original():
    cols = ["neq_1", "neq_1_ters", "neq_2", "neq_2_ters", "neq_3"]
    matches = match_by_prefix(cols)
    neq = next(m for m in matches if m["scale"]["id"] == "neq")
    assert set(neq["matched_cols"]) == {"neq_1_ters", "neq_2_ters", "neq_3"}
    assert len(neq["matched_cols"]) == 3


def test_match_by_prefix_prefers_reversed_sbito_t_suffix():
    cols = ["sbito_6", "SBITO_6_T", "sbito_7", "SBITO_7_T"]
    matches = match_by_prefix(cols)
    ashn = next(m for m in matches if m["scale"]["id"] == "ashn")
    assert set(ashn["matched_cols"]) == {"SBITO_6_T", "SBITO_7_T"}
    assert len(ashn["matched_cols"]) == 2


def test_match_by_prefix_keeps_original_when_no_reversed():
    cols = ["neq_1_ters", "neq_2"]
    matches = match_by_prefix(cols)
    neq = next(m for m in matches if m["scale"]["id"] == "neq")
    assert set(neq["matched_cols"]) == {"neq_1_ters", "neq_2"}


def test_match_by_prefix_sf36():
    cols = ["sf_1", "sf36_2", "sf36_3"]
    matches = match_by_prefix(cols)
    ids = {m["scale"]["id"] for m in matches}
    assert "sf36" in ids
    sf = next(m for m in matches if m["scale"]["id"] == "sf36")
    assert set(sf["matched_cols"]) == set(cols)


def test_match_by_item_text_orto15():
    label = (
        "Yemek yerken yiyeceğin kalorisinden çok sağlıklı "
        "olup olmadığını düşünürüm"
    )
    matches = match_by_item_text({"orto_m1": label})
    assert matches
    best = max(matches, key=lambda m: m.get("similarity", 0))
    assert best["scale"]["id"] == "orto15"
    assert best["confidence"] in ("medium", "high")
    assert best.get("similarity", 0) >= 0.25


def test_prefix_conflict_longer_wins():
    mock_registry = [
        {
            "id": "psqi",
            "names": ["PSQI"],
            "prefix_hints": ["psqi_"],
            "item_sample": [],
            "reverse_items": [],
            "cutoff": None,
            "turkish_validity": {},
        },
        {
            "id": "ps",
            "names": ["PS"],
            "prefix_hints": ["ps_"],
            "item_sample": [],
            "reverse_items": [],
            "cutoff": None,
            "turkish_validity": {},
        },
    ]
    with patch("scale_registry.load_registry", return_value=mock_registry):
        matches = match_by_prefix(["psqi_1", "psqi_2"])
    assert len(matches) == 1
    assert matches[0]["scale"]["id"] == "psqi"
    assert matches[0]["matched_cols"] == ["psqi_1", "psqi_2"]


def test_get_cutoff_neq():
    cutoff = get_cutoff("neq")
    assert cutoff is not None
    assert cutoff["value"] == 25
    assert "interpretation" in cutoff


def test_validate_turkish_vas_false():
    assert validate_turkish("vas") is False


def test_validate_turkish_bdi_true():
    assert validate_turkish("bdi") is True


def test_match_scale_merges_prefix_and_text():
    cols = ["oys_1", "oys_2", "oys_3"]
    labels = {
        "oys_1": "Online yemek sipariş sitesinin kullanım kolaylığı benim için önemlidir",
    }
    merged = match_scale(cols, labels)
    assert any(m["scale"]["id"] == "oysto" for m in merged)
