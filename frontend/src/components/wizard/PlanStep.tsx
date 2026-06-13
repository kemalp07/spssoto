import { useEffect, type ReactNode } from 'react';
import { runAnalysisFromPlan } from '../../hooks/useAnalysis';
import { loadAnalysisPlan, loadHypothesisReview } from '../../hooks/usePlan';
import { getAppState } from '../../lib/storeAccess';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from '../wizard/StepPlaceholder';
import { HypothesisReview } from '../plan/HypothesisReview';
import { PlanCatalogView } from '../plan/PlanCatalogView';
import type { PlanProfileId } from '../../types';

interface PlanStepProps {
  onBack: () => void;
}

export function PlanStep({ onBack }: PlanStepProps) {
  const isApproved = useAppStore((s) => s.hypotheses.isApproved);
  const loading = useAppStore((s) => s.hypotheses.loading);
  const planLoading = useAppStore((s) => s.hypotheses.planLoading);
  const analyzing = useAppStore((s) => s.results.analyzing);
  const catalog = useAppStore((s) => s.plan.catalog);
  const error = useAppStore((s) => s.plan.error);
  const researchTopic = useAppStore((s) => s.wizard.researchTopic);
  const toggleItem = useAppStore((s) => s.togglePlanCatalogItem);
  const toggleTier = useAppStore((s) => s.togglePlanTier);
  const setProfile = useAppStore((s) => s.setPlanProfile);
  const setFilter = useAppStore((s) => s.setPlanActiveFilter);

  useEffect(() => {
    if (!researchTopic.trim()) return;
    if (!isApproved) void loadHypothesisReview();
    else if (!catalog.length) void loadAnalysisPlan();
  }, [isApproved, catalog.length, researchTopic]);

  const handleProfileChange = (profile: PlanProfileId) => {
    const userTouched = getAppState().plan.userTouched;
    if (userTouched && !window.confirm('Seçimleriniz sıfırlanacak, devam?')) return;
    setProfile(profile);
    void loadHypothesisReview();
  };

  let body: ReactNode;
  if (!researchTopic.trim()) {
    body = <p className="textSm textMuted">Araştırma soruları boş. Önceki adımda en az bir soru girin.</p>;
  } else if (loading || planLoading) {
    body = (
      <div className="emptyState">
        <div className="uploadHero">⏳</div>
        <p>{loading ? 'Araştırma soruları analiz ediliyor...' : 'Test planı hazırlanıyor...'}</p>
      </div>
    );
  } else if (error && !catalog.length && !isApproved) {
    body = (
      <div className="alert alertWarn textSm">
        Hipotez eşlemesi yapılamadı. Sorularınızı kontrol edin.
        <div className="textXs mt2">{error}</div>
        <button type="button" className="btn btnSecondary mt2" onClick={() => loadHypothesisReview()}>
          Tekrar dene
        </button>
      </div>
    );
  } else if (!isApproved) {
    body = <HypothesisReview />;
  } else if (error && !catalog.length) {
    body = (
      <div className="alert alertWarn textSm">
        Test planı oluşturulamadı. Araştırma amacını ve backend ayarlarını kontrol edin.
        <div className="textXs mt2">{error}</div>
      </div>
    );
  } else if (!catalog.length) {
    body = <p className="textSm textMuted">Analiz planı oluşturulamadı.</p>;
  } else {
    body = (
      <PlanCatalogView
        onToggleItem={toggleItem}
        onToggleTier={toggleTier}
        onSetProfile={handleProfileChange}
        onFilterHypothesis={setFilter}
      />
    );
  }

  return (
    <>
      <h2 className="wizardTitle">📊 Analiz Planı</h2>
      <p className="wizardSubtitle">Yapılacak testleri onaylayın veya istediğinizi kapatın.</p>
      {body}
      {isApproved && catalog.length ? (
        <WizardNav
          onBack={onBack}
          showNext={false}
          extra={(
            <LoadingButton
              variant="primary"
              loading={analyzing}
              loadingText="Analiz ediliyor..."
              onClick={() => void runAnalysisFromPlan()}
            >
              🔬 Analiz Et
            </LoadingButton>
          )}
        />
      ) : (
        <WizardNav onBack={onBack} showNext={false} />
      )}
    </>
  );
}
