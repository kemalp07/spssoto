import { useEffect } from 'react';
import { DetectedScalesList } from '../analysis/DetectedScalesList';
import { LoadingButton } from '../shared/LoadingButton';
import { useScales } from '../../hooks/useScales';
import { useWizard } from '../../hooks/useWizard';
import { WizardNav } from './StepPlaceholder';

interface ScalesStepProps {
  onNext: () => void;
  onBack: () => void;
}

export function ScalesStep({ onBack }: ScalesStepProps) {
  const { nextStep } = useWizard();
  const {
    detected,
    registryMeta,
    scaleNames,
    isAutoSkipped,
    setScaleNames,
    runDetectScalesEarly,
  } = useScales();

  useEffect(() => {
    void runDetectScalesEarly();
  }, [runDetectScalesEarly]);

  return (
    <>
      <h2 className="wizardTitle">Kullandığınız ölçekler</h2>
      <p className="wizardSubtitle">
        Araştırmanızda kullandığınız ölçek/anket isimlerini yazın. Her birini virgülle ayırın.
      </p>

      {isAutoSkipped ? (
        <div className="alert alertSuccess textSm" role="status">
          Ölçekler otomatik tespit edildi — isterseniz düzenleyip devam edin.
        </div>
      ) : null}

      <DetectedScalesList
        detected={detected}
        registryMatched={registryMeta.registry_matched}
        cutoffs={registryMeta.cutoffs}
      />

      <label className="formLabel" htmlFor="scaleNamesInput">Ölçek adları</label>
      <input
        id="scaleNamesInput"
        className="formInput"
        value={scaleNames}
        placeholder="örn: OYŞTÖ, Gece Yeme Anketi, SBİTO"
        onChange={(e) => setScaleNames(e.target.value)}
      />

      <WizardNav
        onBack={onBack}
        showNext={false}
        hint="Ölçek yoksa boş bırakabilirsiniz"
        extra={(
          <LoadingButton variant="primary" onClick={() => void nextStep()}>
            Devam →
          </LoadingButton>
        )}
      />
    </>
  );
}
