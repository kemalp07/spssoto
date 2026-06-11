# Test dosyaları

Buraya kendi verilerinizi koyun; `scripts/run_fixture_test.py` tarayıcı açmadan tüm akışı dener.

## Dosyalar

| Dosya | Zorunlu | Açıklama |
|-------|---------|----------|
| `anket.sav` | Evet | SPSS veri dosyası |
| `anket.docx` | Hayır | Etik kurul / anket raporu (ölçek + araştırma konusu çıkarımı) |

Alternatif isimler de kabul edilir: `data.sav`, `ethics.docx` veya klasördeki tek `.sav` / `.docx`.

## Çalıştırma

Proje kökünden:

```bash
python scripts/run_fixture_test.py
```

Sadece kural tabanlı plan (Claude yok):

```bash
python scripts/run_fixture_test.py --no-ai
```

Plan + analiz tabloları:

```bash
python scripts/run_fixture_test.py --full
```

## Not

- Bu klasördeki `.sav` / `.docx` dosyaları git'e eklenmez (gizlilik).
- Claude testleri için `backend/.env` içinde `ANTHROPIC_API_KEY` gerekir.
