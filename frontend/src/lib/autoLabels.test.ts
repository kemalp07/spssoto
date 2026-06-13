import { describe, expect, it } from 'vitest';
import { applyDocumentLabels, getUnlabeledColumns } from './autoLabels';

function baseLabels(columns: string[]): Record<string, string> {
  const labels: Record<string, string> = {};
  columns.forEach((col) => { labels[col] = col; });
  return labels;
}

describe('applyDocumentLabels', () => {
  it('ölçek eşleşmesinden etiket üretir', () => {
    const cols = ['OYS_TOPLAM', 'NEQ_TOPLAM', 'cinsiyet'];
    const result = applyDocumentLabels(
      baseLabels(cols),
      [
        { scale_name: 'Online Yemek Sipariş Tutumu Ölçeği', total_columns: ['OYS_TOPLAM'] },
        { scale_name: 'Gece Yeme Anketi', total_columns: ['NEQ_TOPLAM'] },
      ],
      [],
      cols,
    );
    expect(result.OYS_TOPLAM).toBe('Online Yemek Sipariş Tutumu Toplam Puanı');
    expect(result.NEQ_TOPLAM).toBe('Gece Yeme Toplam Puanı');
    expect(result.cinsiyet).toBe('Cinsiyet');
  });

  it('mevcut SPSS etiketlerini ezmez', () => {
    const labels = { OYS_TOPLAM: 'OYŞTÖ Toplam Puanı' };
    const result = applyDocumentLabels(labels, [], [], ['OYS_TOPLAM']);
    expect(result.OYS_TOPLAM).toBe('OYŞTÖ Toplam Puanı');
  });

  it('belge ölçek adlarından etiket üretir', () => {
    const cols = ['SBITO_TOPLAM', 'GYA_RISK_BINARY'];
    const result = applyDocumentLabels(
      baseLabels(cols),
      [],
      ['Sağlıklı Beslenme İnanç ve Tutum Ölçeği'],
      cols,
    );
    expect(result.SBITO_TOPLAM).not.toBe('SBITO_TOPLAM');
    expect(result.GYA_RISK_BINARY).toContain('(İkili)');
  });

  it('sonek çevirisi yapar', () => {
    const cols = ['ABC_TOPLAM', 'XYZ_GRUP'];
    const result = applyDocumentLabels(baseLabels(cols), [], [], cols);
    expect(result.ABC_TOPLAM).toBe('ABC Toplam Puanı');
    expect(result.XYZ_GRUP).toBe('XYZ Grubu');
  });
});

describe('getUnlabeledColumns', () => {
  it('sadece ham isimli kolonları döndürür', () => {
    const labels = {
      OYS_TOPLAM: 'Online Yemek Sipariş Tutumu Toplam Puanı',
      GARIP_KOLON: 'GARIP_KOLON',
    };
    expect(getUnlabeledColumns(labels, ['OYS_TOPLAM', 'GARIP_KOLON'])).toEqual(['GARIP_KOLON']);
  });
});
