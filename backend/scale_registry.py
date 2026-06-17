"""Ölçek veritabanı — prefix ve madde metni eşleştirmesi."""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).resolve().parent / "scale_registry.json"
_REGISTRY_CACHE: Optional[List[dict]] = None

_CONF_RANK = {"high": 2, "medium": 1, "low": 0}
_DERIVED_SUFFIX = re.compile(
    r"_(toplam|total|puan|score|sum|risk|binary|grubu?|kategori|category|mean|ort|avg)$",
    re.I,
)
_REVERSED_RE = re.compile(
    r"(_ters|_t|_rev|_reversed|_rc|_inv)$",
    re.I,
)


def _prefer_reversed(cols: List[str]) -> List[str]:
    """neq_1 ve neq_1_ters ikisi varsa neq_1_ters'i kullan, neq_1'i at."""
    reversed_bases = {
        _REVERSED_RE.sub("", c).lower()
        for c in cols
        if _REVERSED_RE.search(c)
    }
    return [
        c for c in cols
        if _REVERSED_RE.search(c)
        or c.lower() not in reversed_bases
    ]


def normalize_col(name: str) -> str:
    """Küçük harf; nokta/boşluk/tire → alt çizgi."""
    s = (name or "").lower().strip()
    return re.sub(r"[\.\s\-]+", "_", s)


def _tokenize(text: str) -> set:
    tokens = re.findall(r"[a-zçğıöşü0-9]+", (text or "").lower())
    return {t for t in tokens if len(t) > 2}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def load_registry() -> List[dict]:
    """scale_registry.json yükle; modül önbelleği."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is not None:
        return _REGISTRY_CACHE
    try:
        if not _REGISTRY_PATH.is_file():
            logger.warning("scale_registry.json bulunamadı: %s", _REGISTRY_PATH)
            _REGISTRY_CACHE = []
            return _REGISTRY_CACHE
        with open(_REGISTRY_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        _REGISTRY_CACHE = data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("scale_registry.json okunamadı: %s", exc)
        _REGISTRY_CACHE = []
    return _REGISTRY_CACHE


def clear_registry_cache() -> None:
    """Testler için önbelleği temizle."""
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None


def get_scale_info(scale_id: str) -> Optional[dict]:
    sid = (scale_id or "").strip().lower()
    for scale in load_registry():
        if str(scale.get("id", "")).lower() == sid:
            return scale
    return None


def get_reverse_items(scale_id: str) -> Optional[List[int]]:
    """Ters madde listesi. None = bilinmiyor, [] = yok."""
    scale = get_scale_info(scale_id)
    if not scale:
        return None
    rev = scale.get("reverse_items")
    if rev is None:
        return None
    return list(rev)


def get_cutoff(scale_id: str) -> Optional[dict]:
    scale = get_scale_info(scale_id)
    if not scale:
        return None
    cutoff = scale.get("cutoff")
    return dict(cutoff) if isinstance(cutoff, dict) else None


def validate_turkish(scale_id: str) -> bool:
    scale = get_scale_info(scale_id)
    if not scale:
        return False
    return scale.get("turkish_validity") is not None


def resolve_scale_id(name: str) -> Optional[str]:
    """Ölçek adı veya kısaltmadan registry id."""
    if not name:
        return None
    cleaned = re.sub(r"\([^)]*\)", " ", name or "").strip()
    norm = normalize_col(cleaned)
    for scale in load_registry():
        if normalize_col(scale.get("id", "")) == norm:
            return scale["id"]
        for n in scale.get("names") or []:
            n_norm = normalize_col(n)
            if n_norm == norm:
                return scale["id"]
            # Substring sadece kısa kısaltmalar için (≤6 karakter)
            if len(norm) <= 6 and (norm == n_norm or norm in n_norm.split("_")):
                return scale["id"]
            # Uzun isimler için token Jaccard benzerliği
            if len(norm) > 6:
                score = _jaccard(_tokenize(norm), _tokenize(n_norm))
                if score >= 0.5:
                    return scale["id"]
    return None


def match_by_prefix(col_names: List[str]) -> List[dict]:
    """Prefix ipuçlarıyla ölçek eşleştir; çakışmada daha uzun prefix kazanır."""
    registry = load_registry()
    col_owner: Dict[str, Tuple[dict, int]] = {}

    for col in col_names:
        if _DERIVED_SUFFIX.search(col):
            continue
        norm = normalize_col(col)
        best_scale: Optional[dict] = None
        best_len = -1
        for scale in registry:
            for hint in scale.get("prefix_hints") or []:
                hint_norm = normalize_col(hint)
                if norm.startswith(hint_norm) and len(hint_norm) > best_len:
                    best_scale = scale
                    best_len = len(hint_norm)
        if best_scale is not None:
            col_owner[col] = (best_scale, best_len)

    grouped: Dict[str, List[str]] = defaultdict(list)
    scale_by_id: Dict[str, dict] = {}
    for col, (scale, _) in col_owner.items():
        sid = scale["id"]
        grouped[sid].append(col)
        scale_by_id[sid] = scale

    return [
        {
            "scale": scale_by_id[sid],
            "matched_cols": sorted(_prefer_reversed(grouped[sid])),
            "confidence": "high",
        }
        for sid in grouped
    ]


def match_by_item_text(
    col_labels: Dict[str, str],
    top_n: int = 3,
) -> List[dict]:
    """Madde etiket metinleriyle Jaccard benzerliği."""
    registry = load_registry()
    if not col_labels:
        return []

    col_best: Dict[str, Tuple[dict, float, str]] = {}

    for col, label in col_labels.items():
        if not (label or "").strip():
            continue
        label_tokens = _tokenize(label)
        for scale in registry:
            samples = (scale.get("item_sample") or [])[:top_n]
            if not samples:
                continue
            best_sim = 0.0
            for sample in samples:
                best_sim = max(best_sim, _jaccard(label_tokens, _tokenize(sample)))
            if best_sim < 0.25:
                continue
            prev = col_best.get(col)
            if prev is None or best_sim > prev[1]:
                col_best[col] = (scale, best_sim, label)

    scale_cols: Dict[str, List[str]] = defaultdict(list)
    scale_sim: Dict[str, float] = {}
    scale_obj: Dict[str, dict] = {}
    for col, (scale, sim, _) in col_best.items():
        sid = scale["id"]
        scale_cols[sid].append(col)
        scale_sim[sid] = max(scale_sim.get(sid, 0.0), sim)
        scale_obj[sid] = scale

    out: List[dict] = []
    for sid, cols in scale_cols.items():
        sim = scale_sim[sid]
        out.append({
            "scale": scale_obj[sid],
            "matched_cols": sorted(cols),
            "confidence": "high" if sim >= 0.50 else "medium",
            "similarity": round(sim, 4),
        })
    return out


def _merge_matches(matches: List[dict]) -> List[dict]:
    by_id: Dict[str, dict] = {}
    for m in matches:
        scale = m["scale"]
        sid = scale["id"]
        if sid not in by_id:
            by_id[sid] = {
                "scale": scale,
                "matched_cols": list(m.get("matched_cols") or []),
                "confidence": m.get("confidence", "medium"),
                "similarity": m.get("similarity"),
            }
            continue
        existing = by_id[sid]
        existing["matched_cols"] = sorted(
            set(existing["matched_cols"]) | set(m.get("matched_cols") or [])
        )
        if _CONF_RANK.get(m.get("confidence"), 0) > _CONF_RANK.get(existing["confidence"], 0):
            existing["confidence"] = m["confidence"]
        new_sim = m.get("similarity")
        if new_sim is not None and (existing.get("similarity") or 0) < new_sim:
            existing["similarity"] = new_sim
    return list(by_id.values())


def match_scale(
    col_names: List[str],
    col_labels: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """Önce prefix, kalan sütunlar için madde metni; birleştir."""
    prefix_matches = match_by_prefix(col_names)
    prefix_cols = {c for m in prefix_matches for c in m["matched_cols"]}

    text_matches: List[dict] = []
    if col_labels:
        remaining = {
            k: v for k, v in col_labels.items()
            if k in col_names and k not in prefix_cols
        }
        if remaining:
            text_matches = match_by_item_text(remaining)

    return _merge_matches(prefix_matches + text_matches)


def compact_registry_hints(
    matches: List[dict],
    max_items: int = 10,
    max_chars: int = 80,
) -> List[dict]:
    """Gemini prompt için kısa registry ipuçları."""
    hints: List[dict] = []
    for m in matches:
        if m.get("confidence") != "high":
            continue
        scale = m["scale"]
        entry = {
            "id": scale.get("id"),
            "name": (scale.get("names") or [scale.get("id", "")])[0],
            "cols": (m.get("matched_cols") or [])[:12],
        }
        while len(json.dumps(entry, ensure_ascii=False)) > max_chars and entry["cols"]:
            entry["cols"] = entry["cols"][:-1]
        hints.append(entry)
        if len(hints) >= max_items:
            break
    return hints
