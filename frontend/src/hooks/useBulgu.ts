import { apiCall } from '../api/client';
import { getAppState } from '../lib/storeAccess';

export async function generateBulgu(index: number): Promise<string | null> {
  const state = getAppState();
  const r = state.results.analysis[index];
  if (!r) return null;

  try {
    const data = await apiCall<{ bulgu?: string }>('/ai/bulgu', {
      result: r,
      research_topic: state.wizard.researchTopic || state.results.meta.research_topic || '',
      label_map: state.variables.userLabels,
      approved_cutoffs: state.scales.approvedCutoffs,
      scale_info: state.scales.scaleInfo,
      pdf_context: null,
      all_results: state.results.analysis,
    });
    const text = data.bulgu || 'Bulgu üretilemedi.';
    getAppState().setBulgu(index, text);
    return text;
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'API hatası. ANTHROPIC_API_KEY ayarlı mı?';
    getAppState().setBulgu(index, msg);
    return null;
  }
}

export async function generateAllBulgu(): Promise<void> {
  const state = getAppState();
  const total = state.results.analysis.length;
  if (!total) return;

  getAppState().setBulguLoading(true);
  getAppState().setBulguSummary('');

  try {
    for (let i = 0; i < total; i += 1) {
      if (state.results.bulgular[String(i)]) continue;
      await generateBulgu(i);
    }

    const fresh = getAppState();
    try {
      const data = await apiCall<{ summary?: string }>('/ai/bulgu-summary', {
        results: fresh.results.analysis,
        bulgular: fresh.results.bulgular,
        research_topic: fresh.wizard.researchTopic || fresh.results.meta.research_topic || '',
        hypotheses: fresh.hypotheses.approved.length ? fresh.hypotheses.approved : undefined,
      });
      if (data.summary) getAppState().setBulguSummary(data.summary);
    } catch {
      /* optional */
    }
  } finally {
    getAppState().setBulguLoading(false);
  }
}

export function useBulgu() {
  return { generateBulgu, generateAllBulgu };
}
