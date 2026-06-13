import { describe, expect, it, beforeEach } from 'vitest';
import { countAnketItems, countEtikHypotheses } from './documents';
import { useAppStore } from '../stores/useAppStore';
import type { UploadDocumentsResponse } from '../types';

describe('documents helpers', () => {
  it('counts anket items across sections', () => {
    expect(countAnketItems({
      sections: [{ items: [1, 2] }, { items: [3] }],
    })).toBe(3);
  });

  it('counts etik hypotheses', () => {
    expect(countEtikHypotheses({
      hypotheses: ['H1', 'H2'],
    })).toBe(2);
  });
});

describe('applyDocumentUpload', () => {
  beforeEach(() => {
    useAppStore.getState().reset();
  });

  it('writes documentContext and prefills wizard topic from etik', () => {
    const etikFile = new File([''], 'etik.docx');
    useAppStore.getState().setEtikFile(etikFile);

    const response: UploadDocumentsResponse = {
      session_id: 'sess-1',
      document_context: {
        etik_kurul: {
          hypotheses: ['Cinsiyet ile OYS arasında fark vardır.'],
          aim: 'Araştırmanın amacı',
          scale_names: ['OYŞTÖ'],
        },
      },
      etik_kurul: {
        hypotheses: ['Cinsiyet ile OYS arasında fark vardır.'],
        aim: 'Araştırmanın amacı',
        scale_names: ['OYŞTÖ'],
      },
    };

    useAppStore.getState().applyDocumentUpload(response);

    const state = useAppStore.getState();
    expect(state.documents.sessionId).toBe('sess-1');
    expect(state.documents.context?.etik_kurul?.hypotheses).toHaveLength(1);
    expect(state.documents.etikKurul.hypothesisCount).toBe(1);
    expect(state.wizard.researchTopic).toContain('Cinsiyet');
    expect(state.wizard.scaleNames).toBe('OYŞTÖ');
  });
});
