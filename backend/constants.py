"""Paylaşılan sabitler ve regex kalıpları."""
import re
from typing import Dict

DEFAULT_MISSING_CODES = {"99", "999", "998", "997", "-99", "-999"}

STAT_COL_RE = re.compile(r"χ|chi|anova|\bf\s*\(|^p$|^p\s", re.I)

LABEL_COL_RE = re.compile(r"grup|kategori|ölçek|değişken|\(i\)|\(j\)", re.I)
P_VALUE_COL_RE = re.compile(r"^p$|^p\s|sig|anlaml|asymp", re.I)

ANTHROPOMETRIC_META: Dict[str, Dict[str, str]] = {
    "kilo": {
        "label": "Vücut Ağırlığı (kg)",
        "possessive": "Vücut Ağırlıklarının",
        "inline": "vücut ağırlığı",
    },
    "boy": {
        "label": "Boy Uzunluğu (cm)",
        "possessive": "Boy Uzunluklarının",
        "inline": "boy uzunluğu",
    },
    "vki": {
        "label": "Beden Kitle İndeksi (BKİ)",
        "possessive": "Beden Kitle İndeksi (BKİ) Değerlerinin",
        "inline": "beden kitle indeksi (BKİ)",
    },
}

PRIMARY_GROUPING_KEYS = ("bolum", "cinsiyet", "yas")

DEMO_LABEL_KEYWORDS = re.compile(
    r"\b(yaş|yas|boy|kilo|ağırlık|agirlik|beden|bmi|bki|vki|"
    r"height|weight|age)\b",
    re.I,
)

SCALE_SCORE_RE = re.compile(
    r"_toplam$|_puan$|_skor$|_score$|_total$|_sum$", re.I
)

_TR_ASCII = str.maketrans({
    "ş": "s", "Ş": "s",
    "ı": "i", "İ": "i",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c",
})
_TOTAL_MARKERS = ("toplam", "total", "puan", "skor", "score")
_ITEM_COL_RE = re.compile(r"(?:^|_)\d+(?:_ters|_t)?$", re.I)

ETHICS_KEYWORDS = [
    "ölçek", "olcek", "anket", "cronbach", "alfa", "güvenilirlik",
    "geçerlilik", "gecerlilik", "madde", "alt boyut", "likert", "puan",
    "veri toplama", "ölçüm", "olcum", "kesim noktası",
    "alpha", "scale", "questionnaire", "inventory", "reliability",
    "validity", "subscale", "cutoff", "instrument",
    "neq", "oysto", "sbito", "gya", "bdi", "bai", "phq", "gad",
]
ETHICS_MAX_FILTERED_CHARS = 24000
ETHICS_FALLBACK_CHARS = 16000

ETHICS_SYSTEM_PROMPT = (
    "Sen bir akademik araştırma asistanısın. Verilen etik kurul raporu metninden "
    "ölçek bilgilerini çıkar. SADECE JSON döndür, başka hiçbir şey yazma."
)

APA_BORDER_SZ = 4

_WORD_M_MARK = "\x00M\x00"
_WORD_SD_MARK = "\x00SD\x00"
_WORD_STAT_RE = re.compile(
    r"Cohen's d|"
    r"\x00M\x00|\x00SD\x00|"
    r"\bdf\b|"
    r"\bF\b|\bt\b|\bU\b|\bH\b|\bn\b|\bp\b|\bd\b"
)

_CONTEXT_MAX_CHARS = 1500
