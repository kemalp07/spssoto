import { apiCall } from '../api/client';
import {
  anketTextFromContext,
  etikTextFromContext,
} from './analizOneri';
import { getAppState } from './storeAccess';
import type { AnalizOneriResponse, AnketParseResult, EtikKurulParseResult } from '../types';

export async function fetchAnalizOneri(): Promise<AnalizOneriResponse> {
  const state = getAppState();
  const ctx = state.documents.context;
  const anketSource = (ctx?.anket ?? state.documents.anket.data) as AnketParseResult | null | undefined;
  const etikSource = (ctx?.etik_kurul ?? state.documents.etikKurul.data) as EtikKurulParseResult | null | undefined;

  const anketText = anketTextFromContext(anketSource);
  const etikText = etikTextFromContext(etikSource);

  return apiCall<AnalizOneriResponse>('/analiz-oneri', {
    columns: state.columns,
    labels: state.savMetadata.pendingLabels ?? {},
    anket_text: anketText,
    etik_text: etikText,
    document_context: ctx ?? undefined,
  }, { timeout: 120_000 });
}
