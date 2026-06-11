"""p formatlama birim testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from formatting import apa_italicize_stats, fmt_p, fmt_p_display, p_stars


def test_fmt_p_small():
    assert fmt_p(0.0004) == "< .001"


def test_fmt_p_mid():
    assert fmt_p(0.042).startswith(".042") or fmt_p(0.042) == ".042"


def test_fmt_p_none():
    assert fmt_p(None) == "—"


def test_p_stars():
    assert p_stars(0.0005) == "***"
    assert p_stars(0.02) == "*"
    assert p_stars(0.10) == ""


def test_fmt_p_display_includes_stars():
    assert "***" in fmt_p_display(0.0001)


def test_apa_italicize_preserves_turkish_words():
    assert apa_italicize_stats("Katılımcıların") == "Katılımcıların"
    assert apa_italicize_stats("Yaşların") == "Yaşların"
    assert apa_italicize_stats("kayıp") == "kayıp"
    assert "<em>n</em>" not in apa_italicize_stats("Katılımcıların Ölçek Puanlarının")


def test_apa_italicize_stats_symbols():
    assert apa_italicize_stats("n = 120") == "<em>n</em> = 120"
    assert apa_italicize_stats("p = .021") == "<em>p</em> = .021"
