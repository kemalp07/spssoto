"""Cronbach batch — orijinal madde tercihi, çift ters önleme, eksik kod 99."""
import asyncio
import re
import sys
from pathlib import Path

import pandas as pd
import pyreadstat
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from data_cleaning import (  # noqa: E402
    apply_scale_item_resolution,
    build_cronbach_dataframe,
    extract_item_number,
    has_item_deriv_affix,
    prefer_original_items,
)
from main import analyze_cronbach_batch  # noqa: E402
from scale_registry import get_reverse_items, get_scale_info, match_scale  # noqa: E402
from schemas import CronbachBatchRequest, DataRow  # noqa: E402

FIXTURE_NAMES = ("kemal.büsra.sav", "anket.sav", "data.sav")


def _find_sav() -> Path:
    fixture_dir = ROOT / "testdata"
    for name in FIXTURE_NAMES:
        path = fixture_dir / name
        if path.is_file():
            return path
    matches = list(fixture_dir.glob("*.sav"))
    if len(matches) == 1:
        return matches[0]
    pytest.skip("testdata/*.sav bulunamadı")


def _item_columns(columns: list[str]) -> list[str]:
    pattern = re.compile(
        r"^(?:recoded_|rev_|inv_)?[a-zA-Z]+_\d+"
        r"(?:_reversed|_recoded|_inverted|_ters|_rev|_rc|_inv|_t|_r)?$",
        re.I,
    )
    return [c for c in columns if pattern.match(str(c))]


def _load_rows(path: Path) -> tuple[pd.DataFrame, list[DataRow]]:
    df, _ = pyreadstat.read_sav(str(path), user_missing=True)
    rows = [
        DataRow(values={k: (None if pd.isna(v) else v) for k, v in record.items()})
        for record in df.to_dict(orient="records")
    ]
    return df, rows


def _scale_payload(df: pd.DataFrame, scale_id: str) -> dict:
    match = next(
        m for m in match_scale(_item_columns(list(df.columns)), {})
        if m["scale"]["id"] == scale_id
    )
    resolved = apply_scale_item_resolution(match["matched_cols"])
    info = get_scale_info(scale_id) or {}
    return {
        "name": (info.get("names") or [scale_id])[0],
        "cronbach_items": resolved["cronbach_items"],
        "reverse_items": get_reverse_items(scale_id),
        "scale_range": info.get("scale_range") or [0, 4],
    }


def test_apply_scale_item_resolution_prefers_originals():
    resolved = apply_scale_item_resolution(["neq_1", "neq_1_ters", "neq_2"])
    assert "neq_1_ters" not in resolved["cronbach_items"]
    assert "neq_1" in resolved["cronbach_items"]


@pytest.mark.parametrize("scale_id", ["neq", "ashn"])
def test_cronbach_matrix_avoids_double_reverse(scale_id):
    """Ters maddede _ters varsa yalnızca türev kullanılır; orijinale formül uygulanmaz."""
    sav = _find_sav()
    df, _ = _load_rows(sav)
    payload = _scale_payload(df, scale_id)
    matrix, valid = build_cronbach_dataframe(
        df,
        payload["cronbach_items"],
        reverse_items=payload["reverse_items"],
        scale_range=payload["scale_range"],
        missing_codes=["99"],
    )
    assert len(matrix) >= 3
    rev = set(payload["reverse_items"])
    for col in valid:
        if not has_item_deriv_affix(col):
            continue
        num_match = re.search(r"_(\d+)", col)
        if num_match and int(num_match.group(1)) in rev:
            orig = col.lower().replace("_ters", "").replace("_t", "")
            assert not any(
                c.lower().startswith(orig.split("_")[0])
                and not has_item_deriv_affix(c)
                and extract_item_number(c) == int(num_match.group(1))
                for c in valid
            ), f"{scale_id}: hem orijinal hem türev: {valid}"


@pytest.mark.parametrize("scale_id,min_alpha", [
    ("neq", 0.65),
    ("ashn", 0.50),
    ("oysto", 0.75),
])
def test_cronbach_alpha_not_collapsed_by_double_reverse(scale_id, min_alpha):
    sav = _find_sav()
    df, rows = _load_rows(sav)
    payload = _scale_payload(df, scale_id)
    req = CronbachBatchRequest(
        scales=[payload],
        data=rows,
        missing_codes=["99"],
    )
    resp = asyncio.run(analyze_cronbach_batch(req))
    assert resp["results"], f"{scale_id} cronbach sonucu yok"

    table_rows = resp["results"][0]["rows"]
    ref_name = (get_scale_info(scale_id) or {}).get("names", [scale_id])[0]
    match_row = next(
        (
            r for r in table_rows
            if ref_name.split()[0] in str(r[0])
            or scale_id.upper() in str(r[0]).upper()
        ),
        table_rows[0],
    )
    alpha = float(str(match_row[3]).replace(",", "."))
    assert alpha >= min_alpha, f"{scale_id}: α={alpha:.3f} çift ters şüphesi"


def test_reverse_formula_uses_min_plus_max():
    raw = pd.DataFrame({
        "it_1": [1, 2, 3, 4, 5],
        "it_2": [5, 4, 3, 2, 1],
        "it_3": [1, 1, 2, 2, 3],
    })
    matrix, _ = build_cronbach_dataframe(
        raw,
        ["it_1", "it_2", "it_3"],
        reverse_items=[2],
        scale_range=[1, 5],
    )
    assert matrix["it_2"].tolist() == [1, 2, 3, 4, 5]
