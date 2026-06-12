"""Word (.docx) belge ayrıştırıcı — anket formu ve etik kurul raporu."""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple

from docx import Document

_ITEM_RE = re.compile(
    r"^\s*(?:"
    r"(?P<num>\d+)\s*[.)]\s*|"
    r"(?:madde|soru)\s*(?P<num_m>\d+)\s*[.:)]?\s*|"
    r"(?P<letter>[a-zA-Z])\s*[.)]\s*"
    r")(?P<text>.+)$",
    re.IGNORECASE,
)
_REVERSE_HINT = re.compile(r"\(R\)|\(T\)|\bters\b", re.IGNORECASE)
_SECTION_HEADER = re.compile(
    r"^(?:bölüm|section|ölçek|anket|form)\s*[\d.:)\-]*\s*(.+)$",
    re.IGNORECASE,
)
_LIKERT_LINE = re.compile(
    r"(hiç\s+katılmıyorum|katılmıyorum|kararsız|katılıyorum|tamamen\s+katılıyorum)",
    re.IGNORECASE,
)
_AIM_HEADER = re.compile(
    r"^\s*(?:araştırmanın\s+)?(?:amaç|amacı|purpose|hedef)(?:\s*[:.)])?\s*(.*)$",
    re.IGNORECASE,
)
_HYPOTHESIS_RE = re.compile(
    r"^\s*(H\d+)\s*[:.)]\s*(.+)$",
    re.IGNORECASE,
)
_HYPOTHESIS_INLINE = re.compile(
    r"\b(hipotez|araştırma\s+sorusu)\s*[:.)]?\s*(.+)$",
    re.IGNORECASE,
)
_SAMPLE_N = re.compile(
    r"(\d{2,5})\s*(?:katılımcı|öğrenci|kişi|denek|gönüllü)",
    re.IGNORECASE,
)
_QUOTED_NAME = re.compile(r'"([^"]{3,80})"|\'([^\']{3,80})\'')
_CAPS_NAME = re.compile(r"\b([A-ZÇĞİÖŞÜ]{3,20})\b")
_DATE_RE = re.compile(
    r"\b(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2})\b",
)
_INSTITUTION_KW = re.compile(
    r"(üniversite|fakülte|enstitü|yüksekokul|myo|hastane|kurum)",
    re.IGNORECASE,
)


def _docx_paragraphs(file_bytes: bytes) -> List[str]:
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception:
        return []
    lines: List[str] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if text:
            lines.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [((c.text or "").strip()) for c in row.cells]
            row_text = " | ".join(c for c in cells if c)
            if row_text:
                lines.append(row_text)
    return lines


def _parse_item_line(line: str) -> Optional[Tuple[int, str, bool]]:
    m = _ITEM_RE.match(line.strip())
    if not m:
        return None
    num_raw = m.group("num") or m.group("num_m") or m.group("letter")
    try:
        no = int(num_raw) if num_raw and num_raw.isdigit() else ord(num_raw.upper()) - 64
    except (TypeError, ValueError):
        no = 0
    text = (m.group("text") or "").strip()
    if not text:
        return None
    reverse = bool(_REVERSE_HINT.search(text))
    text = _REVERSE_HINT.sub("", text).strip(" -–—")
    return no, text, reverse


def _detect_likert_scale(block_text: str) -> str:
    lower = block_text.lower()
    hits = len(_LIKERT_LINE.findall(lower))
    if hits >= 3:
        if re.search(r"\b7\b|yedi\s*li|7\s*li", lower):
            return "likert_7"
        return "likert_5"
    if re.search(r"strongly\s+disagree|never\s+.*\s+always", lower):
        return "other"
    return "other"


def _is_section_header(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 120:
        return False
    if _ITEM_RE.match(s):
        return False
    if s.endswith(":"):
        return True
    if _SECTION_HEADER.match(s):
        return True
    if s.isupper() and len(s.split()) <= 8:
        return True
    return False


def parse_anket_docx(file_bytes: bytes) -> dict:
    """Anket formu .docx → bölümler, maddeler, ölçek tipi ipuçları."""
    try:
        lines = _docx_paragraphs(file_bytes)
        if not lines:
            return {"parse_error": True, "sections": []}

        sections: List[dict] = []
        current: Optional[dict] = None
        block_lines: List[str] = []

        def flush_section() -> None:
            nonlocal current, block_lines
            if current is None:
                return
            current["scale_type"] = _detect_likert_scale("\n".join(block_lines))
            sections.append(current)
            current = None
            block_lines = []

        for line in lines:
            if _is_section_header(line):
                flush_section()
                title = line.rstrip(":").strip()
                m = _SECTION_HEADER.match(title)
                if m and m.group(1):
                    title = m.group(1).strip()
                current = {"title": title, "items": [], "scale_type": "other"}
                block_lines = [line]
                continue

            item = _parse_item_line(line)
            if item:
                if current is None:
                    current = {"title": "Genel", "items": [], "scale_type": "other"}
                no, text, reverse = item
                current["items"].append({
                    "no": no,
                    "text": text,
                    "reverse_hint": reverse,
                })
                block_lines.append(line)
                continue

            if current is not None:
                block_lines.append(line)

        flush_section()

        if not sections:
            return {"parse_error": True, "sections": []}
        return {"sections": sections}
    except Exception:
        return {"parse_error": True, "sections": []}


def _extract_aim(lines: List[str]) -> Optional[str]:
    for i, line in enumerate(lines):
        m = _AIM_HEADER.match(line)
        if m:
            inline = (m.group(1) or "").strip()
            if inline:
                return inline[:2000]
            parts = []
            for follow in lines[i + 1: i + 6]:
                if _HYPOTHESIS_RE.match(follow) or _is_section_header(follow):
                    break
                if follow.strip():
                    parts.append(follow.strip())
            if parts:
                return " ".join(parts)[:2000]
    for line in lines:
        lower = line.lower()
        if "amaç" in lower or "purpose" in lower:
            return line[:2000]
    return None


def _extract_hypotheses(lines: List[str]) -> List[str]:
    found: List[str] = []
    seen = set()
    for line in lines:
        m = _HYPOTHESIS_RE.match(line.strip())
        if m:
            text = m.group(2).strip()
            if text and text not in seen:
                seen.add(text)
                found.append(text)
            continue
        m2 = _HYPOTHESIS_INLINE.search(line)
        if m2:
            text = m2.group(2).strip()
            if text and text not in seen:
                seen.add(text)
                found.append(text)
    return found


def _extract_sample_n(text: str) -> Optional[int]:
    m = _SAMPLE_N.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_scale_names(lines: List[str]) -> List[str]:
    names: List[str] = []
    seen = set()
    blob = "\n".join(lines)
    for m in _QUOTED_NAME.finditer(blob):
        for g in m.groups():
            if g and g not in seen:
                seen.add(g)
                names.append(g.strip())
    for line in lines:
        for m in _CAPS_NAME.finditer(line):
            token = m.group(1)
            if token not in seen and len(token) >= 3:
                seen.add(token)
                names.append(token)
    return names[:20]


def _extract_institution(lines: List[str]) -> str:
    for line in lines:
        if _INSTITUTION_KW.search(line):
            return line.strip()[:300]
    return ""


def _extract_date(text: str) -> str:
    m = _DATE_RE.search(text)
    return m.group(1) if m else ""


def parse_etik_kurul_docx(file_bytes: bytes) -> dict:
    """Etik kurul raporu .docx → amaç, hipotezler, örneklem vb."""
    try:
        lines = _docx_paragraphs(file_bytes)
        if not lines:
            return {"parse_error": True}

        blob = "\n".join(lines)
        aim = _extract_aim(lines)
        hypotheses = _extract_hypotheses(lines)
        n_val = _extract_sample_n(blob)
        scale_names = _extract_scale_names(lines)
        institution = _extract_institution(lines)
        date = _extract_date(blob)

        if not any([aim, hypotheses, n_val, scale_names, institution, date]):
            return {"parse_error": True}

        return {
            "aim": aim,
            "hypotheses": hypotheses or None,
            "n": n_val,
            "scale_names": scale_names or None,
            "institution": institution or None,
            "date": date or None,
        }
    except Exception:
        return {"parse_error": True}
