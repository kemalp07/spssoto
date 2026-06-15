import { useCallback } from 'react';
import { STEPS } from '../lib/constants';
import { detectScalesInline } from '../lib/scaleApi';
import { getAppState } from '../lib/storeAccess';
import { useAppStore } from '../stores/useAppStore';
import type { WizardStepId } from '../types';
import {
  enterVariablesStep,
  proceedToPhase2,
  validateVariablesStep,
} from './useVariables';
import { SKIP_RULES } from './wizardSkipRules';

export { SKIP_RULES } from './wizardSkipRules';

export async function resolveForwardStepAsync(fromIdx: number): Promise<number> {
  let next = fromIdx + 1;
  while (next < STEPS.length) {
    const stepId = STEPS[next];
    const state = getAppState();
    const skipRule = SKIP_RULES[stepId as WizardStepId];
    if (skipRule?.(state)) {
      getAppState().markStepSkipped(stepId as WizardStepId);
      next += 1;
      continue;
    }
    return next;
  }
  return STEPS.length - 1;
}

export function resolveBackwardStep(fromIdx: number, autoSkipped: Set<WizardStepId>): number {
  let prev = fromIdx - 1;
  while (prev >= 0 && autoSkipped.has(STEPS[prev])) prev -= 1;
  return Math.max(0, prev);
}

export function useWizard() {
  const currentStep = useAppStore((s) => s.wizard.currentStep);
  const variablesPhase = useAppStore((s) => s.wizard.variablesPhase);
  const autoSkippedSteps = useAppStore((s) => s.wizard.autoSkippedSteps);
  const goToStep = useAppStore((s) => s.goToStep);
  const unmarkStepSkipped = useAppStore((s) => s.unmarkStepSkipped);
  const recomputeAutoSkips = useAppStore((s) => s.recomputeAutoSkips);
  const setLabelsPhaseAutoSkipped = useAppStore((s) => s.setLabelsPhaseAutoSkipped);
  const currentStepId = STEPS[currentStep] ?? 'upload';

  const nextStep = useCallback(async () => {
    const stepId = STEPS[currentStep];

    if (stepId === 'variables' && variablesPhase === 1) {
      await proceedToPhase2(false);
      return;
    }

    if (stepId === 'variables' && variablesPhase === 2) {
      if (!validateVariablesStep()) return;
    }

    const next = await resolveForwardStepAsync(currentStep);
    if (STEPS[next] === 'variables') {
      await enterVariablesStep();
    }
    if (next < STEPS.length) goToStep(next);
  }, [currentStep, variablesPhase, goToStep]);

  const prevStep = useCallback(() => {
    const prev = resolveBackwardStep(currentStep, autoSkippedSteps);
    if (prev < currentStep) goToStep(prev);
  }, [currentStep, autoSkippedSteps, goToStep]);

  const jumpToStep = useCallback(
    async (stepIdx: number) => {
      const stepId = STEPS[stepIdx];
      unmarkStepSkipped(stepId);
      if (stepId === 'variables') {
        setLabelsPhaseAutoSkipped(false);
        const state = getAppState();
        if (!state.wizard.variablesDataReady) {
          await enterVariablesStep();
        }
      }
      goToStep(stepIdx);
    },
    [goToStep, unmarkStepSkipped, setLabelsPhaseAutoSkipped],
  );

  const preparePostUploadWizard = useCallback(async () => {
    await detectScalesInline();
    recomputeAutoSkips();
    goToStep(STEPS.indexOf('oneri'));
  }, [goToStep, recomputeAutoSkips]);

  return {
    currentStep,
    currentStepId,
    stepCount: STEPS.length,
    autoSkippedSteps,
    variablesPhase,
    nextStep,
    prevStep,
    jumpToStep,
    preparePostUploadWizard,
    canGoBack: currentStep > 0,
    canGoForward: currentStep < STEPS.length - 1,
  };
}
