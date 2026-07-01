import { apiCall } from '../api/client';
import { bulgularForApi } from '../lib/bulgu';
import { getAppState } from '../lib/storeAccess';

export async function generateBulgu(index: number): Promise<string | null> {
  const state = getAppState();
  const existing = state.results.bulgular[String(index)];
  if (existing?.isLocked) return existing.text;
  if (existing?.text) return existing.text;

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

export async function regenerateBulguAt(index: number): Promise<void> {
  const state = getAppState();
  const existing = state.results.bulgular[String(index)];
  if (existing?.isLocked) return;

  const r = state.results.analysis[index];
  if (!r) return;

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
    const nextVersion = (existing?.version ?? 0) + 1;
    getAppState().regenerateBulgu(index, text);
    getAppState().showToast(
      `Bulgu v${nextVersion} oluşturuldu. Önceki versiyon geçmişte.`,
      'success',
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'API hatası. ANTHROPIC_API_KEY ayarlı mı?';
    getAppState().showToast(msg, 'error');
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
      const existing = getAppState().results.bulgular[String(i)];
      if (existing?.isLocked) continue;
      if (existing?.text) continue;
      await generateBulgu(i);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    const fresh = getAppState();
    try {
      const data = await apiCall<{ summary?: string }>('/ai/bulgu-summary', {
        results: fresh.results.analysis,
        bulgular: bulgularForApi(fresh.results.bulgular),
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
  return { generateBulgu, generateAllBulgu, regenerateBulguAt };
}
