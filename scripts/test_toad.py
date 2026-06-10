import re
import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
headers = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as c:
    r0 = c.get("https://toad.halileksi.net/")
    print("home", r0.status_code, len(r0.text))

    queries = ["Online Yemek", "OYŞTÖ", "Gida Yeme", "Yeme Aliskanliklari", "Zorbalik", "NEQ"]
    for q in queries:
        r = c.get("https://toad.halileksi.net/", params={"s": q})
        links = re.findall(r'href="(https://toad\.halileksi\.net/olcek/[^"]+)"', r.text)
        print(q, r.status_code, "links", len(links), links[:3])

    sample = "https://toad.halileksi.net/olcek/zorbalik-olcegi/"
    r = c.get(sample)
    print("sample page", sample, r.status_code, len(r.text))
    if r.status_code == 200:
        for pat in [r"Madde\s*Say", r"Likert", r"Puan", r"Kesim", r"item"]:
            m = re.search(pat, r.text, re.I)
            print("  has", pat, bool(m))
