import { FileDropZone } from '../shared/FileDropZone';
import { ErrorBanner } from '../shared/ErrorBanner';
import { useDocuments } from '../../hooks/useDocuments';
import { WizardNav } from './StepPlaceholder';

interface AnketStepProps {
  onNext: () => void;
  onBack: () => void;
}

export function AnketStep({ onNext, onBack }: AnketStepProps) {
  const {
    anket,
    uploadAnket,
    clearAnket,
    error,
    hasAnketLoaded,
  } = useDocuments();

  return (
    <>
      <h2 className="wizardTitle">Anket formunuzu yükleyin</h2>
      <p className="wizardSubtitle">Ölçek maddelerini otomatik tanımak için — opsiyonel</p>

      <FileDropZone
        accept=".docx"
        formats={['.docx']}
        title="Anket formunuzu sürükleyin"
        subtitle="Ölçek maddeleri, ters puanlama ve alt boyutlar otomatik tanınır"
        onFile={uploadAnket}
        loading={anket.loading}
        uploaded={hasAnketLoaded}
        fileName={anket.fileName}
        fileMeta={hasAnketLoaded ? 'Yüklendi' : undefined}
        onReset={clearAnket}
      />

      {error ? <ErrorBanner message={error} /> : null}

      {!hasAnketLoaded ? (
        <div className="alert alertInfo textSm">
          Yüklenirse ölçekler %95+ doğrulukla tanınır, ters maddeler otomatik tespit edilir.
        </div>
      ) : null}

      <WizardNav
        onBack={onBack}
        onSkip={onNext}
        showSkip
        showNext={hasAnketLoaded}
        onNext={onNext}
        nextLabel="İleri →"
        skipLabel="Anket formum yok, ölçekleri manuel seçeceğim →"
      />
    </>
  );
}
