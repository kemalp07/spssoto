import type {
  AnketParseResult,
  DocumentContext,
  EtikKurulParseResult,
  UploadDocumentsResponse,
} from '../types';

export const DOC_PARTIAL_WARN =
  'Dosya okunabildi ama bazı bilgiler çıkarılamadı — devam edebilirsiniz';

export function countAnketItems(anket: AnketParseResult | null | undefined): number {
  if (!anket || anket.parse_error) return 0;
  return (anket.sections ?? []).reduce(
    (n, sec) => n + ((sec.items ?? []).length),
    0,
  );
}

export function countEtikHypotheses(etik: EtikKurulParseResult | null | undefined): number {
  if (!etik || etik.parse_error) return 0;
  return (etik.hypotheses ?? []).length;
}

export function buildDocumentContext(response: UploadDocumentsResponse): DocumentContext {
  return response.document_context ?? {
    anket: response.anket ?? null,
    etik_kurul: response.etik_kurul ?? null,
  };
}

export function documentContextPayload(
  context: DocumentContext | null,
  sessionId: string | null,
): { document_context?: DocumentContext; session_id?: string } {
  const out: { document_context?: DocumentContext; session_id?: string } = {};
  if (context) out.document_context = context;
  if (sessionId) out.session_id = sessionId;
  return out;
}
