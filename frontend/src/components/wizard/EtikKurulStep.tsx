import { FileDropZone } from '../shared/FileDropZone';
import { ErrorBanner } from '../shared/ErrorBanner';
import { LoadingButton } from '../shared/LoadingButton';
import { useDocuments } from '../../hooks/useDocuments';
import { WizardNav } from './StepPlaceholder';

interface EtikKurulStepProps {
  onNext: () => void;
  onBack: () => void;
  onProceed: () => void;
}

export function EtikKurulStep({ onBack, onProceed }: EtikKurulStepProps) {
  const {
    etikKurul,
    uploadEtik,
    clearEtik,
    error,
    partialWarn,
    hasEtikLoaded,
  } = useDocuments();

  const skip = onProceed;

  return (
    <>
      <h2 className="wizardTitle">Etik kurul raporunuzu yükleyin</h2>
      <p className="wizardSubtitle">Araştırma sorularını otomatik çıkarmak için — opsiyonel</p>

      <FileDropZone
        accept=".docx"
        formats={['.docx']}
        icon="📄"
        title="Etik kurul raporunuzu sürükleyin"
        subtitle="Hipotezler ve araştırma amacı otomatik çıkarılır"
        onFile={uploadEtik}
        loading={etikKurul.loading}
        uploaded={hasEtikLoaded}
        fileName={etikKurul.fileName}
        fileMeta={hasEtikLoaded ? `${etikKurul.hypothesisCount} hipotez bulundu` : undefined}
        onReset={clearEtik}
      />

      {etikKurul.partial && hasEtikLoaded ? (
        <div className="alert alertWarn textSm" role="status">{partialWarn}</div>
      ) : null}

      {hasEtikLoaded ? (
        <div className="alert alertSuccess textSm" role="status">
          {etikKurul.hypothesisCount} hipotez bulundu
        </div>
      ) : null}

      {error ? <ErrorBanner message={error} /> : null}

      <div className="alert alertInfo textSm">
        Yüklenirse araştırma soruları otomatik doldurulur, manuel yazmak gerekmez.
      </div>

      <WizardNav
        onBack={onBack}
        showNext={false}
        extra={(
          <div className="wizardNavActions">
            <button type="button" className="btn btnGhost" onClick={skip}>
              Atla →
            </button>
            {hasEtikLoaded ? (
              <LoadingButton variant="primary" onClick={onProceed}>
                İleri →
              </LoadingButton>
            ) : null}
          </div>
        )}
      />
    </>
  );
}
