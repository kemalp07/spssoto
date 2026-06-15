import { apiCall } from '../api/client';
import { buildAnalyzePayload, getAnalysisContext } from '../lib/analysisPayload';
import { EXCLUDE_PATTERNS, STEPS } from '../lib/constants';
import { buildVariablesForDerivedDetection } from '../lib/derivedVariables';
import { getMissingCodesFromState } from '../lib/missingCodes';
import { documentContextPayload } from '../lib/wizardSkip';
import { notifyError } from '../lib/notify';
import { getAppState } from '../lib/storeAccess';
import { useAppStore } from '../stores/useAppStore';
import type { AnalysisResult, ClassifyResponse, DetectDerivedResponse } from '../types';

async function applyTableLayout(results: AnalysisResult[]): Promise<AnalysisResult[]> {
  if (!results?.length) return results ?? [];
  try {
    const json = await apiCall<{ results?: AnalysisResult[] }>('/layout-results', { results });
    return json.results ?? results;
  } catch {
    return results;
  }
}

export async function runAnalysisFromPlan(): Promise<boolean> {
  const state = getAppState();
  const enabledTests = state.plan.catalog
    .filter((t) => t.cekirdek || t.enabled !== false)
    .map((t) => t.id)
    .filter(Boolean) as string[];
  if (!enabledTests.length) {
    notifyError('En az bir test seçmelisiniz.');
    return false;
  }
  return runAnalysis(enabledTests);
}

export async function runAnalysis(enabledTests: string[]): Promise<boolean> {
  const state = getAppState();
  if (!state.variables.selectedCat.size && !state.variables.selectedCont.size) {
    notifyError('En az bir değişken seçmelisiniz.');
    return false;
  }

  getAppState().clearBulgu();
  useAppStore.setState((s) => ({
    results: { ...s.results, analysis: [], bulgular: {}, bulguSummary: '' },
  }));
  getAppState().setAnalyzing(true);

  try {
    const fresh = getAppState();
    const json = await apiCall<{
      results?: AnalysisResult[];
      meta?: Record<string, unknown>;
      missing_data?: unknown[];
    }>('/analyze', buildAnalyzePayload(fresh, enabledTests));

    let results = (json.results ?? []).filter((r: AnalysisResult) => r.type !== 'cronbach');

    if (fresh.scales.detected.length > 0) {
      try {
        const scalesToSend = fresh.scales.detected.map((scale) => {
          const items = scale.items as string[] | undefined;
          const prefix = items?.[0]?.split('_')[0]?.toUpperCase();
          const matchingCol = Object.keys(fresh.variables.userLabels).find(
            (col) => col.toUpperCase().startsWith(prefix ?? '') && col.includes('TOPLAM'),
          );

          const registryMatch = fresh.scales.registryMeta?.registry_matched?.find(
            (m) =>
              m.id === (scale as { registry_id?: string; id?: string }).registry_id
              || m.id === (scale as { id?: string }).id
              || m.name === scale.name,
          );

          const cronbachItems =
            (scale as { cronbach_items?: string[] }).cronbach_items ?? items ?? [];

          return {
            ...scale,
            cronbach_items: cronbachItems,
            items: cronbachItems,
            name: (matchingCol && fresh.variables.userLabels[matchingCol] !== matchingCol)
              ? fresh.variables.userLabels[matchingCol]
              : scale.name,
            reverse_items: (scale as { reverse_items?: number[] }).reverse_items
              ?? (registryMatch as { reverse_items?: number[] } | undefined)?.reverse_items
              ?? [],
            scale_range: (scale as { scale_range?: number[] }).scale_range
              ?? (registryMatch as { scale_range?: number[] } | undefined)?.scale_range
              ?? [0, 4],
          };
        });
        const cbData = await apiCall<{ results?: AnalysisResult[] }>('/analyze/cronbach-batch', {
          scales: scalesToSend,
          data: fresh.parsedData.map((row) => ({ values: row })),
          missing_codes: getMissingCodesFromState(
            fresh.wizard.detectedMissingCodes,
            fresh.wizard.manualMissingCodesText,
            fresh.wizard.missingCodesEditOpen,
          ),
        });
        if (cbData.results?.length) {
          const normIdx = results.findIndex((r) => r.type === 'normality');
          const insertIdx = normIdx >= 0 ? normIdx + 1 : 2;
          results = [...results.slice(0, insertIdx), ...cbData.results, ...results.slice(insertIdx)];
        }
      } catch (err) {
        console.error('[CRONBACH BATCH] HATA:', err);
      }
    }

    results = await applyTableLayout(results);
    getAppState().setAnalysisResults(results, json.meta);
    if (json.missing_data) {
      useAppStore.setState((s) => ({
        results: { ...s.results, missingData: json.missing_data as typeof s.results.missingData },
      }));
    }

    if (!results.length) {
      notifyError('Analiz tamamlandı ancak sonuç üretilemedi. Test seçimlerinizi kontrol edin.');
      return false;
    }

    getAppState().goToStep(STEPS.indexOf('results'));
    return true;
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Analiz sırasında bir hata oluştu';
    notifyError(msg);
    useAppStore.setState((s) => ({
      plan: { ...s.plan, error: msg },
    }));
    return false;
  } finally {
    getAppState().setAnalyzing(false);
  }
}

export async function runMultipleRegression(
  predictors: string[],
  outcome: string,
): Promise<boolean> {
  if (!predictors.length) {
    notifyError('En az bir yordayıcı seçin.');
    return false;
  }
  if (!outcome) {
    notifyError('Sonuç değişkeni seçin.');
    return false;
  }
  if (predictors.includes(outcome)) {
    notifyError('Sonuç değişkeni yordayıcılar arasında olamaz.');
    return false;
  }

  const state = getAppState();
  const { variables, data } = getAnalysisContext(state);
  try {
    const json = await apiCall<{ result?: AnalysisResult }>('/analyze/regression', {
      predictors,
      outcome,
      data,
      variables,
    });
    if (json.result) {
      getAppState().appendAnalysisResult(json.result);
      getAppState().clearBulgu();
      return true;
    }
    return false;
  } catch (e) {
    notifyError(e instanceof Error ? e.message : 'Regresyon hatası');
    return false;
  }
}

export async function runAIClassify(): Promise<boolean> {
  const state = getAppState();
  if (!state.parsedData.length) return false;

  const nonItemCols = state.columns.filter(
    (col) => !EXCLUDE_PATTERNS.some((p) => p.test(col)),
  );
  const samples: Record<string, unknown[]> = {};
  nonItemCols.forEach((col) => {
    samples[col] = [...new Set(
      state.parsedData.slice(0, 5).map((r) => r[col]).filter((v) => v !== '' && v != null),
    )].slice(0, 4);
  });

  try {
    const payload: Record<string, unknown> = {
      columns: nonItemCols,
      samples,
      labels: state.variables.userLabels,
      research_topic: state.wizard.researchTopic || '',
      variable_measure: state.savMetadata.variableMeasure,
      data: state.parsedData.map((row) => ({ values: row })),
      missing_codes: getMissingCodesFromState(
        state.wizard.detectedMissingCodes,
        state.wizard.manualMissingCodesText,
        state.wizard.missingCodesEditOpen,
      ),
      ...documentContextPayload(state.documents.context, state.documents.sessionId),
    };

    const cls = await apiCall<ClassifyResponse>('/classify', payload);

    if (cls.derived?.length) {
      getAppState().applyDerivedList(cls.derived);
      cls.derived.forEach((d) => {
        const current = getAppState().variables.derivedVarMap[d.name] ?? {};
        useAppStore.setState((s) => ({
          variables: {
            ...s.variables,
            derivedVarMap: {
              ...s.variables.derivedVarMap,
              [d.name]: { ...current, ...d },
            },
          },
        }));
      });
    }

    if (cls.manual_required && !cls.categorical?.length && !cls.continuous?.length) {
      await fetchAndApplyDerivedVariables();
      return false;
    }

    getAppState().applyClassifyResult(cls);
    return true;
  } catch {
    await fetchAndApplyDerivedVariables();
    return false;
  }
}

export async function fetchAndApplyDerivedVariables(): Promise<void> {
  const state = getAppState();
  if (!state.parsedData.length) return;

  const variables = buildVariablesForDerivedDetection(
    state.variables.catColumns,
    state.variables.contColumns,
    state.variables.userLabels,
    state.parsedData,
  );
  if (!variables.length) return;

  try {
    const json = await apiCall<DetectDerivedResponse>('/detect-derived', {
      variables,
      data: state.parsedData.map((row) => ({ values: row })),
      missing_codes: getMissingCodesFromState(
        state.wizard.detectedMissingCodes,
        state.wizard.manualMissingCodesText,
        state.wizard.missingCodesEditOpen,
      ),
    });
    getAppState().applyDerivedList(json.derived ?? []);
  } catch {
    /* optional fallback */
  }
}

export function useAnalysis() {
  return {
    runAIClassify,
    fetchAndApplyDerivedVariables,
    runAnalysisFromPlan,
    runAnalysis,
    runMultipleRegression,
  };
}
