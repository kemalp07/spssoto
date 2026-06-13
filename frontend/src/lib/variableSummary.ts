import { normalizeDecimalValue } from './formatting';
import type { DataRow } from '../types';

export function valueLabelForCol(
  col: string,
  rawValue: unknown,
  valueLabels: Record<string, Record<string, string>>,
): string | null {
  const vl = valueLabels[col];
  if (!vl) return null;
  const key = String(rawValue).trim();
  if (vl[key] != null) return String(vl[key]);
  const asInt = parseInt(key, 10);
  if (!Number.isNaN(asInt) && vl[String(asInt)] != null) return String(vl[String(asInt)]);
  return null;
}

export function variableSummaryText(
  col: string,
  parsedData: DataRow[],
  valueLabels: Record<string, Record<string, string>>,
): string {
  if (!parsedData?.length) return '—';
  const raw = parsedData
    .map((r) => r[col])
    .filter((v) => v !== '' && v != null && v !== undefined);
  if (!raw.length) return '—';

  const unique = [...new Set(raw.map((v) => String(v).trim()))];
  const nUnique = unique.length;
  const nums = raw.map((v) => parseFloat(String(normalizeDecimalValue(v))));
  const numericRatio = nums.filter((n) => !Number.isNaN(n)).length / raw.length;
  const isContinuous = numericRatio > 0.8 && nUnique > 8;

  if (isContinuous) {
    const valid = nums.filter((n) => !Number.isNaN(n));
    if (!valid.length) return '—';
    const min = Math.min(...valid);
    const max = Math.max(...valid);
    const fmt = (n: number) => (Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100));
    return `${fmt(min)} – ${fmt(max)}`;
  }

  if (nUnique === 2) {
    const sorted = unique.slice().sort((a, b) => {
      const na = parseFloat(a);
      const nb = parseFloat(b);
      if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
      return a.localeCompare(b, 'tr');
    });
    return `2 kategori (${sorted.join('/')})`;
  }

  const catLabels = unique
    .map((v) => valueLabelForCol(col, v, valueLabels))
    .filter(Boolean)
    .slice(0, 3);

  if (catLabels.length) {
    return `${nUnique} kategori — ${catLabels.join(', ')}${nUnique > 3 ? '…' : ''}`;
  }
  return `${nUnique} kategori`;
}
