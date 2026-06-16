import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# .env, shell'deki eski GEMINI_API_KEY gibi degiskenlerin ustune yazilir
load_dotenv(BASE_DIR / ".env", override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
CUTOFF_MODEL = os.getenv("CUTOFF_MODEL", ANTHROPIC_MODEL)
BULGU_MODEL = os.getenv("BULGU_MODEL", ANTHROPIC_MODEL)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# Vertex yalnizca GEMINI_USE_VERTEX=true veya GOOGLE_CLOUD_PROJECT ile (AQ = yeni AI Studio anahtari)
GEMINI_USE_VERTEX = os.getenv("GEMINI_USE_VERTEX", "").lower() in (
    "1", "true", "yes", "on",
)
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
# Gemini — proaktif veri analisti (veri_analisti.py); Claude — karar verici (karar_verici.py)
ENABLE_GEMINI_ENRICH = os.getenv("ENABLE_GEMINI_ENRICH", "true").lower() in (
    "1", "true", "yes", "on",
)
# Gemini çıktı üst sınırı (2.5 Flash model max ~65536); düşürmek için .env ile override
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "65536"))

_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
