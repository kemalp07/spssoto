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
    if (proceeding || etikKurul.loading) return;
    setProceeding(true);
    try {
      await onProceed();
    } finally {
      setProceeding(false);
    }
  };

  const hypothesisMeta = hasEtikLoaded
    ? `${etikKurul.hypothesisCount} hipotez bulundu`
    : undefined;

  return (
    <>
      <h2 className="wizardTitle">Etik kurul raporunuzu yükleyin</h2>
      <p className="wizardSubtitle">Araştırma sorularını otomatik çıkarmak için — opsiyonel</p>

      <FileDropZone
        accept=".docx"
        formats={['.docx']}
        title="Etik kurul raporunuzu sürükleyin"
        subtitle="Hipotezler ve araştırma amacı otomatik çıkarılır"
        onFile={uploadEtik}
        loading={etikKurul.loading}
        uploaded={hasEtikLoaded}
        fileName={etikKurul.fileName}
        fileMeta={hypothesisMeta}
        onReset={clearEtik}
        disabled={proceeding || etikKurul.loading}
      />

      {etikKurul.partial && hasEtikLoaded && !proceeding ? (
        <div className="alert alertWarn textSm" role="status">{partialWarn}</div>
      ) : null}

      {error ? <ErrorBanner message={error} /> : null}

      {!hasEtikLoaded && !proceeding ? (
        <div className="alert alertInfo textSm">
          Yüklenirse araştırma soruları otomatik doldurulur, manuel yazmak gerekmez.
        </div>
      ) : null}

      <WizardNav
        onBack={onBack}
        showBack={!proceeding}
        showSkip={!proceeding}
        onSkip={() => void handleProceed()}
        showNext={false}
        extra={proceeding ? (
          <div className="wizardNavProceeding" role="status" aria-live="polite">
            <span className="spinner" aria-hidden />
            Belgeler işleniyor, lütfen bekleyin…
          </div>
        ) : hasEtikLoaded ? (
          <LoadingButton
            variant="primary"
            disabled={etikKurul.loading}
            onClick={() => void handleProceed()}
          >
            İleri →
          </LoadingButton>
        ) : (
          <span />
        )}
      />
    </>
  );
}
