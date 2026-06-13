import type { DocumentContext, EtikKurulParseResult } from '../types';

export interface RegistryMatch {
  id?: string;
  name?: string;
  confidence?: string;
  cols?: string[];
}

export interface DetectedScale {
  name?: string;
  id?: string;
  registry_id?: string;
  registry_confidence?: string;
  source?: string;
  turkish_valid?: boolean;
}

export function hasHighConfidenceScales(
  registryMatched: RegistryMatch[],
  detected: DetectedScale[],
): boolean {
  const regHigh = (registryMatched ?? []).some((m) => m.confidence === 'high');
  const scaleHigh = (detected ?? []).some(
    (s) =>
      s.registry_confidence === 'high'
      || s.source === 'registry'
      || s.source === 'registry+gemini',
  );
  return regHigh || scaleHigh;
}

export function shouldSkipScalesStep(
  registryMatched: RegistryMatch[],
  detected: DetectedScale[],
): boolean {
  return hasHighConfidenceScales(registryMatched, detected) && (detected?.length ?? 0) >= 1;
}

export function scalesFromDetection(detected: DetectedScale[]): string {
  const names = (detected ?? [])
    .map((s) => (s.name ?? '').trim())
    .filter(Boolean);
  return [...new Set(names)].join(', ');
}

export function shouldSkipTopicStep(etik: EtikKurulParseResult | null | undefined): boolean {
  if (!etik || etik.parse_error) return false;
  return (etik.hypotheses?.length ?? 0) >= 1;
}

export function topicFromEtikKurul(etik: EtikKurulParseResult | null | undefined): string {
  if (!etik) return '';
  const hyps = (etik.hypotheses ?? []).filter(Boolean);
  if (hyps.length) return hyps.join('\n');
  return (etik.aim ?? '').trim();
}

export function isTopicStepOptional(context: DocumentContext | null): boolean {
  return !context?.etik_kurul;
}

export function parseScaleNames(raw: string): string[] {
  return raw.split(',').map((s) => s.trim()).filter(Boolean);
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
