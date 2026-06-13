import { EXCLUDE_PATTERNS } from '../lib/constants';
import {
  checkRequiredLabels,
  getMissingLabelColumns,
  shouldSkipLabelsPhase,
} from '../lib/labels';
import { notifyError } from '../lib/notify';
import { runAIClassify } from './useAnalysis';
import { getAppState } from '../lib/storeAccess';

export async function enterVariablesStep(): Promise<void> {
  const state = getAppState();
  if (!state.wizard.variablesDataReady) {
    await state.loadVariablesStepData();
  }

  const fresh = getAppState();
  const skipLabels = shouldSkipLabelsPhase(
    fresh.columns,
    fresh.variables.userLabels,
    fresh.savMetadata.pendingLabels,
  );

  if (skipLabels) {
    getAppState().setLabelsPhaseAutoSkipped(true);
    getAppState().setVariablesPhase(2);
    await proceedToPhase2(true);
  } else {
    getAppState().setVariablesPhase(1);
  }
}

export async function proceedToPhase2(silent = false): Promise<boolean> {
  await runAIClassify();

  const state = getAppState();
  const missing = getMissingLabelColumns(
    state.columns,
    state.variables.userLabels,
    state.savMetadata.pendingLabels,
  );

  if (missing.length > 0 && !silent) {
    notifyError(`Devam etmeden önce şu değişkenlere Türkçe isim verin: ${missing.join(', ')}`);
    return false;
  }

  getAppState().setVariablesPhase(2);
  return true;
}

export function backToPhase1(): void {
  getAppState().setVariablesPhase(1);
}

export function validateVariablesStep(): boolean {
  const state = getAppState();
  if (state.wizard.variablesPhase === 1) return false;

  if (!state.variables.selectedCat.size && !state.variables.selectedCont.size) {
    notifyError('En az bir değişken seçmelisiniz.');
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
    notifyError(`Devam etmeden önce şu değişkenlere Türkçe isim verin: ${missingLabels.join(', ')}`);
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
