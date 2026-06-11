#!/usr/bin/env python3
"""FastAPI uç noktalarını TestClient ile dener."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
FIXTURE = Path(__file__).resolve().parent.parent / "testdata"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=True)

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from data_cleaning import normalize_variable_labels  # noqa: E402
from main import app  # noqa: E402
from schemas import AnalysisRequest, DataRow, PlanTestsRequest, Variable  # noqa: E402


def _find_sav() -> Path:
    for name in ("anket.sav", "kemal.büsra.sav", "data.sav"):
        p = FIXTURE / name
        if p.is_file():
            return p
    matches = list(FIXTURE.glob("*.sav"))
    if len(matches) == 1:
        return matches[0]
    raise FileNotFoundError(f"testdata/*.sav bulunamadi: {FIXTURE}")


def main() -> int:
    client = TestClient(app)
    steps = 0

    r = client.get("/")
    assert r.status_code == 200, r.text
    print("[OK] GET /")
    steps += 1

    sav = _find_sav()
    with sav.open("rb") as f:
        r = client.post(
            "/read-file",
            files={"file": (sav.name, f, "application/octet-stream")},
        )
    assert r.status_code == 200, r.text[:400]
    payload = r.json()
    rows = payload["data"]
    labels = payload.get("labels") or {}
    print(f"[OK] POST /read-file ({sav.name}): {len(rows)} satir")
    steps += 1

    cols = list(rows[0].keys())
    grouping = [c for c in ("bolum", "dbf_cinsiyet", "dbf_gd") if c in cols]
    outcome = [c for c in cols if "TOPLAM" in c.upper()][:3]
    variables = normalize_variable_labels([
        Variable(name=c, label=labels.get(c, c), type="categorical", role="grouping")
        for c in grouping
    ] + [
        Variable(name=c, label=labels.get(c, c), type="continuous", role="outcome")
        for c in outcome
    ])
    sample = rows[:80]
    data = [DataRow(values=r) for r in sample]

    r = client.post(
        "/plan-tests",
        json=PlanTestsRequest(
            variables=variables,
            data=data,
            research_aim="Online yemek siparisi, gece yeme ve beslenme tutumu",
            use_ai=True,
            missing_codes=["99"],
        ).model_dump(),
    )
    assert r.status_code == 200, r.text[:600]
    plan = r.json()
    meta = plan.get("meta") or {}
    catalog = plan.get("catalog") or []
    rec = [c for c in catalog if c.get("enabled_default")]
    print(
        f"[OK] POST /plan-tests: {len(rec)} onerilen, "
        f"llm_calls={meta.get('llm_calls')}, uygun={meta.get('uygun_count')}"
    )
    steps += 1

    enabled = [t["id"] for t in rec]
    r = client.post(
        "/analyze",
        json=AnalysisRequest(
            variables=variables,
            data=data,
            enabled_tests=enabled,
            missing_codes=["99"],
        ).model_dump(),
    )
    assert r.status_code == 200, r.text[:600]
    results = r.json().get("results") or []
    print(f"[OK] POST /analyze: {len(results)} tablo")
    steps += 1

    r = client.post(
        "/layout-results",
        json={"results": results},
    )
    assert r.status_code == 200, r.text[:400]
    laid = r.json().get("results") or []
    print(f"[OK] POST /layout-results: {len(laid)} tablo")
    steps += 1

    print(f"\nAPI entegrasyon tamam ({steps} adim).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
