import re
import httpx

h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"}
with httpx.Client(headers=h, follow_redirects=True, timeout=15) as c:
    c.get("https://toad.halileksi.net/")
    r = c.get("https://toad.halileksi.net/", params={"s": "Online Yemek"})
    links = re.findall(r'href="(https://toad\.halileksi\.net/olcek/[^"]+)"', r.text)
    print("links", links)
    if links:
        p = c.get(links[0])
        for m in re.finditer(r"<p><strong>([^<]+)</strong>\s*:?\s*([^<]*(?:<[^/][^>]*>[^<]*)*)</p>", p.text):
            print(m.group(1), "=>", re.sub(r"<[^>]+>", "", m.group(2))[:120])
