import { EXCLUDE_PATTERNS } from '../lib/constants';
import {
  checkRequiredLabels,
  getMissingLabelColumns,
  shouldSkipLabelsPhase,
} from '../lib/labels';
import { runAIClassify } from './useAnalysis';
import { useAppStore } from '../stores/useAppStore';

export async function enterVariablesStep(): Promise<void> {
  const state = useAppStore.getState();
  if (!state.wizard.variablesDataReady) {
    await state.loadVariablesStepData();
  }

  const fresh = useAppStore.getState();
  const skipLabels = shouldSkipLabelsPhase(
    fresh.columns,
    fresh.variables.userLabels,
    fresh.savMetadata.pendingLabels,
  );

  if (skipLabels) {
    useAppStore.getState().setLabelsPhaseAutoSkipped(true);
    useAppStore.getState().setVariablesPhase(2);
    await proceedToPhase2(true);
  } else {
    useAppStore.getState().setVariablesPhase(1);
  }
}

export async function proceedToPhase2(silent = false): Promise<boolean> {
  await runAIClassify();

  const state = useAppStore.getState();
  const missing = getMissingLabelColumns(
    state.columns,
    state.variables.userLabels,
    state.savMetadata.pendingLabels,
  );

  if (missing.length > 0 && !silent) {
    window.alert(`Devam etmeden önce şu değişkenlere Türkçe isim verin: ${missing.join(', ')}`);
    return false;
  }

  useAppStore.getState().setVariablesPhase(2);
  return true;
}

export function backToPhase1(): void {
  useAppStore.getState().setVariablesPhase(1);
}

export function validateVariablesStep(): boolean {
  const state = useAppStore.getState();
  if (state.wizard.variablesPhase === 1) return false;

  if (!state.variables.selectedCat.size && !state.variables.selectedCont.size) {
    window.alert('En az bir değişken seçmelisiniz.');
    return false;
  }

  const nonItems = new Set(
    state.columns.filter(
      (col) =>
        !state.variables.aiExcluded.has(col)
        && !EXCLUDE_PATTERNS.some((p) => p.test(col)),
    ),
  );

  const missingLabels = checkRequiredLabels(
    state.variables.selectedCat,
    state.variables.selectedCont,
    state.variables.userLabels,
    nonItems,
  );

  if (missingLabels.length > 0) {
    window.alert(`Devam etmeden önce şu değişkenlere Türkçe isim verin: ${missingLabels.join(', ')}`);
    return false;
  }

  return true;
}

export function useVariables() {
  return {
    enterVariablesStep,
    proceedToPhase2,
    backToPhase1,
    validateVariablesStep,
  };
}
