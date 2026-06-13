import { describe, expect, it } from 'vitest';
import {
  getLabelPhaseColumns,
  isLabelComplete,
  shouldSkipLabelsPhase,
} from './labels';

describe('labels', () => {
  const columns = ['cinsiyet', 'oysto_1', 'oysto_toplam'];

  it('filters item columns from label phase', () => {
    expect(getLabelPhaseColumns(columns)).toEqual(['cinsiyet', 'oysto_toplam']);
  });

  it('detects incomplete labels', () => {
    expect(isLabelComplete('cinsiyet', { cinsiyet: 'cinsiyet' })).toBe(false);
    expect(isLabelComplete('cinsiyet', { cinsiyet: 'Cinsiyet' })).toBe(true);
  });

  it('skips label phase when all labels complete', () => {
    expect(shouldSkipLabelsPhase(
      columns,
      { cinsiyet: 'Cinsiyet', oysto_toplam: 'OYŞTÖ Toplam' },
    )).toBe(true);
  });
});
