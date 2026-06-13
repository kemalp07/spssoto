import { useEffect, useState } from 'react';
import { backToPhase1, enterVariablesStep, proceedToPhase2 } from '../../hooks/useVariables';
import { useWizard } from '../../hooks/useWizard';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from '../wizard/StepPlaceholder';
import { LabelEditor } from '../variables/LabelEditor';
import { MissingCodesEditor } from '../variables/MissingCodesEditor';
import { ScaleMatchPanel } from '../variables/ScaleMatchPanel';
import { SelectionGrid } from '../variables/SelectionGrid';

interface VariablesStepProps {
  onBack: () => void;
}

export function VariablesStep({ onBack }: VariablesStepProps) {
  const { nextStep, variablesPhase } = useWizard();
  const labelsSkipped = useAppStore((s) => s.wizard.labelsPhaseAutoSkipped);
  const fileInfoText = useAppStore((s) => s.variables.fileInfoText);
  const catColumns = useAppStore((s) => s.variables.catColumns);
  const contColumns = useAppStore((s) => s.variables.contColumns);
  const recommendations = useAppStore((s) => s.variables.lastRecommendations);
  const dataReady = useAppStore((s) => s.wizard.variablesDataReady);
  const [classifying, setClassifying] = useState(false);

  useEffect(() => {
    if (!dataReady) void enterVariablesStep();
  }, [dataReady]);

  const handleClassify = async () => {
    setClassifying(true);
    try {
      await proceedToPhase2(false);
    } finally {
      setClassifying(false);
    }
  };

  if (!dataReady) {
    return (
      <>
        <h2 className="wizardTitle">🔢 Değişkenler</h2>
        <p className="wizardSubtitle">Veriler hazırlanıyor…</p>
      </>
    );
  }

  if (variablesPhase === 1) {
    return (
      <>
        <h2 className="wizardTitle">🏷️ Değişken İsimleri</h2>
        <p className="wizardSubtitle">
          Her değişkene anlaşılır bir Türkçe isim verin.
          Bu isimler analiz sonuçlarında ve bulgularda kullanılacak.
        </p>
        {labelsSkipped ? (
          <div className="alert alertSuccess textSm" role="status">
            Tüm değişken etiketleri otomatik okundu.
          </div>
        ) : null}
        <LabelEditor />
        <WizardNav
          onBack={onBack}
          showNext={false}
          extra={(
            <LoadingButton
              variant="primary"
              loading={classifying}
              loadingText="Sınıflandırılıyor..."
              onClick={() => void handleClassify()}
            >
              Sınıflandır →
            </LoadingButton>
          )}
        />
      </>
    );
  }

  return (
    <>
      <h2 className="wizardTitle">🔢 Değişkenleri Onaylayın</h2>
      <p className="wizardSubtitle">
        AI değişkenleri sınıflandırdı. Kontrol edin, yanlış olanları düzeltin.
      </p>
      {fileInfoText ? (
        <p className="textSm textMuted mb2">{fileInfoText}</p>
      ) : null}
      <MissingCodesEditor />
      <ScaleMatchPanel />
      <SelectionGrid
        title="Gruplandırma değişkenleri"
        type="cat"
        columns={catColumns}
        recommendations={recommendations}
      />
      <SelectionGrid
        title="Analiz değişkenleri (bağımlı)"
        type="cont"
        columns={contColumns}
        recommendations={recommendations}
      />
      <WizardNav
        onBack={backToPhase1}
        backLabel="← Etiketleri Düzenle"
        onNext={() => void nextStep()}
        nextLabel="Analiz Planı →"
      />
    </>
  );
}
