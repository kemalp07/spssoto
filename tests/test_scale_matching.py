"""match-scales / match_all_scales birim testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from ai_services import match_all_scales
from scale_registry import resolve_scale_id


def test_resolve_scale_id_strips_parentheses():
    name = "Gece Yeme Ölçeği (Night Eating Questionnaire - NEQ)"
    assert resolve_scale_id(name) == "neq"


def test_match_all_scales_neq_columns_with_long_name():
    cols = [f"neq_{i}" for i in range(1, 17)] + ["NEQ_TOPLAM", "OYS_TOPLAM", "SBITO_TOPLAM"]
    name = "Gece Yeme Ölçeği (Night Eating Questionnaire - NEQ)"
    result = match_all_scales([name], cols)
    neq = result["matches"][0]
    assert neq["item_columns"]
    assert "neq_1" in neq["item_columns"]
    assert "NEQ_TOPLAM" in neq["total_columns"]
    assert neq["confidence"] == "high"


def test_match_all_scales_neq_columns_with_anket_name():
    cols = [f"neq_{i}" for i in range(1, 17)] + ["NEQ_TOPLAM"]
    result = match_all_scales(["Gece Yeme Anketi"], cols)
    neq = result["matches"][0]
    assert len(neq["item_columns"]) >= 16
    assert "NEQ_TOPLAM" in neq["total_columns"]
