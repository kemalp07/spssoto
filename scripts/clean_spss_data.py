"""
SPSS / StatAI veri seti temizleme betiği.

Kullanım:
    python scripts/clean_spss_data.py veri.csv
    python scripts/clean_spss_data.py veri.xlsx -o veri_temiz.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


KRONIK_COL = "kronik_hastalik"
SIGARA_COL = "sigara_kullanimi"
ALKOL_COL = "alkol_kullanimi"
MEDENI_COL = "medeni_durum"

VALID_KRONIK = {"yok", "var"}


def load_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        for sep in (";", ","):
            try:
                df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
                if df.shape[1] > 1:
                    return df
            except Exception:
                pass
        return pd.read_csv(path, encoding="utf-8-sig")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Desteklenmeyen dosya türü: {suffix}")


def normalize_label(value) -> str:
    if pd.isna(value) or value == "":
        return ""
    return str(value).strip().lower()


def drop_invalid_kronik_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if KRONIK_COL not in df.columns:
        print(f"[UYARI] '{KRONIK_COL}' sutunu bulunamadi — adim atlandi.")
        return df, 0

    col = df[KRONIK_COL]
    invalid_mask = col.apply(
        lambda v: normalize_label(v) not in VALID_KRONIK and str(v).strip() != ""
    )
    n_drop = int(invalid_mask.sum())

    if n_drop:
        print(f"   Silinen satırlar ({KRONIK_COL} hatalı): {n_drop}")
        invalid_vals = col[invalid_mask].value_counts()
        for val, cnt in invalid_vals.items():
            print(f"      - '{val}' -> {cnt} satir")

    return df.loc[~invalid_mask].copy(), n_drop


def check_sigara_alkol_identity(df: pd.DataFrame) -> bool:
    if SIGARA_COL not in df.columns or ALKOL_COL not in df.columns:
        print(f"[UYARI] '{SIGARA_COL}' veya '{ALKOL_COL}' bulunamadi — benzerlik testi atlandi.")
        return False

    sigara = df[SIGARA_COL].astype(str).str.strip()
    alkol = df[ALKOL_COL].astype(str).str.strip()
    identical = sigara.eq(alkol) | (sigara.isna() & alkol.isna())

    match_pct = identical.mean() * 100
    print("\n[SIGARA/ALKOL] Benzerlik testi")
    print(f"   Eşleşen satır: {identical.sum()} / {len(df)} (%{match_pct:.1f})")

    if identical.all():
        print("\n[UYARI] 'sigara_kullanimi' ve 'alkol_kullanimi' sutunlari %100 ayni!")
        print("   Olası veri kopyalama hatası — lütfen SPSS kaynağını kontrol edin.\n")
        print("   İlk 5 satır karşılaştırması:")
        sample = df[[SIGARA_COL, ALKOL_COL]].head()
        print(sample.to_string(index=True))
        return True

    print("   Sutunlar birebir ayni degil (beklenen durum).")
    return False


def drop_medeni_durum(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    if MEDENI_COL not in df.columns:
        print(f"[UYARI] '{MEDENI_COL}' sutunu bulunamadi — adim atlandi.")
        return df, False

    counts = df[MEDENI_COL].value_counts(dropna=False)
    print(f"\n[MEDENI DURUM] Dagilim (kaldirilmadan once):")
    for val, cnt in counts.items():
        pct = cnt / len(df) * 100
        print(f"   - {val}: n={cnt} (%{pct:.1f})")

    df_out = df.drop(columns=[MEDENI_COL])
    return df_out, True


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    summary: dict = {
        "baslangic_satir": len(df),
        "baslangic_sutun": len(df.columns),
        "silinen_satir_kronik": 0,
        "kaldirilan_sutun_medeni": False,
        "sigara_alkol_ayni": False,
    }

    print("=" * 60)
    print("SPSS / StatAI VERİ TEMİZLEME")
    print("=" * 60)
    print(f"Başlangıç: {summary['baslangic_satir']} satır × {summary['baslangic_sutun']} sütun\n")

    print("[1] Kronik hastalik temizligi")
    df, summary["silinen_satir_kronik"] = drop_invalid_kronik_rows(df)

    summary["sigara_alkol_ayni"] = check_sigara_alkol_identity(df)

    print("\n[2] Medeni durum degerlendirmesi")
    df, summary["kaldirilan_sutun_medeni"] = drop_medeni_durum(df)

    summary["bitis_satir"] = len(df)
    summary["bitis_sutun"] = len(df.columns)

    print("\n" + "=" * 60)
    print("ÖZET")
    print("=" * 60)
    print(f"   Silinen satır (kronik_hastalik='3' vb.): {summary['silinen_satir_kronik']}")
    print(f"   Kaldırılan sütun (medeni_durum):         {'Evet' if summary['kaldirilan_sutun_medeni'] else 'Hayır'}")
    print(f"   Sigara = alkol (%100):                   {'EVET — UYARI' if summary['sigara_alkol_ayni'] else 'Hayır'}")
    print(f"   Son durum: {summary['bitis_satir']} satır × {summary['bitis_sutun']} sütun")
    print("=" * 60)

    return df, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="SPSS/StatAI veri temizleme")
    parser.add_argument("input", type=Path, help="Giriş dosyası (.csv, .xlsx)")
    parser.add_argument("-o", "--output", type=Path, help="Temiz veri çıktı dosyası")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Hata: Dosya bulunamadı: {args.input}", file=sys.stderr)
        return 1

    df = load_dataset(args.input)
    df_cleaned, _ = clean_dataset(df)

    if args.output:
        suffix = args.output.suffix.lower()
        if suffix == ".csv":
            df_cleaned.to_csv(args.output, index=False, encoding="utf-8-sig")
        elif suffix in {".xlsx", ".xls"}:
            df_cleaned.to_excel(args.output, index=False)
        else:
            df_cleaned.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"\nKaydedildi: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
