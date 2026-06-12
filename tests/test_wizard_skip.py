"""Wizard adım atlama kuralları testleri."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from wizard_skip import (
    scales_from_detection,
    should_skip_labels_phase,
    should_skip_scales_step,
    should_skip_topic_step,
    topic_from_etik_kurul,
    topic_step_optional,
)


def test_skip_scales_with_high_registry_match():
    registry = [{"id": "oysto", "confidence": "high", "cols": ["oys_1"]}]
    scales = [{"name": "OYŞTÖ", "id": "oysto"}]
    assert should_skip_scales_step(registry, scales) is True


def test_show_scales_without_high_match():
    registry = [{"id": "oysto", "confidence": "medium", "cols": ["oys_1"]}]
    scales = [{"name": "OYŞTÖ"}]
    assert should_skip_scales_step(registry, scales) is False


def test_skip_topic_with_etik_hypotheses():
    etik = {"hypotheses": ["H1: X ile Y arasında fark vardır."]}
    assert should_skip_topic_step(etik) is True
    assert "H1" in topic_from_etik_kurul(etik)


def test_show_topic_without_etik():
    assert should_skip_topic_step(None) is False
    assert topic_step_optional(False) is True


def test_skip_topic_with_docx_scenario():
    """anket+etik docx: hipotez listesi varsa soru adımı atlanır."""
    etik = {
        "hypotheses": [
            "Cinsiyet ile OYS arasında fark vardır.",
            "Yaş ile GYA arasında ilişki vardır.",
        ],
        "aim": "Araştırmanın amacı...",
    }
    assert should_skip_topic_step(etik) is True
    lines = topic_from_etik_kurul(etik).split("\n")
    assert len(lines) == 2


def test_show_topic_without_docx_scenario():
    """docx yok: soru adımı zorunlu değil."""
    assert should_skip_topic_step(None) is False
    assert topic_step_optional(False) is True


def test_scales_prefill_from_detection():
    names = scales_from_detection([
        {"name": "OYŞTÖ"},
        {"name": "GYA"},
    ])
    assert names == "OYŞTÖ, GYA"


def test_skip_labels_when_all_spss_labels():
    cols = ["cinsiyet", "yas", "oys_toplam"]
    labels = {"cinsiyet": "Cinsiyet", "yas": "Yaş", "oys_toplam": "OYŞTÖ Toplam"}
    assert should_skip_labels_phase(cols, labels) is True


def test_show_labels_when_any_empty():
    cols = ["cinsiyet", "yas"]
    labels = {"cinsiyet": "Cinsiyet", "yas": "yas"}
    assert should_skip_labels_phase(cols, labels) is False
