import { describe, expect, it, beforeEach } from 'vitest';
import {
  countAnketItems,
  countAnketSections,
  countEtikHypotheses,
  formatAnketUploadMeta,
  formatEtikUploadMeta,
} from './documents';
import { useAppStore } from '../stores/useAppStore';
import type { UploadDocumentsResponse } from '../types';

describe('documents helpers', () => {
  it('counts anket items across sections', () => {
    expect(countAnketItems({
      sections: [{ items: [{ no: 1 }, { no: 2 }] }, { items: [{ no: 3 }] }],
    })).toBe(3);
  });

  it('formats anket meta with sections and items', () => {
    expect(formatAnketUploadMeta({
      sections: [
        { title: 'OYS', items: [{ no: 1 }, { no: 2 }] },
        { title: 'NEQ', items: [{ no: 1 }] },
      ],
    })).toBe('2 bölüm, 3 madde ayrıştırıldı');
  });

  it('formats anket meta when sections exist without items', () => {
    expect(formatAnketUploadMeta({
      sections: [{ title: 'Kapak' }, { title: 'OYS', items: [] }],
    })).toBe('2 bölüm tespit edildi (madde eşleşmedi)');
  });

  it('formats etik meta', () => {
    expect(formatEtikUploadMeta({
      hypotheses: ['H1', 'H2'],
    })).toBe('2 araştırma sorusu ayrıştırıldı');
  });

  it('counts anket sections', () => {
    expect(countAnketSections({
      sections: [{ title: 'A' }, { title: 'B', items: [{ no: 1 }] }],
    })).toBe(2);
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
