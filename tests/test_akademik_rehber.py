"""Akademik rehber yükleme testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from akademik_rehber.loader import (
    effect_size_label,
    hypothesis_phrase,
    llm_compact_rules,
    posthoc_empty_phrase,
)
from yorum_motoru import build_llm_rules_block, corr_strength_label


def test_effect_size_cohens_d():
    assert effect_size_label("cohens_d", 0.85) == "büyük"
    assert effect_size_label("cohens_d", 0.55) == "orta"
    assert effect_size_label("cohens_d", 0.25) == "küçük"


def test_correlation_strength_from_rehber():
    assert corr_strength_label(0.45) == "orta düzeyde"
    assert corr_strength_label(0.15) == "zayıf"
    assert corr_strength_label(0.55) == "güçlü"


def test_posthoc_empty_phrases():
    assert "Tukey" in posthoc_empty_phrase("tukey")
    assert "Games-Howell" in posthoc_empty_phrase("games_howell")
    assert "Dunn" in posthoc_empty_phrase("dunn") or "Bonferroni" in posthoc_empty_phrase("dunn")


def test_epsilon_squared_labels():
    assert effect_size_label("epsilon_squared", 0.15) == "büyük"
    assert effect_size_label("epsilon_squared", 0.08) == "orta"


def test_hypothesis_phrase():
    assert "H1" in hypothesis_phrase("H1", True)
    assert "desteklenmemiştir" in hypothesis_phrase("H2", False)


def test_llm_rules_block_nonempty():
    assert len(llm_compact_rules()) >= 5
    assert "p < .05" in build_llm_rules_block()
