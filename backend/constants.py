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

REASON_CODES = (
    "amac_disi",
    "yetersiz_n",
    "dengesiz_grup",
    "totoloji",
    "cift_test",
    "dusuk_oncelik",
)

REASON_TEMPLATES: Dict[str, str] = {
    "amac_disi": (
        "Bu karşılaştırma araştırma amacıyla doğrudan ilişkili değildir."
    ),
    "yetersiz_n": (
        "Alt grup örneklem büyüklüğü (n={n}) güvenilir analiz için yetersizdir."
    ),
    "dengesiz_grup": (
        "{var_label} değişkeninde bir kategori örneklemin %90'ından fazlasını "
        "oluşturmaktadır."
    ),
    "totoloji": (
        "{var1_label} ve {var2_label} arasındaki korelasyon, ölçek alt boyutu ile "
        "toplam puan yapısından dolayı yapay olarak yüksek çıkabilir."
    ),
    "cift_test": (
        "{var1_label} ve {var2_label} için hem ki-kare hem grup karşılaştırma "
        "testi planlanmıştır; yalnızca biri tercih edilmelidir."
    ),
    "dusuk_oncelik": (
        "Araştırma amacına göre düşük öncelikli analiz olarak değerlendirilmiştir."
    ),
}

PLAN_TEST_SYSTEM = """Sen tez istatistik danışmanısın. Araştırma amacına hizmet eden testleri seç, etmeyenleri reason_code ile ele.
Yalnızca JSON döndür: {"selected":["id",...],"excluded":[{"id":"...","reason_code":"..."},...]}
reason_code: amac_disi | yetersiz_n | dengesiz_grup | totoloji | cift_test | dusuk_oncelik
Serbest metin gerekçe yazma. Ham veri veya tablo yok; yalnızca aday listesine bak."""

BULGU_SUMMARY_SYSTEM = """Sen tez bulgular bölümü editörüsün. Verilen kompakt test özetlerinden 3-5 cümlelik genel değerlendirme paragrafı yaz.
Geçmiş zaman (-miştir). Madde işareti kullanma. Tartışma yazma. Yalnızca verilen özetlere dayan."""
