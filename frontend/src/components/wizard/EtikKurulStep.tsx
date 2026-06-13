import { useState } from 'react';
import { FileDropZone } from '../shared/FileDropZone';
import { ErrorBanner } from '../shared/ErrorBanner';
import { LoadingButton } from '../shared/LoadingButton';
import { useDocuments } from '../../hooks/useDocuments';
import { WizardNav } from './StepPlaceholder';

interface EtikKurulStepProps {
  onNext: () => void;
  onBack: () => void;
  onProceed: () => void | Promise<void>;
}

export function EtikKurulStep({ onBack, onProceed }: EtikKurulStepProps) {
  const [proceeding, setProceeding] = useState(false);
  const {
    etikKurul,
    uploadEtik,
    clearEtik,
    error,
    partialWarn,
    hasEtikLoaded,
  } = useDocuments();

  const handleProceed = async () => {
    if (proceeding) return;
    setProceeding(true);
    try {
      await onProceed();
    } finally {
      setProceeding(false);
    }
  };

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
        disabled={proceeding}
      />

      {proceeding ? (
        <div className="wizardStepBusy" role="status" aria-live="polite">
          <span className="spinner" aria-hidden />
          <div>
            <strong>Lütfen bekleyin</strong>
            <p className="textSm" style={{ margin: '4px 0 0' }}>
              Belgeler ve ölçekler işleniyor, bir sonraki adıma geçiliyor…
            </p>
          </div>
        </div>
      ) : null}

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
        showBack={!proceeding}
        showNext={false}
        extra={(
          <div className="wizardNavActions">
            <LoadingButton
              variant="ghost"
              loading={proceeding}
              loadingText="Bekleyin…"
              disabled={proceeding || etikKurul.loading}
              onClick={() => void handleProceed()}
            >
              Atla →
            </LoadingButton>
            {hasEtikLoaded ? (
              <LoadingButton
                variant="primary"
                loading={proceeding}
                loadingText="Bekleyin…"
                disabled={proceeding || etikKurul.loading}
                onClick={() => void handleProceed()}
              >
                İleri →
              </LoadingButton>
            ) : null}
          </div>
        )}
      />
    </>
  );
}
