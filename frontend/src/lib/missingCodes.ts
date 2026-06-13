import { normalizeDecimalValue } from './formatting';
import type { DataRow } from '../types';

export interface InferredMissingCodes {
  codes: string[];
  columnMap: Record<string, string[]>;
  global: string | null;
}

export function inferMissingCodesFromRows(rows: DataRow[]): InferredMissingCodes {
  const empty: InferredMissingCodes = { codes: [], columnMap: {}, global: null };
  if (!rows?.length) return empty;

  const codeCols: Record<string, string[]> = {};
  const codeSet = new Set<string>();
  const cols = Object.keys(rows[0]);

  cols.forEach((col) => {
    const nums = rows
      .map((r) => parseFloat(String(normalizeDecimalValue(r[col] ?? ''))))
      .filter((n) => !Number.isNaN(n));
    if (nums.length < 10) return;

    const sorted = [...nums].sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? sorted[sorted.length - 1];
    const counts: Record<string, number> = {};
    nums.forEach((n) => {
      const key = String(n);
      counts[key] = (counts[key] ?? 0) + 1;
    });

    Object.entries(counts).forEach(([val, cnt]) => {
      if (cnt < 2) return;
      const f = parseFloat(val);
      const iv = Number.isInteger(f) ? f : null;
      const sentinel = iv !== null && [9, 99, 998, 999, -9, -99].includes(iv);
      const above = f > p95 && f >= Math.max(p95 * 1.2, p95 + 3);
      if (sentinel || above) {
        const key = String(iv ?? val);
        codeSet.add(key);
        if (!codeCols[key]) codeCols[key] = [];
        codeCols[key].push(col);
      }
    });
  });

  return {
    codes: [...codeSet],
    columnMap: codeCols,
    global: codeSet.size ? [...codeSet][0] : null,
  };
}

export function buildMissingCodesFromRead(readResult: {
  missing_codes?: Record<string, string[]>;
  global_missing_code?: string | null;
}): InferredMissingCodes {
  const perCol = readResult?.missing_codes ?? {};
  const codeCols: Record<string, string[]> = {};
  const codeSet = new Set<string>();
  Object.entries(perCol).forEach(([col, codes]) => {
    (codes ?? []).forEach((c) => {
      const key = String(c);
      codeSet.add(key);
      if (!codeCols[key]) codeCols[key] = [];
      codeCols[key].push(col);
    });
  });
  const global = readResult?.global_missing_code;
  if (global) codeSet.add(String(global));
  return {
    codes: [...codeSet],
    columnMap: codeCols,
    global: global ?? null,
  };
}

export function parseMissingCodesText(raw: string): string[] {
  return raw.split(/[,;]+/).map((s) => s.trim()).filter(Boolean);
}

export function getMissingCodesFromState(
  detected: InferredMissingCodes,
  manualText: string,
  editOpen: boolean,
  editValue?: string,
): string[] {
  if (editOpen) {
    const raw = editValue ?? manualText;
    return parseMissingCodesText(raw);
  }
  if (detected.codes?.length) return detected.codes;
  return parseMissingCodesText(manualText);
}

export function missingCodesRecordFromInferred(inferred: InferredMissingCodes): Record<string, string[]> {
  const perCol: Record<string, string[]> = {};
  Object.entries(inferred.columnMap).forEach(([code, cols]) => {
    cols.forEach((col) => {
      if (!perCol[col]) perCol[col] = [];
      perCol[col].push(code);
    });
  });
  return perCol;
}
