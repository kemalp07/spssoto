#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env", override=True)

from analiz_oneri import ONERI_SYSTEM, gemini_analiz_oneri
from llm_router import _parse_json_object, gemini_json_task


async def main() -> int:
    cols = [
        "bolum", "dbf_cinsiyet", "OYS1", "OYS2", "OYS3",
        "OYS_TOPLAM", "NEQ1", "NEQ_TOPLAM", "SBITO_TOPLAM",
    ]
    etik = (
        "H1: Bölümler arası OYS puanında fark vardır.\n"
        "H2: Cinsiyet ile NEQ puanı arasında fark vardır.\n"
        + "Etik kurul metni. " * 400
    )
    anket = "Anket maddesi. " * 300
    user = (
        f"Sütunlar: {', '.join(cols)}\n\n"
        f"Etik kurul:\n{etik[:5000]}\n\n"
        f"Anket:\n{anket[:4000]}"
    )
    raw, meta = gemini_json_task(ONERI_SYSTEM, user, max_tokens=3000)
    print("raw_len", len(raw or ""))
    print("output_tokens", meta.get("approx_output_tokens"))
    parsed = _parse_json_object(raw or "")
    print("parsed_keys", list(parsed.keys()) if parsed else "EMPTY")
    if not parsed:
        print("raw_preview", (raw or "")[:800])
        print("raw_tail", (raw or "")[-300:])
    result = await gemini_analiz_oneri(cols, {}, anket, etik, None)
    print("plan_source", result["meta"].get("plan_source"))
    print("gemini_error", result["meta"].get("gemini_error"))
    print("gerekce_count", len(result["oneri"].get("gerekceler") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
