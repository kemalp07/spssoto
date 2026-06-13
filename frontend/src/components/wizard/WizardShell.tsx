import { useWizard } from '../../hooks/useWizard';
import { STEP_ICONS, STEPS } from '../../lib/constants';
import { WizardStepper } from '../layout/WizardStepper';
import { AnketStep } from './AnketStep';
import { EtikKurulStep } from './EtikKurulStep';
import { PlanStep, ResultsStep, ReviewStep, VariablesStep } from './steps';
import { ScalesStep } from './ScalesStep';
import { TopicStep } from './TopicStep';
import { UploadStep } from './UploadStep';

export function WizardShell() {
  const {
    currentStep,
    currentStepId,
    nextStep,
    prevStep,
    jumpToStep,
    preparePostUploadWizard,
    canGoBack,
    canGoForward,
  } = useWizard();

  const nav = {
    onNext: () => void nextStep(),
    onBack: prevStep,
  };

  const renderStep = () => {
    switch (currentStepId) {
      case 'upload':
        return <UploadStep {...nav} />;
      case 'anket':
        return <AnketStep {...nav} />;
      case 'etikkurul':
        return <EtikKurulStep {...nav} onProceed={preparePostUploadWizard} />;
      case 'scales':
        return <ScalesStep {...nav} />;
      case 'topic':
        return <TopicStep {...nav} />;
      case 'variables':
        return <VariablesStep onBack={prevStep} />;
      case 'plan':
        return <PlanStep onBack={prevStep} />;
      case 'results':
        return <ResultsStep onBack={prevStep} />;
      case 'review':
        return <ReviewStep onBack={prevStep} />;
      default:
        return null;
    }
  };

  const wide = ['variables', 'plan', 'results', 'review'].includes(currentStepId);
  const center = ['upload', 'anket', 'etikkurul', 'scales', 'topic'].includes(currentStepId);

  return (
    <>
      <WizardStepper currentStep={currentStep} onStepClick={(idx) => void jumpToStep(idx)} />
      <div className="container">
        <div className="wizardShell">
          <article
            className={`wizardCard${wide ? ' wizardCardWide' : ''}${center ? ' wizardCardCenter' : ''}`}
            aria-label={`${STEP_ICONS[currentStepId]} ${STEPS[currentStep]}`}
          >
            {renderStep()}
          </article>
        </div>
        <p className="stepMeta" style={{ textAlign: 'center', marginTop: 'var(--space-2)' }}>
          Adım {currentStep + 1} / {STEPS.length}
          {!canGoBack && !canGoForward ? '' : ` · ${currentStepId}`}
        </p>
      </div>
    </>
  );
}
