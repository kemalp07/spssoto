import re
import httpx

url = "https://toad.halileksi.net/olcek/zorbalik-olcegi/"
h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"}
r = httpx.get(url, headers=h, timeout=15, follow_redirects=True)
text = r.text
open("scripts/toad_sample.html", "w", encoding="utf-8").write(text)

# strip scripts/styles for readability
body = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S | re.I)
body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.S | re.I)
plain = re.sub(r"<[^>]+>", "\n", body)
plain = re.sub(r"\n{2,}", "\n", plain)
lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
for ln in lines:
    low = ln.lower()
    if any(k in low for k in ("madde", "likert", "puan", "kesim", "aralık", "ölçek", "toplam", "derece")):
        print(ln[:200])
