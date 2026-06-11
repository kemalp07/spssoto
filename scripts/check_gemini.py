#!/usr/bin/env python3
"""Gemini / Google AI Studio API baglantisini kontrol eder."""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

from config import ENABLE_GEMINI_ENRICH, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_USE_VERTEX  # noqa: E402
from llm_router import _make_gemini_client, gemini_api_mode  # noqa: E402


def key_kind(key: str) -> str:
    if key.startswith("AQ."):
        return "AI Studio (yeni AQ...)"
    if key.startswith("AIza"):
        return "AI Studio (klasik AIza...)"
    return "bilinmeyen format"


def main() -> int:
    shell_key = os.environ.get("GEMINI_API_KEY", "")
    print("Gemini yapilandirma")
    print(f"  ENABLE_GEMINI_ENRICH: {ENABLE_GEMINI_ENRICH}")
    print(f"  MODEL: {GEMINI_MODEL}")
    print(f"  GEMINI_USE_VERTEX: {GEMINI_USE_VERTEX}")
    print(f"  Mod: {gemini_api_mode()}")
    if shell_key and shell_key != (GEMINI_API_KEY or ""):
        print("  [UYARI] Shell GEMINI_API_KEY != backend/.env — .env oncelikli")
    if GEMINI_USE_VERTEX and GEMINI_API_KEY and (
        GEMINI_API_KEY.startswith("AQ.") or GEMINI_API_KEY.startswith("AIza")
    ):
        print("  [UYARI] AQ/AIza anahtari Studio icindir — GEMINI_USE_VERTEX=false olmali")
    if not GEMINI_API_KEY and not GEMINI_USE_VERTEX:
        print("  [HATA] GEMINI_API_KEY bos")
        return 1
    if GEMINI_API_KEY:
        print(f"  KEY: {key_kind(GEMINI_API_KEY)} ({len(GEMINI_API_KEY)} karakter)")

    from google.genai import types

    client = _make_gemini_client()
    try:
        r = client.models.generate_content(
            model=GEMINI_MODEL,
            contents="Yalnizca OK yaz.",
            config=types.GenerateContentConfig(max_output_tokens=64, temperature=0),
        )
        text = (r.text or "").strip()
        print(f"\n[OK] generateContent: {text!r}")
        return 0 if text else 1
    except Exception as exc:
        err = str(exc)
        print(f"\n[HATA] generateContent:\n  {err[:700]}")
        if "prepayment credits are depleted" in err.lower():
            print("\nEski AIza anahtari veya farkli proje — Studio'dan yeni AQ anahtar alin.")
        elif "aiplatform" in err.lower() and "403" in err:
            print("\nVertex API kapali — veya Studio anahtarini Vertex modunda kullaniyorsunuz.")
            print("Studio (AQ...) icin: GEMINI_USE_VERTEX=false")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
