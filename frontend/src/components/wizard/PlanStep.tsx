import { useEffect, type ReactNode } from 'react';
import { runAnalysisFromPlan } from '../../hooks/useAnalysis';
import { loadAnalysisPlan } from '../../hooks/usePlan';
import { getAppState } from '../../lib/storeAccess';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from '../wizard/StepPlaceholder';
import { PlanCatalogView } from '../plan/PlanCatalogView';
import type { PlanProfileId } from '../../types';

interface PlanStepProps {
  onBack: () => void;
}

export function PlanStep({ onBack }: PlanStepProps) {
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
    if (!catalog.length) {
      const state = getAppState();
      if (!state.hypotheses.isApproved) {
        state.setHypothesesApproved(true);
      }
      void loadAnalysisPlan();
    }
  }, [catalog.length, researchTopic]);

  const handleProfileChange = (profile: PlanProfileId) => {
    const userTouched = getAppState().plan.userTouched;
    if (userTouched && !window.confirm('Seçimleriniz sıfırlanacak, devam?')) return;
    setProfile(profile);
    void loadAnalysisPlan();
  };

  let body: ReactNode;
  if (!researchTopic.trim()) {
    body = (
      <p className="textSm textMuted">
        Araştırma soruları boş. Önceki adımda en az bir soru girin.
      </p>
    );
  } else if (planLoading) {
    body = (
      <div className="planLoadingState">
        <span className="spinner" style={{ width: 24, height: 24, borderWidth: 2 }} aria-hidden />
        <p className="planLoadingText">Test planı hazırlanıyor...</p>
      </div>
    );
  } else if (error && !catalog.length) {
    body = (
      <div className="alert alertWarn textSm">
        Test planı oluşturulamadı.
        <div className="textXs mt2">{error}</div>
        <button
          type="button"
          className="btn btnSecondary mt2"
          onClick={() => void loadAnalysisPlan()}
        >
          Tekrar dene
        </button>
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
      <p className="wizardSubtitle">
        Önerilen testleri onaylayın; uygun olanlar seçili gelir, olası olanları işaretleyerek ekleyebilirsiniz.
      </p>
      {body}
      {catalog.length > 0 ? (
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
