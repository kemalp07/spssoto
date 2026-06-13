import { describe, expect, it } from 'vitest';
import { classifyColumns, mapClassifyResponse, resolveAiStatus } from './classify';

describe('classifyColumns', () => {
  const data = [
    { cinsiyet: '1', yas: '25', oysto_toplam: '42' },
    { cinsiyet: '2', yas: '30', oysto_toplam: '38' },
  ];

  it('puts demographic patterns in grouping', () => {
    const { groupingCols, outcomeCols } = classifyColumns(['cinsiyet', 'yas', 'oysto_toplam'], data);
    expect(groupingCols).toContain('cinsiyet');
    expect(outcomeCols).toContain('oysto_toplam');
  });

  it('excludes item-like columns', () => {
    const { excludeCols } = classifyColumns(['oysto_1', 'oysto_2'], data);
    expect(excludeCols).toEqual(['oysto_1', 'oysto_2']);
  });
});

describe('mapClassifyResponse', () => {
  it('forces measurement labels to outcome', () => {
    const mapped = mapClassifyResponse(
      {
        categorical: ['boy'],
        continuous: [],
        recommendations: { boy: { role: 'grouping' } },
      },
      { boy: 'Boy (cm)' },
    );
    expect(mapped.outcomeCols).toContain('boy');
    expect(mapped.groupingCols).not.toContain('boy');
  });
});

describe('resolveAiStatus', () => {
  it('returns not_recommended for exclude derived vars', () => {
    expect(resolveAiStatus('x', {}, { x: { name: 'x', action: 'exclude' } })).toBe('not_recommended');
  });
});
