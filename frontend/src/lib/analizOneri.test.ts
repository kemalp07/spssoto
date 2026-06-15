import { describe, expect, it } from 'vitest';
import {
  matchColumnHint,
  scalesFromOneriOlcekler,
} from './analizOneri';

describe('analizOneri helpers', () => {
  it('matches column hints case-insensitively', () => {
    const cols = ['bolum', 'OYS_TOPLAM', 'dbf_cinsiyet'];
    expect(matchColumnHint(cols, 'BOLUM')).toBe('bolum');
    expect(matchColumnHint(cols, 'oys_toplam')).toBe('OYS_TOPLAM');
  });

  it('builds cronbach scales from oneri olcekler', () => {
    const cols = ['OYS_1', 'OYS_2', 'OYS_3', 'OYS_TOPLAM'];
    const scales = scalesFromOneriOlcekler(
      [{ ad: 'OYŞTÖ', maddeler_prefix: 'OYS' }],
      cols,
    );
    expect(scales).toHaveLength(1);
    expect(scales[0].cronbach_items).toEqual(['OYS_1', 'OYS_2', 'OYS_3']);
  });
});
