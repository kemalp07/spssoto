"""Layout sonrası istatistik doğruluk kontrolü."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import levene, ttest_ind

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "backend"))

from formatting import TableCounter
from schemas import Variable
from stat_tests import run_analyze, table_ttest
from table_layout import merge_ttest_tables


def _short(s: str, n: int = 55) -> str:
    s = str(s).replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


rng = np.random.default_rng(42)
n = 200
sex = rng.choice([1, 2], n)
oys = np.where(sex == 1, rng.normal(55, 8, n), rng.normal(48, 8, n))
neq = np.where(sex == 1, rng.normal(26, 4, n), rng.normal(24, 4, n))

df = pd.DataFrame({
    "dbf_cinsiyet": sex,
    "BOLUM": rng.choice([1, 2, 3], n),
    "YAS_GRUBU": rng.choice([1, 2, 3], n),
    "OYS_TOPLAM": oys,
    "NEQ_TOPLAM": neq,
    "SBITO_TOPLAM": rng.normal(70, 10, n),
})

vars_ = [
    Variable(name="dbf_cinsiyet", label="Cinsiyet", type="categorical", role="grouping", included=True),
    Variable(name="BOLUM", label="Bolum", type="categorical", role="grouping", included=True),
    Variable(name="YAS_GRUBU", label="Yas Grubu", type="categorical", role="grouping", included=True),
    Variable(name="OYS_TOPLAM", label="OYS Toplam", type="continuous", role="outcome", included=True),
    Variable(name="NEQ_TOPLAM", label="NEQ Toplam", type="continuous", role="outcome", included=True),
    Variable(name="SBITO_TOPLAM", label="SBITO Toplam", type="continuous", role="outcome", included=True),
]

enabled = ["descriptive", "normality", "frequency", "ttest", "correlation"]
results, _ = run_analyze(df, vars_, enabled, None, None, [])

print("=== LAYOUT SONRASI TABLOLAR ===")
print(f"Toplam tablo: {len(results)}")
for r in results:
    flags = []
    if r.get("combined"):
        flags.append("birlesik")
    if r.get("lower_triangle"):
        flags.append("alt_ucgen")
    flag_txt = f" ({', '.join(flags)})" if flags else ""
    print(f"  [{r['type']}] Tablo {r.get('table_number')}{flag_txt}: {_short(r.get('title', ''))}")

cv, sv1, sv2 = vars_[0], vars_[3], vars_[4]
tc = TableCounter()
t1 = table_ttest(tc, df, cv, sv1)
t2 = table_ttest(tc, df, cv, sv2)
merged = merge_ttest_tables([t1, t2])

print("\n=== ISTATISTIK DOGRULAMA (t-test) ===")
g1 = df.loc[df.dbf_cinsiyet == 1, "OYS_TOPLAM"]
g2 = df.loc[df.dbf_cinsiyet == 2, "OYS_TOPLAM"]
_, lev_p = levene(g1, g2)
t_scipy, p_scipy = ttest_ind(g1, g2, equal_var=lev_p >= 0.05)
print(f"Scipy OYS:  t={t_scipy:.3f}, p={p_scipy:.3f}")
print(f"Tablo OYS:  t={t1['t']}, p={t1['p']}")
t_ok = abs(float(t1["t"]) - float(t_scipy)) < 0.02
p_ok = abs(float(t1["p"]) - float(p_scipy)) < 0.002
print(f"t eslesmesi: {'OK' if t_ok else 'HATA'}")
print(f"p eslesmesi: {'OK' if p_ok else 'HATA'}")

if merged:
    for row in merged["rows"]:
        print(f"Birlesik tablo: {row[0]} -> t={row[3]}, p={row[5]}, d={row[6]}")

desc = next((r for r in results if r["type"] == "descriptive"), None)
norm_gone = not any(r["type"] == "normality" for r in results)
print("\n=== NORMALLIK DIPNOTU ===")
print(f"Normallik tablosu kaldirildi: {norm_gone}")
if desc:
    note = desc.get("note") or ""
    print(f"Dipnotta normallik var: {'Normallik' in note}")

demo = [r for r in results if r["type"] in ("demographics", "frequency")]
print(f"\nDemografi tablo sayisi: {len(demo)} (tip: {[r['type'] for r in demo]})")

ttests = [r for r in results if r["type"] == "ttest"]
print(f"t-test tablo sayisi: {len(ttests)} (birlesik: {sum(1 for t in ttests if t.get('combined'))})")

corr = next((r for r in results if r["type"] == "correlation_matrix"), None)
if corr and corr.get("rows"):
    upper_empty = corr["rows"][0][2] == ""
    print(f"Korelasyon ust ucgen bos: {'OK' if upper_empty else 'HATA'}")

has_comma = any(
    "," in str(cell)
    for r in results
    for row in r.get("rows", [])
    for cell in row
)
print(f"TR virgul formati: {'OK' if has_comma else 'yok/henuz yok'}")

all_ok = t_ok and p_ok and norm_gone and len(demo) <= 2
print(f"\nGENEL: {'DOGRU GORUNUYOR' if all_ok else 'BIR SEYLERI KONTROL ET'}")
