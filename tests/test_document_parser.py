"""document_parser — .docx ayrıştırma testleri."""
import io
import sys
from pathlib import Path

import pytest
from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from document_parser import parse_anket_docx, parse_etik_kurul_docx


def _docx_bytes(paragraphs: list) -> bytes:
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_anket_numbered_items_parsed():
    raw = _docx_bytes([
        "Bölüm 1: Yaşam Kalitesi",
        "1. Kendimi iyi hissediyorum",
        "2. Enerjim yüksek (R)",
        "Hiç katılmıyorum ... Tamamen katılıyorum",
    ])
    result = parse_anket_docx(raw)
    assert not result.get("parse_error")
    items = result["sections"][0]["items"]
    assert len(items) >= 2
    assert items[0]["no"] == 1
    assert "hissediyorum" in items[0]["text"]
    assert items[1]["reverse_hint"] is True
    assert result["sections"][0]["scale_type"] in ("likert_5", "likert_7", "other")


def test_anket_reverse_hint_from_r_marker():
    raw = _docx_bytes(["1) Bu madde ters (R)"])
    result = parse_anket_docx(raw)
    item = result["sections"][0]["items"][0]
    assert item["reverse_hint"] is True
    assert "(R)" not in item["text"]


def test_etik_kurul_aim_extracted():
    raw = _docx_bytes([
        "Araştırmanın amacı:",
        "Bu çalışmanın amacı üniversite öğrencilerinde gece yeme davranışını incelemektir.",
    ])
    result = parse_etik_kurul_docx(raw)
    assert not result.get("parse_error")
    assert result["aim"]
    assert "gece yeme" in result["aim"].lower()


def test_etik_kurul_hypothesis_pattern():
    raw = _docx_bytes([
        "H1: Cinsiyet ile OYS puanı arasında anlamlı fark vardır.",
        "H2: Yaş ile NEQ puanı arasında anlamlı ilişki vardır.",
    ])
    result = parse_etik_kurul_docx(raw)
    assert result["hypotheses"]
    assert any("Cinsiyet" in h for h in result["hypotheses"])


def test_empty_docx_returns_parse_error():
    assert parse_anket_docx(b"")["parse_error"] is True
    assert parse_etik_kurul_docx(b"not a zip")["parse_error"] is True


def test_blank_docx_parse_error():
    raw = _docx_bytes([])
    assert parse_anket_docx(raw)["parse_error"] is True
    assert parse_etik_kurul_docx(raw)["parse_error"] is True
