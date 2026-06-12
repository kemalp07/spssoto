"""Yüklenen belge bağlamı — session ve LLM compact yardımcıları."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

_store: Dict[str, dict] = {}


def save_document_context(ctx: dict, session_id: Optional[str] = None) -> str:
    sid = (session_id or "").strip() or str(uuid.uuid4())
    _store[sid] = ctx
    return sid


def get_document_context(session_id: Optional[str]) -> Optional[dict]:
    if not session_id:
        return None
    return _store.get(session_id.strip())


def resolve_document_context(
    inline: Optional[dict] = None,
    session_id: Optional[str] = None,
) -> Optional[dict]:
    stored = get_document_context(session_id)
    if inline and stored:
        return {
            "anket": inline.get("anket") or stored.get("anket"),
            "etik_kurul": inline.get("etik_kurul") or stored.get("etik_kurul"),
        }
    return inline or stored


def effective_research_text(
    document_context: Optional[dict],
    research_topic: str = "",
) -> str:
    """Etik kurul amacı + hipotezler varsa araştırma metni yerine kullan."""
    etik = (document_context or {}).get("etik_kurul") or {}
    if etik.get("parse_error"):
        return (research_topic or "").strip()

    parts: List[str] = []
    aim = (etik.get("aim") or "").strip()
    if aim:
        parts.append(aim)
    for h in etik.get("hypotheses") or []:
        h = str(h).strip()
        if h:
            parts.append(h)
    if parts:
        return "\n".join(parts)[:2000]
    return (research_topic or "").strip()


def anket_section_hints(document_context: Optional[dict]) -> List[str]:
    anket = (document_context or {}).get("anket") or {}
    if anket.get("parse_error"):
        return []
    titles: List[str] = []
    for sec in anket.get("sections") or []:
        title = (sec.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
    return titles


def compact_document_context_for_gemini(document_context: Optional[dict]) -> str:
    """Gemini veri analisti girdisine eklenecek kısa özet."""
    if not document_context:
        return ""

    lines: List[str] = []
    anket = document_context.get("anket") or {}
    if not anket.get("parse_error"):
        for sec in (anket.get("sections") or [])[:8]:
            title = sec.get("title")
            if title:
                lines.append(f"Anket bölümü: {title} ({sec.get('scale_type', 'other')})")
            for item in (sec.get("items") or [])[:5]:
                text = str(item.get("text") or "")[:200]
                rev = " [ters]" if item.get("reverse_hint") else ""
                lines.append(f"  Madde {item.get('no')}: {text}{rev}")

    etik = document_context.get("etik_kurul") or {}
    if not etik.get("parse_error"):
        if etik.get("aim"):
            lines.append(f"Etik kurul amacı: {str(etik['aim'])[:400]}")
        for h in (etik.get("hypotheses") or [])[:8]:
            lines.append(f"Etik kurul hipotezi: {str(h)[:200]}")
        if etik.get("scale_names"):
            lines.append(
                "Etik kurul ölçek adları: "
                + ", ".join(str(s) for s in etik["scale_names"][:10])
            )

    return "\n".join(lines)[:3500]
