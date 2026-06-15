import { apiBlob } from '../api/client';
import { bulgularForApi, bulgularForWordExport } from '../lib/bulgu';
import { buildReviewScaleList } from '../lib/reviewScales';
import { notifyError } from '../lib/notify';
import { scaleMatchingInline } from '../lib/scaleApi';
import { getAppState } from '../lib/storeAccess';
import type { QualityCheckResult } from '../types';

export async function runQualityCheck(): Promise<void> {
  const state = getAppState();
  if (!state.results.analysis.length) return;

  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8765'}/quality-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        results: state.results.analysis,
        bulgular: bulgularForApi(state.results.bulgular),
        intro: state.results.meta.intro || '',
        hypotheses: state.hypotheses.approved.length ? state.hypotheses.approved : undefined,
        n_total: state.parsedData?.length || null,
      }),
    });
    if (res.status === 404) {
      getAppState().setQualityCheck({
        overall: 'sorunlu',
        has_errors: false,
        findings: [{
          severity: 'uyari',
          table_no: null,
          message: "Kalite kontrolü endpoint'i bulunamadı. Backend eski sürüm olabilir.",
        }],
        stale_backend: true,
      });
      return;
    }
    if (!res.ok) return;
    const json = await res.json() as QualityCheckResult;
    getAppState().setQualityCheck(json);
  } catch {
    /* optional */
  }
}

export async function initReviewStep(): Promise<void> {
  const state = getAppState();
  getAppState().setReviewLoading(true);

  try {
    if (!state.scales.matchResults.length && state.parsedData.length) {
      await scaleMatchingInline();
    }
    await runQualityCheck();
    const fresh = getAppState();
    const scales = buildReviewScaleList({
      detectedScales: fresh.scales.detected,
      matchResults: fresh.scales.matchResults,
      scaleInfo: fresh.scales.scaleInfo as Record<string, { full_name?: string }>,
      customLabels: fresh.review.customLabels,
      analysisResults: fresh.results.analysis,
    });
    getAppState().setReviewScalesCache(scales);
  } finally {
    getAppState().setReviewLoading(false);
  }
}

export async function downloadWord(force = false): Promise<void> {
  const state = getAppState();
  const qc = state.review.qualityCheck;
  const hasErrors = qc?.has_errors || (qc?.findings ?? []).some((f) => f.severity === 'hata');
  if (hasErrors && !force && !state.review.forceExport) {
    if (!window.confirm('Tutarlılık kontrolünde HATA bulundu. Yine de Word\'e aktarmak istiyor musunuz?')) {
      return;
    }
    getAppState().setReviewForceExport(true);
  }

  getAppState().setWordExporting(true);
  const exportCustomLabels = Object.fromEntries(
    Object.entries(state.review.customLabels).filter(([k]) => !k.startsWith('scale:')),
  );

  try {
    const methodology = state.plan.catalog
      .filter((t) => (t.cekirdek || t.enabled !== false) && t.decision_log)
      .map((t) => ({
        vars: t.vars,
        decision_log: t.decision_log,
        test: t.test,
        id: t.id,
      }));

    const blob = await apiBlob('/export/word', {
      results: state.results.analysis,
      bulgular: bulgularForWordExport(state.results.bulgular),
      intro: state.results.meta.intro || '',
      label_map: state.variables.userLabels,
      custom_labels: exportCustomLabels,
      custom_titles: state.review.customTitles,
      hypotheses: state.hypotheses.approved.length ? state.hypotheses.approved : undefined,
      methodology: methodology.length ? methodology : undefined,
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'statai_bulgular.docx';
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    notifyError(`Word indirme hatası: ${e instanceof Error ? e.message : 'Bilinmeyen hata'}`);
  } finally {
    getAppState().setWordExporting(false);
  }
}

export function useReview() {
  return { initReviewStep, downloadWord, runQualityCheck };
}
