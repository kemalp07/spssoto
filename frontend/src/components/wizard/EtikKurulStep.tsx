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
        fileMeta={hasEtikLoaded ? 'Yüklendi' : undefined}
        onReset={clearEtik}
        disabled={proceeding || etikKurul.loading}
      />

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
        skipLabel="Etik kurul belgem yok, devam et →"
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
