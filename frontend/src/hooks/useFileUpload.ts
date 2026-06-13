import { useCallback, useState } from 'react';
import { ApiError, apiUpload } from '../api/client';
import { fileTypeFromName, parseSpreadsheetFile } from '../lib/fileParse';
import { useAppStore } from '../stores/useAppStore';
import type { ReadFileResponse } from '../types';

export type UploadStatus = 'idle' | 'loading' | 'success' | 'error';

async function readFileViaBackend(file: File): Promise<ReadFileResponse> {
  const formData = new FormData();
  formData.append('file', file);
  return apiUpload<ReadFileResponse>('/read-file', formData);
}

export function useFileUpload() {
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<File | null>(null);

  const fileInfo = useAppStore((s) => s.fileInfo);
  const parsedData = useAppStore((s) => s.parsedData);
  const columns = useAppStore((s) => s.columns);
  const applyFileUpload = useAppStore((s) => s.applyFileUpload);
  const clearFileUpload = useAppStore((s) => s.clearFileUpload);
  const showToast = useAppStore((s) => s.showToast);

  const processFile = useCallback(async (file: File) => {
    const type = fileTypeFromName(file.name);
    if (!type) {
      setError('Desteklenmeyen dosya formatı. .sav, .xlsx, .xls veya .csv yükleyin.');
      setStatus('error');
      return;
    }

    setStatus('loading');
    setError(null);
    setLastFile(file);

    try {
      let result: ReadFileResponse;
      if (type === 'sav' || type === 'xlsx' || type === 'xls') {
        result = await readFileViaBackend(file);
      } else {
        result = await parseSpreadsheetFile(file);
      }

      if (!result.data?.length) {
        throw new Error('Dosya boş görünüyor');
      }

      applyFileUpload(file, result);
      setStatus('success');

      const labelCount = result.labels_found ?? 0;
      if (labelCount > 0) {
        const src = result.source === 'spss' ? 'SPSS\'den' : 'Excel\'den';
        showToast(`${labelCount} değişken etiketi ${src} otomatik okundu`, 'success');
      } else {
        showToast('Veri dosyası yüklendi', 'success');
      }
    } catch (err) {
      const message = err instanceof ApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : 'Dosya okunamadı';
      setError(message);
      setStatus('error');
    }
  }, [applyFileUpload, showToast]);

  const resetFile = useCallback(() => {
    clearFileUpload();
    setLastFile(null);
    setError(null);
    setStatus('idle');
  }, [clearFileUpload]);

  const retry = useCallback(() => {
    if (lastFile) void processFile(lastFile);
  }, [lastFile, processFile]);

  return {
    status,
    error,
    uploadFile: processFile,
    resetFile,
    retry,
    hasFile: Boolean(fileInfo && parsedData.length > 0),
    fileInfo,
    rowCount: parsedData.length,
    columnCount: columns.length,
    isLoading: status === 'loading',
  };
}
