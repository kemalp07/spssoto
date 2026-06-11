# StatAI

Tez ve akademik araştırma yazan öğrenciler için **SPSS alternatifi** web aracı. Veriyi yükleyin, değişken rollerini belirleyin; StatAI APA 7 uyumlu tablolar, otomatik bulgu metinleri ve Word çıktısı üretir.

## Ekran Görüntüsü

<!-- TODO: index.html ana ekran görüntüsü ekleyin -->
![StatAI ana ekran](docs/screenshot-placeholder.png)

## Özellikler

### Desteklenen testler ve tablolar

| Kategori | Testler |
|----------|---------|
| Tanımlayıcı | Frekans, tanımlayıcı istatistikler (x̄ ± SS, medyan) |
| Varsayımlar | Normallik (Shapiro-Wilk / Lilliefors), Cronbach α |
| Kategorik | Ki-kare, Fisher kesin olasılık (2×2, düşük beklenen frekans) |
| İki grup | Bağımsız t-testi (Welch), Mann-Whitney U + r etki büyüklüğü |
| Çok grup | Tek yönlü ANOVA + Tukey HSD; Kruskal-Wallis + Dunn post-hoc |
| İlişki | Pearson / Spearman korelasyon matrisi |
| Regresyon | Basit ve çoklu doğrusal regresyon (OLS, VIF) |
| Eşleştirilmiş | Bağımlı t-testi veya Wilcoxon işaretli sıralar (otomatik seçim) |

### Diğer

- `.sav` SPSS metadata (etiket, value label, ölçüm düzeyi, missing code)
- AI destekli değişken sınıflandırma ve analiz planı
- APA 7 formatında Word dışa aktarma
- Etik kurul raporundan ölçek bilgisi çıkarma

## Kurulum

### Gereksinimler

- Python 3.11+
- [Anthropic API](https://console.anthropic.com/) anahtarı (AI özellikleri için)

### Adımlar

```bash
git clone https://github.com/kemalp07/spssoto.git
cd spssoto
pip install -r requirements.txt
```

`backend/.env` dosyası oluşturun:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
# İsteğe bağlı — CORS (virgülle ayrılmış)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### Çalıştırma

Windows:

```bat
baslat.bat
```

Bu komut backend (uvicorn) ve frontend (`http.server`) sunucularını başlatır ve tarayıcıyı açar.

Manuel:

```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 8765
```

Başka terminalde proje kökünden: `python -m http.server 3000` → `http://localhost:3000/index.html`

## Desteklenen dosya formatları

| Format | Okuma |
|--------|--------|
| `.sav` | Backend (`/read-file`) — tam SPSS metadata |
| `.xlsx` / `.xls` | Backend |
| `.csv` | Frontend (SheetJS) |

## Nasıl çalışır?

1. **Veri yükle** — SAV, Excel veya CSV dosyasını sürükle-bırak
2. **Etik kurul / ölçek** (isteğe bağlı) — PDF/DOCX rapordan ölçek bilgisi
3. **Değişken rolleri** — AI sınıflandırma + etiket düzenleme (grouping / outcome)
4. **Analiz planı** — Hangi testlerin çalışacağını onayla
5. **Analiz** — APA tabloları üretilir
6. **Bulgu** — AI ile Türkçe bulgu paragrafları
7. **Word export** — Tek tıkla tez formatında indir

## Geliştirme

```bash
pip install -r requirements-dev.txt
pytest
```

## Proje yapısı

```
backend/
  main.py           # FastAPI endpoint'leri
  formatting.py     # APA sayı formatlama
  data_cleaning.py  # Eksik değer / kategorik normalizasyon
  stat_tests.py     # İstatistiksel test fonksiyonları
  spss_import.py    # SPSS tablo dönüşümü
  word_export.py    # Word üretimi
  ai_services.py    # LLM servisleri
  file_io.py        # Dosya okuma
index.html          # Tek sayfa frontend
```

## Lisans

[MIT](LICENSE)
