"""Şablon tabanlı APA bulgu cümleleri — akademik rehber + yorum motoru."""
from typing import Dict, List, Optional

from bulgu_uretici import BULGU_BUILDERS, build_bulgu_text
from yorum_motoru import finalize_bulgu, p_txt, highest_group_name, compact_result_summary as _compact_result_summary

# Geriye dönük uyumluluk (testler, jüri)
_p_txt = p_txt
_higher_group_name = highest_group_name


def has_bulgu_template(result: dict) -> bool:
    return result.get("type") in BULGU_BUILDERS


def generate_bulgu_from_template(
    result: dict,
    label_map: Optional[Dict[str, str]] = None,
    all_results: Optional[List[dict]] = None,
) -> Optional[str]:
    text = build_bulgu_text(result, all_results)
    if not text:
        return None
    finalized, _issues = finalize_bulgu(result, text, label_map, all_results)
    return finalized


def compact_result_summary(result: dict, all_results: Optional[List[dict]] = None) -> dict:
    return _compact_result_summary(result, all_results=all_results)
