import type { ScaleMatch } from '../types';

/** Türkçe sonek çevirileri */
const SUFFIX_TR: [RegExp, string][] = [
  [/_TOPLAM$/i, 'Toplam Puanı'],
  [/_TOTAL$/i, 'Toplam Puanı'],
  [/_SCORE$/i, 'Puanı'],
  [/_PUAN$/i, 'Puanı'],
  [/_SKOR$/i, 'Skoru'],
  [/_AVG$|_MEAN$|_ORT$/i, 'Ortalaması'],
  [/_GRUP$/i, 'Grubu'],
  [/_GROUP$/i, 'Grubu'],
  [/_BINARY$/i, '(İkili)'],
  [/_RISK$/i, 'Risk Durumu'],
  [/_KAT$|_KATEGORI$/i, 'Kategorisi'],
];

/** Yaygın demografik değişkenler */
const DEMOGRAPHICS: Record<string, string> = {
  cinsiyet: 'Cinsiyet',
  gender: 'Cinsiyet',
  yas: 'Yaş',
  age: 'Yaş',
  boy: 'Boy',
  kilo: 'Kilo',
  vki: 'VKİ',
  bki: 'BKİ',
  bmi: 'BKİ',
  bolum: 'Bölüm',
  sinif: 'Sınıf',
  medeni_durum: 'Medeni Durum',
  medeni: 'Medeni Durum',
  egitim: 'Eğitim Düzeyi',
  gelir: 'Gelir Düzeyi',
  sigara: 'Sigara Kullanımı',
  alkol: 'Alkol Kullanımı',
};

/**
 * Belge ve ölçek bilgilerinden prefix → tam ad haritası kur.
 */
function buildPrefixMap(
  matchResults: ScaleMatch[],
  documentScaleNames: string[],
  columns: string[],
): Record<string, string> {
  const map: Record<string, string> = {};
  const stripSuffix = (s: string) =>
    s.replace(/\s*(ölçeği|anketi|envanteri|formu|testi|skalası|indeksi)\s*$/i, '').trim();

  for (const m of matchResults) {
    if (!m.scale_name) continue;
    const base = stripSuffix(m.scale_name);
    for (const col of [...(m.total_columns ?? []), ...(m.matched_columns ?? [])]) {
      const prefix = col.split('_')[0].toUpperCase();
      if (prefix.length >= 2) map[prefix] = base;
    }
    const sid = (m.scale_id ?? m.registry_id ?? '').toUpperCase();
    if (sid.length >= 2 && sid.length <= 10) map[sid] = base;
  }

  const colPrefixes = new Set(
    columns.map((c) => c.split('_')[0].toUpperCase()).filter((p) => p.length >= 2),
  );
  for (const name of documentScaleNames) {
    const base = stripSuffix(name);
    const words = name.split(/\s+/).filter((w) =>
      !['ölçeği', 'anketi', 'envanteri', 'formu', 'testi', 've', 'ile', 'için', 've/veya'].includes(w.toLowerCase()),
    );
    const abbr = words.map((w) => w[0]?.toUpperCase() ?? '').join('');
    const abbrAscii = abbr.replace(/[ÖÜŞÇĞİ]/g, (c) =>
      ({ Ö: 'O', Ü: 'U', Ş: 'S', Ç: 'C', Ğ: 'G', İ: 'I' }[c] ?? c),
    );

    for (const candidate of [abbr, abbrAscii]) {
      if (candidate.length >= 2 && colPrefixes.has(candidate) && !map[candidate]) {
        map[candidate] = base;
      }
      for (const prefix of colPrefixes) {
        if (map[prefix]) continue;
        if ((candidate.startsWith(prefix) || prefix.startsWith(candidate)) && candidate.length >= 2) {
          map[prefix] = base;
        }
      }
    }
  }

  return map;
}

/**
 * Aşama 2+3: Belge context'inden etiket üret.
 * Sadece boş (label === col) olanları doldurur.
 */
export function applyDocumentLabels(
  labels: Record<string, string>,
  matchResults: ScaleMatch[],
  documentScaleNames: string[],
  columns: string[],
): Record<string, string> {
  const result = { ...labels };
  const prefixMap = buildPrefixMap(matchResults, documentScaleNames, columns);

  for (const col of columns) {
    if (result[col] && result[col] !== col) continue;

    const lower = col.toLowerCase();

    if (DEMOGRAPHICS[lower]) {
      result[col] = DEMOGRAPHICS[lower];
      continue;
    }

    const prefix = col.split('_')[0].toUpperCase();
    const scaleName = prefixMap[prefix];
    if (scaleName) {
      let matched = false;
      for (const [pat, tr] of SUFFIX_TR) {
        if (pat.test(col)) {
          result[col] = `${scaleName} ${tr}`;
          matched = true;
          break;
        }
      }
      if (!matched) {
        const rest = col.split('_').slice(1).join(' ');
        result[col] = rest
          ? `${scaleName} — ${rest.charAt(0).toUpperCase()}${rest.slice(1).toLowerCase()}`
          : scaleName;
      }
      continue;
    }

    for (const [pat, tr] of SUFFIX_TR) {
      if (pat.test(col)) {
        const base = col.replace(pat, '');
        result[col] = `${base} ${tr}`;
        break;
      }
    }
  }

  return result;
}

/** Hâlâ etiketsiz kalan kolonları döndürür (Aşama 4 AI). */
export function getUnlabeledColumns(
  labels: Record<string, string>,
  columns: string[],
): string[] {
  return columns.filter((col) => !labels[col] || labels[col] === col);
}
