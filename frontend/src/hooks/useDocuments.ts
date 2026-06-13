import { useCallback, useState } from 'react';
import { ApiError, apiUpload } from '../api/client';
import { DOC_PARTIAL_WARN } from '../lib/documents';
import { getAppState } from '../lib/storeAccess';
import { useAppStore } from '../stores/useAppStore';
import type { UploadDocumentsResponse } from '../types';

export type DocumentUploadStatus = 'idle' | 'loading' | 'success' | 'error';

async function postDocuments(
  anketFile: File | null,
  etikFile: File | null,
  sessionId: string | null,
): Promise<UploadDocumentsResponse> {
  const form = new FormData();
  if (anketFile) form.append('anket', anketFile);
  if (etikFile) form.append('etik_kurul', etikFile);
  if (sessionId) form.append('session_id', sessionId);
  return apiUpload<UploadDocumentsResponse>('/upload-documents', form);
}

export function useDocuments() {
  const [error, setError] = useState<string | null>(null);

  const documents = useAppStore((s) => s.documents);
  const setAnketFile = useAppStore((s) => s.setAnketFile);
  const setEtikFile = useAppStore((s) => s.setEtikFile);
  const applyDocumentUpload = useAppStore((s) => s.applyDocumentUpload);
  const resetAnketDocument = useAppStore((s) => s.resetAnketDocument);
  const resetEtikDocument = useAppStore((s) => s.resetEtikDocument);
  const showToast = useAppStore((s) => s.showToast);

  const syncUpload = useCallback(async () => {
    const state = getAppState();
    const { anket, etikKurul, sessionId } = state.documents;
    if (!anket.file && !etikKurul.file) return;

    setError(null);
    try {
      const response = await postDocuments(anket.file, etikKurul.file, sessionId);
      applyDocumentUpload(response);
      showToast('Belge işlendi', 'success');
    } catch (err) {
      const message = err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : 'Belge yüklenemedi';
      setError(message);
      useAppStore.setState((s) => ({
        documents: {
          ...s.documents,
          anket: anket.file
            ? { ...s.documents.anket, loading: false, loaded: true, partial: true }
            : s.documents.anket,
          etikKurul: etikKurul.file
            ? { ...s.documents.etikKurul, loading: false, loaded: true, partial: true }
            : s.documents.etikKurul,
        },
      }));
    }
  }, [applyDocumentUpload, showToast]);

  const uploadAnket = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setError('Anket dosyası .docx formatında olmalıdır.');
      return;
    }
    setAnketFile(file);
    await syncUpload();
  }, [setAnketFile, syncUpload]);

  const uploadEtik = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) {
      setError('Etik kurul dosyası .docx formatında olmalıdır.');
      return;
    }
    setEtikFile(file);
    await syncUpload();
  }, [setEtikFile, syncUpload]);

  const clearAnket = useCallback(() => {
    resetAnketDocument();
    setError(null);
  }, [resetAnketDocument]);

  const clearEtik = useCallback(() => {
    resetEtikDocument();
    setError(null);
  }, [resetEtikDocument]);

  return {
    anket: documents.anket,
    etikKurul: documents.etikKurul,
    context: documents.context,
    sessionId: documents.sessionId,
    uploadAnket,
    uploadEtik,
    clearAnket,
    clearEtik,
    error,
    partialWarn: DOC_PARTIAL_WARN,
    hasAnketLoaded: documents.anket.loaded && !documents.anket.loading,
    hasEtikLoaded: documents.etikKurul.loaded && !documents.etikKurul.loading,
  };
}
