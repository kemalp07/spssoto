"""Madde türev sütunları (ters/kodlanmış) — sayım ve gösterim testleri."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from data_cleaning import (
    apply_scale_item_resolution,
    normalize_item_root,
    partition_item_variants,
)


def test_normalize_item_root_strips_suffix_and_prefix():
    assert normalize_item_root("item_1_ters") == normalize_item_root("item_1")
    assert normalize_item_root("rev_item_2") == normalize_item_root("item_2")
    assert normalize_item_root("item_1_recoded") == normalize_item_root("item_1")


def test_item_1_and_item_1_ters_count_as_one():
    items = ["item_1", "item_1_ters"]
    display, cronbach, count = partition_item_variants(items)
    assert count == 1
    assert display == ["item_1"]
    assert cronbach == ["item_1_ters"]
    assert len(display) == 1


def test_item_1_and_item_2_ters_count_as_two():
    items = ["item_1", "item_2_ters"]
    display, cronbach, count = partition_item_variants(items)
    assert count == 2
    assert set(display) == {"item_1", "item_2_ters"}
    assert set(cronbach) == {"item_1", "item_2_ters"}


def test_apply_scale_item_resolution_variant_map():
    resolved = apply_scale_item_resolution(["item_1", "item_1_ters", "item_2"])
    assert resolved["item_count"] == 2
    assert resolved["items"] == ["item_1", "item_2"]
    assert resolved["cronbach_items"] == ["item_1_ters", "item_2"]
    assert resolved["item_variant_map"]["item_1"] == "item_1_ters"
    assert resolved["item_variant_map"]["item_2"] == "item_2"


@pytest.mark.parametrize("suffix", [
    "_ters", "_T", "_r", "_rev", "_reversed", "_recoded", "_rc", "_inv", "_inverted",
])
def test_suffix_variants_share_root(suffix):
    assert normalize_item_root(f"oys_3{suffix}") == normalize_item_root("oys_3")


@pytest.mark.parametrize("prefix", ["rev_", "recoded_", "inv_"])
def test_prefix_variants_share_root(prefix):
    assert normalize_item_root(f"{prefix}neq_4") == normalize_item_root("neq_4")
