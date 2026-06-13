import { FileDropZone } from '../shared/FileDropZone';
import { ErrorBanner } from '../shared/ErrorBanner';
import { LoadingButton } from '../shared/LoadingButton';
import { useFileUpload } from '../../hooks/useFileUpload';
import { WizardNav } from './StepPlaceholder';

interface UploadStepProps {
  onNext: () => void;
  onBack: () => void;
}

export function UploadStep({ onNext, onBack }: UploadStepProps) {
  const {
    uploadFile,
    resetFile,
    retry,
    hasFile,
    fileInfo,
    rowCount,
    columnCount,
    isLoading,
    error,
    status,
  } = useFileUpload();

  const sizeKb = fileInfo ? Math.max(1, Math.round(fileInfo.size / 1024)) : 0;
  const fileMeta = fileInfo
    ? `${sizeKb} KB · ${rowCount} satır · ${columnCount} sütun`
    : undefined;

  return (
    <>
      <div className="uploadHero" aria-hidden>📊</div>
      <h2 className="wizardTitle">StatAI&apos;ya Hoş Geldiniz</h2>
      <p className="wizardSubtitle">
        Akademik analiz ve APA formatlı tablolar için verinizi yükleyin
      </p>

      <FileDropZone
        onFile={uploadFile}
        loading={isLoading}
        uploaded={hasFile}
        fileName={fileInfo?.name}
        fileMeta={fileMeta}
        onReset={resetFile}
      />

      {error && status === 'error' ? (
        <ErrorBanner message={error} onRetry={retry} />
      ) : null}

      <div className="alert alertInfo textSm">
        <div>
          <strong>SPSS:</strong> .sav dosyasını doğrudan yükleyebilirsiniz — değişken etiketleri otomatik okunur.
          CSV export için <em>Save value labels where defined</em> seçeneğini işaretleyin.
        </div>
      </div>

      <WizardNav
        onBack={onBack}
        onNext={onNext}
        showBack={false}
        showNext={false}
        extra={(
          <LoadingButton
            variant="primary"
            loading={isLoading}
            loadingText="Okunuyor..."
            disabled={!hasFile}
            onClick={onNext}
            aria-label="Anket adımına ilerle"
          >
            İleri →
          </LoadingButton>
        )}
      />
    </>
  );
}
