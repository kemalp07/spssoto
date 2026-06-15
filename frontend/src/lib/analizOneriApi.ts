import { apiCall } from '../api/client';
import {
  anketTextFromContext,
  etikTextFromContext,
} from './analizOneri';
import { getAppState } from './storeAccess';
import type { AnalizOneriResponse } from '../types';

export async function fetchAnalizOneri(): Promise<AnalizOneriResponse> {
  const state = getAppState();
  const ctx = state.documents.context;
  const anketText = anketTextFromContext(ctx?.anket);
  const etikText = etikTextFromContext(ctx?.etik_kurul);

  console.log('[ONERİ] anket_text length:', anketText.length);
  console.log('[ONERİ] etik_text length:', etikText.length);
  console.log('[ONERİ] columns count:', state.columns.length);

  return apiCall<AnalizOneriResponse>('/analiz-oneri', {
    columns: state.columns,
    labels: state.savMetadata.pendingLabels ?? {},
    anket_text: anketText,
    etik_text: etikText,
  }, { timeout: 120_000 });
}
