import { useAppStore } from '../../stores/useAppStore';
import { isTopicStepOptional } from '../../lib/wizardSkip';
import { useWizard } from '../../hooks/useWizard';
import { WizardNav } from './StepPlaceholder';

interface TopicStepProps {
  onNext: () => void;
  onBack: () => void;
}

export function TopicStep({ onBack }: TopicStepProps) {
  const { nextStep } = useWizard();
  const researchTopic = useAppStore((s) => s.wizard.researchTopic);
  const setResearchTopic = useAppStore((s) => s.setResearchTopic);
  const autoSkipped = useAppStore((s) => s.wizard.autoSkippedSteps);
  const context = useAppStore((s) => s.documents.context);
  const optional = isTopicStepOptional(context);

  const skipTopic = () => {
    void nextStep();
  };

  return (
    <>
      <h2 className="wizardTitle">Araştırma soruları</h2>
      <p className="wizardSubtitle">
        Her satıra bir soru yazabilirsiniz; hipotez eşlemesi plan adımında yapılır.
        {optional ? ' (Opsiyonel)' : ''}
      </p>

      {autoSkipped.has('topic') ? (
        <div className="alert alertSuccess textSm" role="status">
          Etik kurul raporundan otomatik dolduruldu — isterseniz düzenleyin.
        </div>
      ) : null}

      <label className="formLabel" htmlFor="researchTopic">Araştırma soruları / hipotezler</label>
      <textarea
        id="researchTopic"
        className="formTextarea"
        rows={5}
        value={researchTopic}
        placeholder="Araştırma sorularınızı yazın; her satıra bir soru yazabilirsiniz."
        onChange={(e) => setResearchTopic(e.target.value)}
      />

      <WizardNav
        onBack={onBack}
        onSkip={optional ? skipTopic : undefined}
        showSkip={optional}
        showNext
        onNext={() => void nextStep()}
        nextLabel="Devam →"
      />
    </>
  );
}
