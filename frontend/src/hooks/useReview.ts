import { apiBlob } from '../api/client';
import { buildReviewScaleList } from '../lib/reviewScales';
import { scaleMatchingInline } from '../lib/scaleApi';
import { useAppStore } from '../stores/useAppStore';
import type { QualityCheckResult } from '../types';

export async function runQualityCheck(): Promise<void> {
  const state = useAppStore.getState();
  if (!state.results.analysis.length) return;

  try {
    const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8765'}/quality-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        results: state.results.analysis,
        bulgular: state.results.bulgular,
        intro: state.results.meta.intro || '',
        hypotheses: state.hypotheses.approved.length ? state.hypotheses.approved : undefined,
        n_total: state.parsedData?.length || null,
      }),
    });
    if (res.status === 404) {
      useAppStore.getState().setQualityCheck({
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
    useAppStore.getState().setQualityCheck(json);
  } catch {
    /* optional */
  }
}

export async function initReviewStep(): Promise<void> {
  const state = useAppStore.getState();
  useAppStore.getState().setReviewLoading(true);

  try {
    if (!state.scales.matchResults.length && state.parsedData.length) {
      await scaleMatchingInline();
    }
    await runQualityCheck();
    const fresh = useAppStore.getState();
    const scales = buildReviewScaleList({
      detectedScales: fresh.scales.detected,
      matchResults: fresh.scales.matchResults,
      scaleInfo: fresh.scales.scaleInfo as Record<string, { full_name?: string }>,
      customLabels: fresh.review.customLabels,
      analysisResults: fresh.results.analysis,
    });
    useAppStore.getState().setReviewScalesCache(scales);
  } finally {
    useAppStore.getState().setReviewLoading(false);
  }
}

export async function downloadWord(force = false): Promise<void> {
  const state = useAppStore.getState();
  const qc = state.review.qualityCheck;
  const hasErrors = qc?.has_errors || (qc?.findings ?? []).some((f) => f.severity === 'hata');
  if (hasErrors && !force && !state.review.forceExport) {
    if (!window.confirm('Tutarlılık kontrolünde HATA bulundu. Yine de Word\'e aktarmak istiyor musunuz?')) {
      return;
    }
    useAppStore.getState().setReviewForceExport(true);
  }

  useAppStore.getState().setWordExporting(true);
  const exportCustomLabels = Object.fromEntries(
    Object.entries(state.review.customLabels).filter(([k]) => !k.startsWith('scale:')),
  );

  try {
    const blob = await apiBlob('/export/word', {
      results: state.results.analysis,
      bulgular: state.results.bulgular,
      intro: state.results.meta.intro || '',
      label_map: state.variables.userLabels,
      custom_labels: exportCustomLabels,
      custom_titles: state.review.customTitles,
      hypotheses: state.hypotheses.approved.length ? state.hypotheses.approved : undefined,
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'statai_bulgular.docx';
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    window.alert(`Word indirme hatası: ${e instanceof Error ? e.message : 'Bilinmeyen hata'}`);
  } finally {
    useAppStore.getState().setWordExporting(false);
  }
}

export function useReview() {
  return { initReviewStep, downloadWord, runQualityCheck };
}
