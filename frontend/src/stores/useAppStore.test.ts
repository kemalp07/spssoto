import { describe, expect, it, beforeEach } from 'vitest';
import { useAppStore } from '../stores/useAppStore';
import type { ReadFileResponse } from '../types';

describe('useAppStore applyFileUpload', () => {
  beforeEach(() => {
    useAppStore.getState().reset();
  });

  it('stores parsed data and columns from read result', () => {
    const file = new File([''], 'test.sav', { type: 'application/octet-stream' });
    const readResult: ReadFileResponse = {
      data: [{ cinsiyet: 1, OYS_TOPLAM: 42 }],
      columns: ['cinsiyet', 'OYS_TOPLAM'],
      labels: { cinsiyet: 'Cinsiyet' },
      labels_found: 1,
      source: 'spss',
      missing_codes: { OYS_TOPLAM: ['99'] },
      global_missing_code: '99',
    };

    useAppStore.getState().applyFileUpload(file, readResult);

    const state = useAppStore.getState();
    expect(state.parsedData).toHaveLength(1);
    expect(state.columns).toEqual(['cinsiyet', 'OYS_TOPLAM']);
    expect(state.fileInfo?.name).toBe('test.sav');
    expect(state.fileInfo?.type).toBe('sav');
    expect(state.savMetadata.pendingLabels.cinsiyet).toBe('Cinsiyet');
    expect(state.savMetadata.missingCodes.OYS_TOPLAM).toEqual(['99']);
    expect(state.wizard.scaleNames).toBe('OYS');
  });

  it('clearFileUpload resets file state', () => {
    const file = new File([''], 'a.csv', { type: 'text/csv' });
    useAppStore.getState().applyFileUpload(file, {
      data: [{ x: 1 }],
      columns: ['x'],
    });
    useAppStore.getState().clearFileUpload();
    const state = useAppStore.getState();
    expect(state.fileInfo).toBeNull();
    expect(state.parsedData).toHaveLength(0);
  });
});
