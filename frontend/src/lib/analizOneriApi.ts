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
  return apiCall<AnalizOneriResponse>('/analiz-oneri', {
    columns: state.columns,
    labels: state.savMetadata.pendingLabels ?? {},
    anket_text: anketTextFromContext(ctx?.anket),
    etik_text: etikTextFromContext(ctx?.etik_kurul),
  }, { timeout: 120_000 });
}
