import type { AppState } from '../stores/useAppStore';
import type { WizardStepId } from '../types';
import {
  hasHighConfidenceScales,
  shouldSkipScalesStep,
  shouldSkipTopicStep,
} from '../lib/wizardSkip';

type StoreState = AppState;

export const SKIP_RULES: Partial<Record<WizardStepId, (state: StoreState) => boolean>> = {
  scales: (s) =>
    shouldSkipScalesStep(s.scales.registryMeta.registry_matched, s.scales.detected),
  topic: (s) => shouldSkipTopicStep(s.documents.context?.etik_kurul),
};

export function shouldSkipScalesForState(state: StoreState): boolean {
  return SKIP_RULES.scales?.(state) ?? false;
}

export function hasHighConfidenceForState(state: StoreState): boolean {
  return hasHighConfidenceScales(
    state.scales.registryMeta.registry_matched,
    state.scales.detected,
  );
}
