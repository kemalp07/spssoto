import { useEffect, useRef, useState } from 'react';
import { useWizard } from '../../hooks/useWizard';
import { fetchAnalizOneri } from '../../lib/analizOneriApi';
import { detectScalesInline, scaleMatchingInline } from '../../lib/scaleApi';
import { useAppStore } from '../../stores/useAppStore';
import { ErrorBanner } from '../shared/ErrorBanner';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from './StepPlaceholder';

interface OneriStepProps {
  onBack: () => void;
}

export function OneriStep({ onBack }: OneriStepProps) {
  const { nextStep } = useWizard();
  const [proceeding, setProceeding] = useState(false);
  const loading = useAppStore((s) => s.oneri.loading);
  const error = useAppStore((s) => s.oneri.error);
  const oneri = useAppStore((s) => s.oneri.data);
  const fetched = useAppStore((s) => s.oneri.fetched);
  const setOneriLoading = useAppStore((s) => s.setOneriLoading);
  const setOneriError = useAppStore((s) => s.setOneriError);
  const applyAnalizOneriResponse = useAppStore((s) => s.applyAnalizOneriResponse);
  const applyAnalizOneriEffects = useAppStore((s) => s.applyAnalizOneriEffects);
  const started = useRef(false);

  useEffect(() => {
    if (fetched || started.current) return;
    started.current = true;
    setOneriLoading(true);
    void fetchAnalizOneri()
      .then((response) => applyAnalizOneriResponse(response))
      .catch((err: Error) => setOneriError(err.message || 'Analiz önerisi alınamadı'));
  }, [
    fetched,
    setOneriLoading,
    setOneriError,
    applyAnalizOneriResponse,
  ]);

  const handleNext = async () => {
    if (proceeding || loading) return;
    setProceeding(true);
    try {
      applyAnalizOneriEffects();
      await detectScalesInline();
      await scaleMatchingInline();
      await nextStep();
    } finally {
      setProceeding(false);
    }
  };

  const nextButton = (
    <LoadingButton
      variant="primary"
      loading={proceeding}
      loadingText="Hazırlanıyor..."
      disabled={loading && !oneri}
      onClick={() => void handleNext()}
    >
      Değişkenlere Git →
    </LoadingButton>
  );

  if (loading && !oneri) {
    return (
      <>
        <h2 className="wizardTitle">Analiz Planı Önerisi</h2>
        <p className="wizardSubtitle">Anket ve etik kurul belgeleriniz inceleniyor…</p>
        <div className="planLoadingState">
          <span className="spinner" style={{ width: 24, height: 24, borderWidth: 2 }} aria-hidden />
          <p className="planLoadingText">Önerilen analiz planı hazırlanıyor…</p>
        </div>
        <WizardNav onBack={onBack} showNext={false} extra={<span />} />
      </>
    );
  }

  return (
    <>
      <h2 className="wizardTitle">Analiz Planı Önerisi</h2>
      <p className="wizardSubtitle">
        Anket ve etik kurul belgelerinize göre önerilen analizler
      </p>

      {error ? <ErrorBanner message={error} /> : null}

      <div className="oneriCard">
        {oneri?.ozet ? (
          <p className="oneriOzet">{oneri.ozet}</p>
        ) : null}

        {(oneri?.gerekceler?.length ?? 0) > 0 ? (
          <>
            <h4 className="oneriSectionTitle">Önerilen analizler</h4>
            {oneri!.gerekceler!.map((g, i) => (
              <div key={`${g.analiz ?? 'g'}-${i}`} className="oneriItem">
                <strong>{g.analiz}</strong>
                <p className="oneriNeden">{g.neden}</p>
              </div>
            ))}
          </>
        ) : null}

        {(oneri?.olcekler?.length ?? 0) > 0 ? (
          <div className="oneriOlcekler">
            <span className="label">Tespit edilen ölçekler:</span>
            {oneri!.olcekler!.map((o) => (
              <span key={o.ad} className="olcekBadge">{o.ad}</span>
            ))}
          </div>
        ) : null}
      </div>

      <WizardNav
        onBack={onBack}
        showNext={false}
        extra={nextButton}
      />
    </>
  );
}
