import { describe, expect, it } from 'vitest';
import { estimatePlanTableCount, normalizeCatalogItem } from './planCatalog';

describe('planCatalog', () => {
  it('counts enabled merge keys', () => {
    const catalog = [
      normalizeCatalogItem({ id: 'a', merge_key: 'a', enabled: true, cekirdek: true }),
      normalizeCatalogItem({ id: 'b', merge_key: 'b', enabled: true }),
      normalizeCatalogItem({ id: 'c', merge_key: 'c', enabled_default: false }),
    ];
    expect(estimatePlanTableCount(catalog)).toBe(2);
  });
});
