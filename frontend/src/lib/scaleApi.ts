import { apiCall } from '../api/client';
import { documentContextPayload, parseScaleNames } from '../lib/wizardSkip';
import { getAppState } from './storeAccess';
import { useAppStore } from '../stores/useAppStore';
import type { DetectScalesResponse, MatchScalesResponse } from '../types';

export async function detectScalesInline(): Promise<void> {
  const state = getAppState();
  if (state.wizard.detectScalesRan || !state.parsedData.length) return;

  try {
    const res = await apiCall<DetectScalesResponse>('/detect-scales', {
      columns: state.columns,
      labels: state.savMetadata.pendingLabels ?? {},
      ...documentContextPayload(state.documents.context, state.documents.sessionId),
    });
    getAppState().setScaleDetection(res);
  } catch {
    useAppStore.setState((s) => ({
      wizard: { ...s.wizard, detectScalesRan: true },
    }));
  }
}

export async function scaleMatchingInline(): Promise<void> {
  const state = getAppState();
  const scaleNames = parseScaleNames(state.wizard.scaleNames);
  if (!scaleNames.length || !state.parsedData.length) return;

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
