import { apiCall } from '../api/client';
import { documentContextPayload, parseScaleNames, scalesFromDetection } from '../lib/wizardSkip';
import { getAppState } from './storeAccess';
import { useAppStore } from '../stores/useAppStore';
import type { DetectScalesResponse, MatchScalesResponse } from '../types';

export async function detectScalesInline(): Promise<void> {
  const state = getAppState();
  const hasReliableScales = state.scales.detected.some(
    (s) => s.registry_confidence === 'high' || s.registry_confidence == null,
  );
  console.log('[DETECT] reliable:', hasReliableScales, 'cols:', state.columns.length);
  if (hasReliableScales || !state.parsedData.length) return;

  try {
    const res = await apiCall<DetectScalesResponse>('/detect-scales', {
      columns: state.columns,
      labels: state.savMetadata.pendingLabels ?? {},
      ...documentContextPayload(state.documents.context, state.documents.sessionId),
    });
    console.log('[DETECT] scales:', res.scales?.map(s => s.name + ' conf:' + s.registry_confidence));
    getAppState().setScaleDetection(res);
  } catch (e) {
    console.error('[DETECT] hata:', e);
    useAppStore.setState((s) => ({
      wizard: { ...s.wizard, detectScalesRan: true },
    }));
  }
}

export async function scaleMatchingInline(): Promise<void> {
  const state = getAppState();
  if (!state.wizard.scaleNames?.trim() && !state.scales.detected.length) return;
  if (!state.parsedData.length) return;

  const scaleNames = parseScaleNames(
    state.wizard.scaleNames?.trim() || scalesFromDetection(state.scales.detected),
  );
  if (!scaleNames.length) return;

  try {
    const res = await apiCall<MatchScalesResponse>('/match-scales', {
      scale_names: scaleNames,
      column_names: state.columns,
    });
    getAppState().setScaleMatches(res);
  } catch {
    getAppState().setScaleMatches({ matches: [], unmatched_columns: [] });
  }
}
