import { useAppStore } from '../../stores/useAppStore';
import { STEP_LABELS, STEPS } from '../../lib/constants';
import type { WizardStepId } from '../../types';

interface WizardStepperProps {
  currentStep: number;
  maxReachedStep: number;
  onStepClick: (stepIdx: number) => void;
}

export function WizardStepper({ currentStep, maxReachedStep, onStepClick }: WizardStepperProps) {
  const autoSkippedSteps = useAppStore((s) => s.wizard.autoSkippedSteps);

  if (currentStep === 0) return null;

  return (
    <nav className="wizardProgress" aria-label="Adımlar">
      <div className="stepperInner">
        <div className="progressSteps" role="list">
          {STEPS.map((stepId, i) => {
            if (i === 0) return null;

            const isSkipped = autoSkippedSteps.has(stepId as WizardStepId);
            const isActive = i === currentStep;
            const isDone = i < currentStep && !isSkipped;
            const isReachable = i <= maxReachedStep && !isSkipped;

            let state: 'active' | 'done' | 'skipped' | 'future' = 'future';
            if (isActive) state = 'active';
            else if (isDone) state = 'done';
            else if (isSkipped) state = 'skipped';

            const label = STEP_LABELS[stepId as WizardStepId];

            return (
              <div key={stepId} style={{ display: 'contents' }}>
                <button
                  type="button"
                  className={`stepperItem stepperItem${state.charAt(0).toUpperCase()}${state.slice(1)}${isReachable ? ' stepperItemClickable' : ''}`}
                  disabled={!isReachable}
                  aria-current={isActive ? 'step' : undefined}
                  aria-label={`${label}${isSkipped ? ' (otomatik)' : ''}`}
                  title={`${label}${isSkipped ? ' — otomatik geçildi' : ''}`}
                  onClick={() => isReachable && onStepClick(i)}
                >
                  <div className="stepperNode" aria-hidden />
                  <span className="stepperLabel">{label}</span>
                  {isSkipped ? (
                    <span className="stepperAutoTag">otomatik</span>
                  ) : null}
                </button>
                {i < STEPS.length - 1 ? (
                  <div
                    className={`stepperLine${i < currentStep ? ' stepperLineDone' : ''}`}
                    aria-hidden
                  />
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
