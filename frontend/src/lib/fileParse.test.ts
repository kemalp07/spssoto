import { describe, expect, it } from 'vitest';
import { inferMissingCodesFromRows } from './missingCodes';
import { suggestedScaleNamesFromColumns } from './fileParse';
import type { DataRow } from '../types';

describe('inferMissingCodesFromRows', () => {
  it('detects repeated sentinel 99', () => {
    const rows: DataRow[] = Array.from({ length: 12 }, (_, i) => ({
      score: i < 9 ? i + 1 : 99,
      other: i + 1,
    }));
    const result = inferMissingCodesFromRows(rows);
    expect(result.codes).toContain('99');
    expect(result.columnMap['99']).toContain('score');
  });

  it('ignores single outlier', () => {
    const rows: DataRow[] = Array.from({ length: 20 }, (_, i) => ({
      a: i === 19 ? 999 : i + 1,
    }));
    const result = inferMissingCodesFromRows(rows);
    expect(result.codes).not.toContain('999');
  });
});

describe('suggestedScaleNamesFromColumns', () => {
  it('extracts scale prefixes from _TOPLAM columns', () => {
    expect(
      suggestedScaleNamesFromColumns(['OYS_TOPLAM', 'GYA_TOPLAM', 'cinsiyet']),
    ).toBe('OYS, GYA');
  });
});
