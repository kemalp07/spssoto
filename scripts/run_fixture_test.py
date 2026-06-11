#!/usr/bin/env python3
"""testdata/ içindeki anket.sav (+ isteğe bağlı anket.docx) ile uçtan uca test.

Kullanım (proje kökünden):
    python scripts/run_fixture_test.py
    python scripts/run_fixture_test.py --no-ai
    python scripts/run_fixture_test.py --full
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FIXTURE_DIR = ROOT / "testdata"
sys.path.insert(0, str(BACKEND))

from data_cleaning import prepare_analysis_df  # noqa: E402
from file_io import read_uploaded_file  # noqa: E402
from llm_router import has_claude  # noqa: E402
from main import detect_item_columns  # noqa: E402
from schemas import DetectScalesRequest, Variable  # noqa: E402
from test_planner import plan_tests  # noqa: E402
from stat_tests import run_analyze  # noqa: E402

EXCLUDE_PATTERNS = [
    re.compile(r"^(anket_no|id|no|sira|num|serial)$", re.I),
    re.compile(r"^[a-z]+_\d+(_ters)?$", re.I),
    re.compile(r"^[A-Z]+_\d+(_T)?$"),
    re.compile(r"_\d+$"),
    re.compile(r"^LG10", re.I),
    re.compile(r"^LOG", re.I),
    re.compile(r"^SQRT", re.I),
    re.compile(r"^ln", re.I),
]
GROUPING_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"cinsiyet", r"gender", r"sex\b", r"bolum", r"department", r"faculty",
        r"fakulte", r"medeni", r"marital", r"egitim", r"education", r"gelir",
        r"income", r"meslek", r"occupation", r"job\b", r"sigara", r"tobacco",
        r"smoking", r"alkol", r"alcohol", r"ilac", r"medication", r"kronik",
        r"chronic", r"bölge", r"bolge", r"region", r"okul", r"school",
        r"sinif\b", r"class\b",
    )
]
OUTCOME_CAT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"kategori", r"category", r"_grup(u)?$", r"_group$", r"_binary$",
        r"_sinif$", r"_class$", r"_risk$", r"_durum$", r"_status$",
        r"_level$", r"_seviye$",
    )
]
OUTCOME_CONT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"_toplam$", r"_total$", r"_sum$", r"_puan$", r"_score$", r"_skor$",
        r"_ortalama$", r"_mean$", r"_avg$", r"_endeks$", r"_index$",
    )
]
FORCE_OUTCOME_SUFFIXES = [
    re.compile(p, re.I)
    for p in (
        r"_toplam$", r"_total$", r"_score$", r"_puan$", r"_skor$", r"_sum$",
        r"_mean$", r"_avg$", r"_ortalama$", r"_grubu?$", r"_group$",
        r"_binary$", r"_kategori$", r"_category$", r"_sinif$", r"_level$",
        r"_seviye$", r"_risk$", r"_durum$",
    )
]


def _find_fixture(names: List[str], ext: str) -> Optional[Path]:
    for name in names:
        p = FIXTURE_DIR / name
        if p.is_file():
            return p
    matches = sorted(FIXTURE_DIR.glob(f"*{ext}"))
    return matches[0] if len(matches) == 1 else None


def _matches(patterns: List[re.Pattern], col: str) -> bool:
    return any(p.search(col) for p in patterns)


def classify_columns_rule(
    cols: List[str],
    data: List[dict],
    labels: Dict[str, str],
) -> Tuple[List[str], List[str], List[str]]:
    grouping: List[str] = []
    outcome: List[str] = []
    exclude: List[str] = []

    for col in cols:
        if _matches(EXCLUDE_PATTERNS, col):
            exclude.append(col)
            continue
        if _matches(GROUPING_PATTERNS, col):
            grouping.append(col)
            continue
        if _matches(OUTCOME_CAT_PATTERNS, col):
            outcome.append(col)
            continue
        if _matches(OUTCOME_CONT_PATTERNS, col):
            outcome.append(col)
            continue
        vals = list({
            r[col] for r in data[:50]
            if r.get(col) not in ("", None)
        })
        numeric = [
            v for v in vals
            if str(v).replace(",", ".").replace("-", "").replace(".", "").isdigit()
        ]
        if vals and len(numeric) / len(vals) > 0.8 and len(vals) > 8:
            outcome.append(col)
        else:
            grouping.append(col)

    for col in grouping + outcome:
        label = labels.get(col, col)
        if _matches(FORCE_OUTCOME_SUFFIXES, col):
            if col in grouping:
                grouping.remove(col)
            if col not in outcome:
                outcome.append(col)

    return grouping, outcome, exclude


def build_variables(
    grouping_cols: List[str],
    outcome_cols: List[str],
    labels: Dict[str, str],
    value_labels: Dict[str, Any],
) -> List[Variable]:
    variables: List[Variable] = []
    for col in grouping_cols:
        variables.append(Variable(
            name=col,
            label=labels.get(col, col),
            type="categorical",
            role="grouping",
            included=True,
            value_labels=value_labels.get(col),
        ))
    for col in outcome_cols:
        variables.append(Variable(
            name=col,
            label=labels.get(col, col),
            type="continuous" if _matches(OUTCOME_CONT_PATTERNS, col) else "categorical",
            role="outcome",
            included=True,
            value_labels=value_labels.get(col),
        ))
    return variables


def _print_plan_summary(title: str, catalog: List[dict], meta: dict) -> None:
    kesin = [c for c in catalog if c.get("tier") == "kesin_onerilen"]
    onerilen = [c for c in catalog if c.get("tier") == "onerilen"]
    opt = [c for c in catalog if c.get("tier") == "onerilmeyen"]
    print(f"\n{'=' * 60}")
    print(title)
    print(f"{'=' * 60}")
    print(
        f"  Ham aday: {meta.get('total_candidates', '?')} | "
        f"Uygun: {meta.get('uygun_count', '?')} | "
        f"Katalog: {meta.get('catalog_count', '?')} | "
        f"Kesin: {len(kesin)} | Önerilen: {len(onerilen)} | Önerilmeyen: {len(opt)} | "
        f"Gizli (kural dışı): {meta.get('rule_excluded_count', '?')}"
    )
    if meta.get("ai_used"):
        print(
            f"  Claude: {meta.get('llm_calls', 0)} çağrı | "
            f"~{meta.get('approx_input_tokens', 0)} token"
        )
    print("\n  Kesin önerilen:")
    for i, t in enumerate(kesin, 1):
        print(f"    {i:2}. {t.get('label', t.get('id'))}")
    if onerilen:
        print(f"\n  Önerilen ({len(onerilen)}):")
        for i, t in enumerate(onerilen, 1):
            print(f"    {i:2}. {t.get('label', t.get('id'))}")
    if opt:
        print(f"\n  Önerilmeyen ({len(opt)}) — ilk 5:")
        for t in opt[:5]:
            print(f"    · {t.get('label', t.get('id'))}")
        if len(opt) > 5:
            print(f"    … +{len(opt) - 5} daha")


async def run_plan(
    df: pd.DataFrame,
    variables: List[Variable],
    research_aim: str,
    missing_codes: List[str],
    use_ai: bool,
) -> Tuple[List[dict], List[dict], List[dict], dict]:
    return await plan_tests(df, variables, research_aim, use_ai=use_ai)


def load_ethics_topic(docx_path: Path) -> Tuple[str, List[dict], bool]:
    from ai_services import run_import_ethics_report

    try:
        data = run_import_ethics_report(
            docx_path.read_bytes(),
            docx_path.name.lower(),
            None,
        )
    except Exception as exc:
        print(f"  [UYARI] anket.docx okunamadi: {exc}")
        return "", [], False
    topic = (data.get("research_topic") or "").strip()
    scales = data.get("scales") or []
    print(f"  [OK] anket.docx: {len(scales)} olcek, konu: {topic[:80] or '(bos)'}...")
    return topic, scales, True


async def main_async(args: argparse.Namespace) -> int:
    sav_path = _find_fixture(["anket.sav", "data.sav"], ".sav")
    docx_path = _find_fixture(["anket.docx", "ethics.docx"], ".docx")

    if not sav_path:
        print("[HATA] testdata/ icinde .sav dosyasi bulunamadi.")
        print(f"   Klasör: {FIXTURE_DIR}")
        print("   anket.sav dosyanızı buraya koyun, sonra tekrar çalıştırın.")
        print("   Detay: testdata/README.md")
        return 1

    print(f"[SAV] {sav_path.name}")
    raw = read_uploaded_file(sav_path.name, sav_path.read_bytes())
    records: List[dict] = raw["data"]
    labels: Dict[str, str] = raw.get("labels") or {}
    value_labels: Dict[str, Any] = raw.get("value_labels") or {}
    missing_codes: List[str] = []
    if raw.get("global_missing_code"):
        missing_codes.append(str(raw["global_missing_code"]))
    for codes in (raw.get("missing_codes") or {}).values():
        missing_codes.extend(str(c) for c in codes)
    missing_codes = list(dict.fromkeys(missing_codes)) or ["99"]

    print(f"  {len(records)} satır, {len(records[0]) if records else 0} sütun")

    research_aim = args.topic or ""
    if docx_path and not args.skip_docx:
        print(f"[DOCX] {docx_path.name}")
        if args.no_ai:
            print("  [--no-ai] docx atlandi (Claude gerekir)")
        else:
            topic, _scales, ok = load_ethics_topic(docx_path)
            if ok and topic:
                research_aim = topic
    elif not docx_path:
        print("[DOCX] yok (istege bagli: testdata/anket.docx)")

    if not research_aim:
        research_aim = (
            "Üniversite öğrencilerinde beslenme tutumu, gece yeme ve obezite "
            "riski arasındaki ilişkilerin incelenmesi"
        )
        print("[KONU] Varsayilan arastirma amaci kullaniliyor")

    columns = list(records[0].keys())
    samples = {
        col: list({
            r[col] for r in records[:5]
            if r.get(col) not in ("", None)
        })[:4]
        for col in columns
    }
    item_resp = detect_item_columns(DetectScalesRequest(
        columns=columns,
        samples=samples,
        variable_measure=raw.get("variable_measure"),
    ))
    item_cols = set(item_resp.get("item_columns") or [])
    non_item = [
        c for c in columns
        if c not in item_cols and not _matches(EXCLUDE_PATTERNS, c)
    ]
    for col in non_item:
        if col not in labels:
            labels[col] = col

    grouping, outcome, excluded = classify_columns_rule(non_item, records, labels)
    print(
        f"[SINIF] {len(grouping)} gruplandirici, "
        f"{len(outcome)} sonuç, {len(excluded)} madde/hariç"
    )
    print(f"   Gruplandırıcı: {', '.join(grouping[:8])}{'…' if len(grouping) > 8 else ''}")

    variables = build_variables(grouping, outcome, labels, value_labels)
    df = pd.DataFrame(records)
    df = prepare_analysis_df(df, variables, missing_codes)

    use_ai = not args.no_ai and has_claude()
    if args.no_ai:
        print("\n[--no-ai] Claude devre disi")
    elif not has_claude():
        print("\n[UYARI] ANTHROPIC_API_KEY yok — yalnizca kural cekirdegi")

    _rec, _exc, catalog_rules, meta_rules = await run_plan(
        df, variables, research_aim, missing_codes, use_ai=False,
    )
    _print_plan_summary("PLAN (kural çekirdeği, AI yok)", catalog_rules, meta_rules)

    if use_ai:
        _rec, _exc, catalog_ai, meta_ai = await run_plan(
            df, variables, research_aim, missing_codes, use_ai=True,
        )
        _print_plan_summary("PLAN (Claude önerisi)", catalog_ai, meta_ai)
        catalog_final = catalog_ai
        meta_final = meta_ai
    else:
        catalog_final = catalog_rules
        meta_final = meta_rules

    default_count = sum(1 for c in catalog_final if c.get("enabled_default"))
    kesin_n = sum(1 for c in catalog_final if c.get("tier") == "kesin_onerilen")
    print(f"\n[OK] Varsayilan secili: {default_count} (kesin: {kesin_n}, katalog: {len(catalog_final)})")

    if args.full:
        enabled = [c["id"] for c in catalog_final if c.get("enabled_default")]
        print(f"\n[ANALIZ] Calistiriliyor ({len(enabled)} test)...")
        results, meta = run_analyze(df, variables, None, enabled, None, missing_codes)
        print(f"  {len(results)} tablo üretildi")
        by_type: Dict[str, int] = {}
        for r in results:
            by_type[r.get("type", "?")] = by_type.get(r.get("type", "?"), 0) + 1
        print(f"  Türler: {dict(sorted(by_type.items()))}")

    print("\nBitti.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="testdata fixture ile uçtan uca test")
    parser.add_argument("--no-ai", action="store_true", help="Claude/docx atla")
    parser.add_argument("--skip-docx", action="store_true", help="anket.docx yükleme")
    parser.add_argument("--full", action="store_true", help="Önerilen testlerle analiz de çalıştır")
    parser.add_argument("--topic", default="", help="Araştırma amacı (docx yoksa)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
