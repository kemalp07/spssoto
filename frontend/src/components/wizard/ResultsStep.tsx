import { generateAllBulgu } from '../../hooks/useBulgu';
import { useWizard } from '../../hooks/useWizard';
import { useAppStore } from '../../stores/useAppStore';
import { ResultCard } from '../analysis/ResultCard';
import { RegressionPanel } from '../analysis/RegressionPanel';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from './StepPlaceholder';

interface ResultsStepProps {
  onBack: () => void;
}

export function ResultsStep({ onBack }: ResultsStepProps) {
  const { nextStep } = useWizard();
  const results = useAppStore((s) => s.results.analysis);
  const meta = useAppStore((s) => s.results.meta);
  const bulgular = useAppStore((s) => s.results.bulgular);
  const bulguSummary = useAppStore((s) => s.results.bulguSummary);
  const bulguLoading = useAppStore((s) => s.results.bulguLoading);
  const errors = meta.errors as Array<{ analysis?: string; variables?: string; error?: string }> | undefined;

  return (
    <>
      <div className="stepHeader">
        <h2 className="wizardTitle">✅ Analiz Sonuçları</h2>
        <div className="stepActions">
          <LoadingButton
            variant="secondary"
            loading={bulguLoading}
            loadingText="Bulgu yazılıyor..."
            disabled={!results.length}
            onClick={() => void generateAllBulgu()}
          >
            ✨ Tüm Bulguları Yaz
          </LoadingButton>
        </div>
      </div>

      <RegressionPanel />

      {errors?.length ? (
        <div className="alert alertWarn textSm mb2">
          <strong>Şu analizler üretilemedi:</strong>
          <ul className="alertList">
            {errors.map((e, i) => (
              <li key={i}>
                <strong>{e.analysis}</strong> ({e.variables}): {e.error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {meta.intro ? (
        <div className="introBox">{String(meta.intro)}</div>
      ) : null}

      {!results.length ? (
        <div className="emptyState">
          <div className="uploadHero">📭</div>
          <p>Sonuç bulunamadı</p>
        </div>
      ) : (
        results.map((r, i) => (
          <ResultCard key={i} result={r} bulgu={bulgular[String(i)]} />
        ))
      )}

      {bulguSummary ? (
        <div className="introBox introBoxAccent">
          <strong>Genel Değerlendirme</strong>
          <p className="introSummary">{bulguSummary}</p>
        </div>
      ) : null}

      <WizardNav
        onBack={onBack}
        onNext={() => void nextStep()}
        nextLabel="Gözden Geçir →"
        showNext={results.length > 0}
      />
    </>
  );
}
