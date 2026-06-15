"""Word export bulgu metadata testleri."""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from word_export import _bulgu_caption, _parse_bulgu_entry, build_word_document


def test_parse_bulgu_entry_structured():
    text, version, locked = _parse_bulgu_entry({
        "text": "Anlamlı fark bulundu.",
        "version": 2,
        "lockedAt": "2026-06-15T12:00:00.000Z",
    })
    assert text == "Anlamlı fark bulundu."
    assert version == 2
    assert locked.startswith("2026-06-15")


def test_parse_bulgu_entry_legacy_string():
    text, version, locked = _parse_bulgu_entry("Eski format")
    assert text == "Eski format"
    assert version is None
    assert locked is None


def test_bulgu_caption_format():
    assert _bulgu_caption(2, "2026-06-15T12:00:00.000Z") == "[Bulgu v2 · 2026-06-15]"


def test_word_export_bulgu_caption_in_document():
    doc = build_word_document(
        [{
            "type": "ttest",
            "title": "Tablo 1. Test",
            "headers": ["A", "B"],
            "rows": [["1", "2"]],
        }],
        bulgular={
            "0": {
                "text": "Test bulgusu",
                "version": 1,
                "lockedAt": "2026-06-15T10:00:00.000Z",
            },
        },
    )
    with zipfile.ZipFile(io.BytesIO(doc)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Test bulgusu" in xml
    assert "Bulgu v1" in xml
