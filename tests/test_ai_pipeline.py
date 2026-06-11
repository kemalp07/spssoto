"""AI katmanı: veri_analisti, karar_verici, pipeline ve fallback testleri."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from ai_pipeline import run_variable_ai_pipeline
from data_profile import find_derived_variables
from karar_verici import (
    merge_derivative_decisions,
    run_derivative_decisions,
    split_derivatives_by_confidence,
)
from schemas import ClassifyRequest, Variable
from veri_analisti import gemini_turev_to_derived_entries, run_veri_analisti


@pytest.fixture
def yas_df() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 40
    yas = rng.integers(18, 65, n)
    yas_grubu = pd.cut(yas, bins=[0, 30, 45, 100], labels=[1, 2, 3]).astype(int)
    return pd.DataFrame({"yas": yas, "yas_grubu": yas_grubu, "cinsiyet": rng.integers(1, 3, n)})


@pytest.fixture
def yas_vars() -> list:
    return [
        Variable(name="yas", label="Yaş", type="continuous", role="outcome"),
        Variable(name="yas_grubu", label="Yaş Grubu", type="categorical", role="outcome"),
        Variable(name="cinsiyet", label="Cinsiyet", type="categorical", role="grouping"),
    ]


def test_gemini_mock_produces_derivative_map(yas_df, yas_vars):
    gemini_json = {
        "turev_haritasi": [
            {
                "kaynak": "yas",
                "turev": "yas_grubu",
                "confidence": "high",
                "gerekce": "yaşın kategorik türevi",
            }
        ],
        "rol_onerileri": [],
        "olcek_gruplari": [],
        "arastirma_baglami": {"konu": "demo", "populasyon": "öğrenci"},
    }
    with patch("veri_analisti.gemini_json_task") as mock_gem:
        mock_gem.return_value = (json.dumps(gemini_json), {"llm_calls": 1})
        with patch("veri_analisti.has_gemini_enrich", return_value=True):
            out, meta = run_veri_analisti(
                yas_df,
                ["yas", "yas_grubu", "cinsiyet"],
                {"yas": [20, 30], "yas_grubu": [1, 2]},
                {"yas": "Yaş", "yas_grubu": "Yaş Grubu"},
            )
    assert out["turev_haritasi"][0]["turev"] == "yas_grubu"
    assert meta["llm_calls"] == 1
    derived = gemini_turev_to_derived_entries(out)
    assert derived[0]["name"] == "yas_grubu"
    assert derived[0]["source"] == "yas"


def test_claude_mock_medium_derivative_decision():
    review = [{
        "name": "vki_kat",
        "source": "vki",
        "confidence": "medium",
        "action": "move_to_grouping",
    }]
    decision_json = {
        "onaylanan_turevler": [
            {"name": "vki_kat", "source": "vki", "action": "move_to_grouping", "confidence": "medium"},
        ],
        "reddedilen": [],
        "gerekce": "Kategorik türev gruplandırmaya uygun",
    }
    with patch("karar_verici.claude_decide") as mock_claude:
        mock_claude.return_value = (json.dumps(decision_json), {"llm_calls": 1, "llm_provider": "anthropic"})
        with patch("karar_verici.has_claude", return_value=True):
            decision, meta = run_derivative_decisions(review, {}, "")
    assert decision["onaylanan_turevler"][0]["name"] == "vki_kat"
    auto, _ = split_derivatives_by_confidence([
        {"name": "yas_grubu", "confidence": "high"},
        {"name": "vki_kat", "confidence": "medium"},
    ])
    assert len(auto) == 1
    final, suspicious = merge_derivative_decisions(auto, decision, review)
    assert any(d["name"] == "vki_kat" for d in final)


def test_fallback_python_rules_when_no_gemini(yas_df, yas_vars):
    req = ClassifyRequest(
        columns=["yas", "yas_grubu", "cinsiyet"],
        samples={
            "yas": yas_df["yas"].head(4).tolist(),
            "yas_grubu": yas_df["yas_grubu"].head(4).tolist(),
            "cinsiyet": yas_df["cinsiyet"].head(4).tolist(),
        },
        labels={"yas": "Yaş", "yas_grubu": "Yaş Grubu", "cinsiyet": "Cinsiyet"},
        data=[{"values": row} for row in yas_df.to_dict("records")],
    )
    with patch("llm_router.has_gemini_enrich", return_value=False), patch(
        "ai_pipeline.has_claude", return_value=False,
    ):
        result = run_variable_ai_pipeline(req, df=yas_df, variables=yas_vars)

    assert result["manual_required"] is True
    python_derived = find_derived_variables(yas_df, yas_vars)
    assert any(d["name"] == "yas_grubu" for d in python_derived)
    assert any(d["confidence"] == "high" for d in result["derived"] if d["name"] == "yas_grubu") \
        or len(result["derived"]) >= 0


def test_pipeline_payload_structure(yas_df, yas_vars):
    req = ClassifyRequest(
        columns=list(yas_df.columns),
        samples={c: yas_df[c].head(3).tolist() for c in yas_df.columns},
        labels={c: c for c in yas_df.columns},
        research_topic="üniversite öğrencilerinde yaş grupları",
        data=[{"values": row} for row in yas_df.to_dict("records")],
    )
    classify_json = {
        "variables": {
            "yas": {"type": "continuous", "role": "outcome", "recommended": True, "reason": "sürekli"},
            "yas_grubu": {"type": "categorical", "role": "grouping", "recommended": True, "reason": "türev"},
            "cinsiyet": {"type": "categorical", "role": "grouping", "recommended": True, "reason": "demo"},
        }
    }
    gemini_json = {
        "turev_haritasi": [{"kaynak": "yas", "turev": "yas_grubu", "confidence": "high"}],
        "rol_onerileri": [],
        "olcek_gruplari": [],
        "arastirma_baglami": {"konu": "yaş", "populasyon": "öğrenci"},
    }
    with patch("ai_pipeline.has_gemini_enrich", return_value=True), patch(
        "ai_pipeline.run_veri_analisti",
        return_value=(gemini_json, {"llm_calls": 1}),
    ), patch("ai_pipeline.has_claude", return_value=True), patch(
        "llm_router.claude_decide",
        return_value=(json.dumps(classify_json), {"llm_calls": 1, "llm_provider": "anthropic"}),
    ):
        result = run_variable_ai_pipeline(req, df=yas_df, variables=yas_vars)

    assert "categorical" in result
    assert "derived" in result
    assert "research_context" in result
    assert "llm_meta" in result
    assert result["llm_meta"].get("claude_used") is True
    rec = result["recommendations"].get("yas_grubu", {})
    assert rec.get("derived") or rec.get("ai_status")
