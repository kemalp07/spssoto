import { apiCall } from '../api/client';
import { buildHypothesisPayload, buildPlanPayload } from '../lib/analysisPayload';
import { documentContextPayload } from '../lib/wizardSkip';
import { useAppStore } from '../stores/useAppStore';
import type { ParseHypothesesResponse, PlanTestsResponse } from '../types';

export async function loadHypothesisReview(): Promise<void> {
  const state = useAppStore.getState();
  if (!state.wizard.researchTopic.trim()) return;

  useAppStore.setState((s) => ({
    hypotheses: { ...s.hypotheses, loading: true },
    plan: { ...s.plan, error: null },
  }));

  try {
    const res = await apiCall<ParseHypothesesResponse>('/parse-hypotheses', {
      ...buildHypothesisPayload(state),
      ...documentContextPayload(state.documents.context, state.documents.sessionId),
    });
    useAppStore.getState().applyHypothesisParse(res);
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Bilinmeyen hata';
    useAppStore.setState((s) => ({
      hypotheses: { ...s.hypotheses, loading: false },
      plan: { ...s.plan, error: msg },
    }));
  }
}

export async function loadAnalysisPlan(): Promise<void> {
  const state = useAppStore.getState();
  if (!state.wizard.researchTopic.trim()) return;

  useAppStore.setState((s) => ({
    hypotheses: { ...s.hypotheses, planLoading: true },
    plan: { ...s.plan, error: null },
  }));

  try {
    const fresh = useAppStore.getState();
    const res = await apiCall<PlanTestsResponse>('/plan-tests', {
      ...buildPlanPayload(fresh),
      ...documentContextPayload(fresh.documents.context, fresh.documents.sessionId),
    });
    useAppStore.getState().applyPlanResponse(res);
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Bilinmeyen hata';
    useAppStore.setState((s) => ({
      hypotheses: { ...s.hypotheses, planLoading: false },
      plan: { ...s.plan, error: msg },
    }));
  }
}

export function approveHypothesesAndLoadPlan(): void {
  useAppStore.getState().setHypothesesApproved(true);
  void loadAnalysisPlan();
}

export function skipHypothesisReviewAndLoadPlan(): void {
  useAppStore.getState().skipHypothesisReview();
  void loadAnalysisPlan();
}

export function usePlan() {
  return {
    loadHypothesisReview,
    loadAnalysisPlan,
    approveHypothesesAndLoadPlan,
    skipHypothesisReviewAndLoadPlan,
  };
}
