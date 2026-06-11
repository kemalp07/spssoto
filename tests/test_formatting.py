"""p formatlama birim testleri."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from formatting import fmt_p, fmt_p_display, p_stars


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
