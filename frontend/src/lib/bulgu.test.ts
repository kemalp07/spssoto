import { describe, expect, it } from 'vitest';
import {
  bulgularForApi,
  bulgularForWordExport,
  migratePersistedBulgular,
  normalizeBulguEntry,
} from '../lib/bulgu';

describe('bulgu helpers', () => {
  it('normalizes legacy string entries', () => {
    const entry = normalizeBulguEntry('Eski bulgu metni');
    expect(entry?.text).toBe('Eski bulgu metni');
    expect(entry?.version).toBe(1);
    expect(entry?.isLocked).toBe(false);
  });

  it('flattens bulgular for API', () => {
    const api = bulgularForApi({
      '0': {
        text: 'Bulgu metni',
        lockedAt: '2026-01-01T00:00:00.000Z',
        version: 2,
        isLocked: true,
      },
    });
    expect(api['0']).toBe('Bulgu metni');
  });

  it('exports metadata for word', () => {
    const exported = bulgularForWordExport({
      '1': {
        text: 'Test',
        lockedAt: '2026-06-15T10:00:00.000Z',
        version: 3,
        isLocked: true,
      },
    });
    expect(exported['1']).toEqual({
      text: 'Test',
      version: 3,
      lockedAt: '2026-06-15T10:00:00.000Z',
    });
  });

  it('migrates persisted mixed formats', () => {
    const migrated = migratePersistedBulgular({
      '0': 'eski',
      '1': {
        text: 'yeni',
        lockedAt: '2026-01-01',
        version: 2,
        isLocked: true,
      },
    });
    expect(migrated['0'].version).toBe(1);
    expect(migrated['1'].version).toBe(2);
  });
});

describe('bulgu store actions', () => {
  it('locks and unlocks bulgu entries', async () => {
    const { useAppStore } = await import('../stores/useAppStore');
    useAppStore.getState().reset();
    useAppStore.getState().setBulgu(0, 'İlk bulgu');
    useAppStore.getState().lockBulgu(0);
    expect(useAppStore.getState().results.bulgular['0'].isLocked).toBe(true);

    useAppStore.getState().setBulgu(0, 'Değişmemeli');
    expect(useAppStore.getState().results.bulgular['0'].text).toBe('İlk bulgu');

    useAppStore.getState().unlockBulgu(0);
    useAppStore.getState().regenerateBulgu(0, 'Yeni bulgu');
    const entry = useAppStore.getState().results.bulgular['0'];
    expect(entry.version).toBe(2);
    expect(entry.previousVersions).toEqual(['İlk bulgu']);
    expect(entry.text).toBe('Yeni bulgu');
  });
});
