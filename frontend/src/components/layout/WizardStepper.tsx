import { useAppStore } from '../../stores/useAppStore';
import {
  SCALES_STEP_INDEX,
  STEPPER_GROUPS,
  STEP_LABELS,
  STEPS,
  WORKFLOW_STEPS,
} from '../../lib/constants';
import type { WizardStepId } from '../../types';

interface WizardStepperProps {
  currentStep: number;
  onStepClick: (stepIdx: number) => void;
}

function getStepperGroupIndex(stepIdx: number): number {
  const stepId = STEPS[stepIdx];
  return STEPPER_GROUPS.findIndex((g) => g.steps.includes(stepId));
}

function getVisitedStepperGroups(stepIdx: number): Set<number> {
  const visited = new Set<number>();
  for (let i = 0; i <= stepIdx; i += 1) {
    visited.add(getStepperGroupIndex(i));
  }
  return visited;
}

function UploadPhaseStepper({ currentStep, onStepClick }: WizardStepperProps) {
  const currentGroup = getStepperGroupIndex(currentStep);
  const visitedGroups = getVisitedStepperGroups(currentStep);

  return (
    <div className="stepperInner">
      <div className="progressSteps" role="list" aria-label="Yükleme adımları">
        {STEPPER_GROUPS.map((group, i) => {
          let state: 'active' | 'done' | 'future' = 'future';
          if (i === currentGroup) state = 'active';
          else if (visitedGroups.has(i)) state = 'done';

          return (
            <div key={group.label} style={{ display: 'contents' }}>
              <button
                type="button"
                className={`stepperItem stepperItemClickable stepperItem${state.charAt(0).toUpperCase()}${state.slice(1)}`}
                title={group.label}
                aria-current={state === 'active' ? 'step' : undefined}
                aria-label={group.label}
                onClick={() => {
                  const target = STEPS.indexOf(group.steps[0]);
                  if (target >= 0) onStepClick(target);
                }}
              >
                <div className="stepperNode">{state === 'done' ? '✓' : i + 1}</div>
                <span className="stepperLabel">{group.label}</span>
              </button>
              {i < STEPPER_GROUPS.length - 1 && (
                <div className={`stepperLine${visitedGroups.has(i + 1) ? ' stepperLineDone' : ''}`} aria-hidden />
              )}
            </div>
          );
        })}
      </div>
      <span className="progressLabel">{STEPPER_GROUPS[currentGroup]?.label ?? ''}</span>
    </div>
  );
}

function WorkflowStepper({ currentStep, onStepClick }: WizardStepperProps) {
  const autoSkippedSteps = useAppStore((s) => s.wizard.autoSkippedSteps);
  const labelsPhaseAutoSkipped = useAppStore((s) => s.wizard.labelsPhaseAutoSkipped);

  return (
    <div className="stepperInner">
      <div className="progressSteps" role="list" aria-label="Analiz adımları">
        {WORKFLOW_STEPS.map((stepName, i) => {
          const idx = STEPS.indexOf(stepName);
          let state: 'active' | 'done' | 'skipped' | 'future' = 'future';
          if (idx === currentStep) state = 'active';
          else if (idx < currentStep) state = autoSkippedSteps.has(stepName) ? 'skipped' : 'done';
          else if (autoSkippedSteps.has(stepName)) state = 'skipped';

          const node = state === 'done' || state === 'skipped' ? '✓' : String(i + 1);
          const autoTag = autoSkippedSteps.has(stepName)
            || (stepName === 'variables' && labelsPhaseAutoSkipped)
            ? <span className="stepperAutoTag">otomatik</span>
            : null;

          return (
            <div key={stepName} style={{ display: 'contents' }}>
              <button
                type="button"
                className={`stepperItem stepperItemClickable stepperItem${state.charAt(0).toUpperCase()}${state.slice(1)}`}
                title={STEP_LABELS[stepName]}
                aria-current={state === 'active' ? 'step' : undefined}
                aria-label={STEP_LABELS[stepName]}
                onClick={() => onStepClick(idx)}
              >
                <div className="stepperNode">{node}</div>
                <span className="stepperLabel">{STEP_LABELS[stepName]}</span>
                {autoTag}
              </button>
              {i < WORKFLOW_STEPS.length - 1 && (() => {
                const nextIdx = STEPS.indexOf(WORKFLOW_STEPS[i + 1]);
                const lineDone = nextIdx <= currentStep || autoSkippedSteps.has(WORKFLOW_STEPS[i + 1]);
                return <div className={`stepperLine${lineDone ? ' stepperLineDone' : ''}`} aria-hidden />;
              })()}
            </div>
          );
        })}
      </div>
      <span className="progressLabel">{STEP_LABELS[STEPS[currentStep] as WizardStepId] ?? ''}</span>
    </div>
  );
}

export function WizardStepper({ currentStep, onStepClick }: WizardStepperProps) {
  if (currentStep === 0) return null;

  return (
    <nav className="wizardProgress" aria-label="Sihirbaz ilerlemesi">
      {currentStep >= SCALES_STEP_INDEX ? (
        <WorkflowStepper currentStep={currentStep} onStepClick={onStepClick} />
      ) : (
        <UploadPhaseStepper currentStep={currentStep} onStepClick={onStepClick} />
      )}
    </nav>
  );
}
