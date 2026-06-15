import type { AppState } from '../stores/useAppStore';
import type { WizardStepId } from '../types';

type StoreState = AppState;

export const SKIP_RULES: Partial<Record<WizardStepId, (state: StoreState) => boolean>> = {};

export function shouldSkipScalesForState(_state: StoreState): boolean {
  return false;
}

export function hasHighConfidenceForState(state: StoreState): boolean {
  const regHigh = (state.scales.registryMeta.registry_matched ?? []).some(
    (m) => m.confidence === 'high',
  );
  const scaleHigh = (state.scales.detected ?? []).some(
    (s) =>
      s.registry_confidence === 'high'
      || s.source === 'registry'
      || s.source === 'registry+gemini',
  );
  return regHigh || scaleHigh;
}
