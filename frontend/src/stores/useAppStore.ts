/**
 * Monolithic app store (~900 lines). Async hooks read fresh snapshots via
 * getAppState() in lib/storeAccess.ts; use useAppStore(selector) in components.
 */
import { create } from 'zustand';
import { STEPS } from '../lib/constants';
import type {
  AnalysisResult,
  ClassifyResponse,
  DataRow,
  DerivedVariable,
  DocumentSlice,
  FileInfo,
  HypothesesSlice,
  LabelMeta,
  DetectScalesResponse,
  MatchScalesResponse,
  PlanProfileId,
  PlanSlice,
  ParseHypothesesResponse,
  PlanTestsResponse,
  QualityCheckResult,
  ReadFileResponse,
  ResultsSlice,
  ReviewScaleEntry,
  ReviewSlice,
  SavMetadata,
  ScalesSlice,
  ToastMessage,
  UploadDocumentsResponse,
  VariableSlice,
  WizardSlice,
  WizardStepId,
} from '../types';
import { suggestedScaleNamesFromColumns } from '../lib/fileParse';
import {
  buildDocumentContext,
  countAnketItems,
  countEtikHypotheses,
} from '../lib/documents';
import {
  applyDerivedPlacements,
  computeMissingData,
} from '../lib/derivedVariables';
import { mapClassifyResponse, resolveAiStatus } from '../lib/classify';
import {
  catalogFromLegacy,
  normalizeCatalogItem,
  syncTestsFromCatalog,
} from '../lib/planCatalog';
import { loadVariablesData } from '../lib/variablesLoad';
import {
  scalesFromDetection,
  shouldSkipScalesStep,
  shouldSkipTopicStep,
  topicFromEtikKurul,
} from '../lib/wizardSkip';

function emptyVariableSlice(): VariableSlice {
  return {
    catColumns: [],
    contColumns: [],
    selectedCat: new Set(),
    selectedCont: new Set(),
    excludeColumns: [],
    userLabels: {},
    itemVariantMap: {},
    derivedVarMap: {},
    lastRecommendations: {},
    aiExcluded: new Set(),
    fileInfoText: '',
    showAllLabelRows: false,
  };
}

function emptyScalesSlice(): ScalesSlice {
  return {
    detected: [],
    registryMeta: { registry_matched: [], registry_unmatched: [], cutoffs: {} },
    scaleInfo: {},
    approvedCutoffs: [],
    matchResults: [],
    unmatchedColumns: [],
  };
}

function emptyDocumentSlice(): DocumentSlice {
  return {
    anket: {
      loading: false,
      fileName: '',
      data: null,
      loaded: false,
      partial: false,
      itemCount: 0,
      file: null,
    },
    etikKurul: {
      loading: false,
      fileName: '',
      data: null,
      loaded: false,
      partial: false,
      hypothesisCount: 0,
      file: null,
    },
    context: null,
    sessionId: null,
    ethicsFile: { base64: null, type: null, name: '' },
    pdfContextMap: {},
  };
}

function emptyHypothesesSlice(): HypothesesSlice {
  return {
    approved: [],
    candidates: [],
    unmatched: [],
    unmatchedDisplay: [],
    isApproved: false,
    editMode: false,
    activeFilter: null,
    parseMeta: {},
    loading: false,
    planLoading: false,
  };
}

function emptyPlanSlice(): PlanSlice {
  return {
    tests: [],
    catalog: [],
    excluded: [],
    meta: {},
    profile: 'standart',
    userTouched: false,
    error: null,
  };
}

function emptyResultsSlice(): ResultsSlice {
  return {
    analysis: [],
    meta: {},
    missingData: [],
    cronbach: [],
    bulgular: {},
    bulguSummary: '',
    analyzing: false,
    bulguLoading: false,
  };
}

function emptyReviewSlice(): ReviewSlice {
  return {
    qualityCheck: null,
    forceExport: false,
    expandedScales: new Set(),
    scalesCache: [],
    customTitles: {},
    customLabels: {},
    loading: false,
    wordExporting: false,
  };
}

function emptyWizardSlice(): WizardSlice {
  return {
    currentStep: 0,
    autoSkippedSteps: new Set(),
    variablesPhase: 1,
    variablesDataReady: false,
    labelsPhaseAutoSkipped: false,
    researchTopic: '',
    scaleNames: '',
    detectScalesRan: false,
    manualMissingCodesText: '99',
    missingCodesEditOpen: false,
    detectedMissingCodes: { codes: [], columnMap: {}, global: null },
  };
}

function emptySavMetadata(): SavMetadata {
  return {
    variableMeasure: {},
    valueLabels: {},
    pendingLabels: {},
    missingCodes: {},
    globalMissingCode: null,
    labelMeta: null,
  };
}

export interface AppState {
  parsedData: DataRow[];
  columns: string[];
  fileInfo: FileInfo | null;
  savMetadata: SavMetadata;
  variables: VariableSlice;
  scales: ScalesSlice;
  documents: DocumentSlice;
  hypotheses: HypothesesSlice;
  plan: PlanSlice;
  results: ResultsSlice;
  review: ReviewSlice;
  wizard: WizardSlice;
  toasts: ToastMessage[];

  setFileData: (data: DataRow[], cols: string[], fileInfo: FileInfo) => void;
  applyFileUpload: (file: File, readResult: ReadFileResponse) => void;
  clearFileUpload: () => void;
  setAnketFile: (file: File | null) => void;
  setEtikFile: (file: File | null) => void;
  applyDocumentUpload: (response: UploadDocumentsResponse) => void;
  resetAnketDocument: () => void;
  resetEtikDocument: () => void;
  setSavMetadata: (meta: Partial<SavMetadata>) => void;
  updateVariable: (col: string, label: string) => void;
  goToStep: (step: number) => void;
  goToStepById: (stepId: WizardStepId) => void;
  markStepSkipped: (stepId: WizardStepId) => void;
  unmarkStepSkipped: (stepId: WizardStepId) => void;
  setResearchTopic: (topic: string) => void;
  setScaleNames: (names: string) => void;
  setScaleDetection: (response: DetectScalesResponse) => void;
  setScaleMatches: (response: MatchScalesResponse) => void;
  recomputeAutoSkips: () => void;
  loadVariablesStepData: () => Promise<void>;
  applyClassifyResult: (cls: ClassifyResponse) => void;
  applyDerivedList: (derived: DerivedVariable[]) => void;
  toggleColumnSelection: (type: 'cat' | 'cont', col: string, checked: boolean) => void;
  setVariablesPhase: (phase: 1 | 2) => void;
  setShowAllLabelRows: (show: boolean) => void;
  setMissingCodesEditOpen: (open: boolean) => void;
  setManualMissingCodesText: (text: string) => void;
  setLabelsPhaseAutoSkipped: (skipped: boolean) => void;
  applyHypothesisParse: (response: ParseHypothesesResponse) => void;
  setHypothesesApproved: (approved: boolean) => void;
  setHypothesisEditMode: (edit: boolean) => void;
  updateHypothesisCandidates: (idx: number, candidateIds: string[]) => void;
  skipHypothesisReview: () => void;
  applyPlanResponse: (response: PlanTestsResponse) => void;
  togglePlanCatalogItem: (index: number, enabled: boolean) => void;
  togglePlanTier: (tier: string, enabled: boolean) => void;
  setPlanProfile: (profile: PlanProfileId) => void;
  setPlanActiveFilter: (filter: string | null) => void;
  setAnalysisResults: (results: AnalysisResult[], meta?: Record<string, unknown>) => void;
  appendAnalysisResult: (result: AnalysisResult) => void;
  setBulgu: (index: number, text: string) => void;
  setBulguSummary: (text: string) => void;
  clearBulgu: () => void;
  setAnalyzing: (v: boolean) => void;
  setBulguLoading: (v: boolean) => void;
  setQualityCheck: (result: QualityCheckResult | null) => void;
  setReviewScalesCache: (scales: ReviewScaleEntry[]) => void;
  toggleReviewScaleExpanded: (idx: number) => void;
  setCustomTitle: (index: number, title: string | null) => void;
  applyReviewScaleName: (idx: number, newName: string) => void;
  setReviewLoading: (v: boolean) => void;
  setWordExporting: (v: boolean) => void;
  setReviewForceExport: (v: boolean) => void;
  showToast: (text: string, type?: ToastMessage['type']) => void;
  dismissToast: (id: string) => void;
  reset: () => void;
}

const initialState = {
  parsedData: [] as DataRow[],
  columns: [] as string[],
  fileInfo: null as FileInfo | null,
  savMetadata: emptySavMetadata(),
  variables: emptyVariableSlice(),
  scales: emptyScalesSlice(),
  documents: emptyDocumentSlice(),
  hypotheses: emptyHypothesesSlice(),
  plan: emptyPlanSlice(),
  results: emptyResultsSlice(),
  review: emptyReviewSlice(),
  wizard: emptyWizardSlice(),
  toasts: [] as ToastMessage[],
};

export const useAppStore = create<AppState>((set, get) => ({
  ...initialState,

  setFileData: (data, cols, fileInfo) =>
    set({ parsedData: data, columns: cols, fileInfo }),

  applyFileUpload: (file, readResult) => {
    const data = readResult.data ?? [];
    if (!data.length) return;

    const cols = readResult.columns ?? Object.keys(data[0]);
    const fileType = file.name.toLowerCase().endsWith('.sav')
      ? 'sav'
      : file.name.toLowerCase().endsWith('.csv')
        ? 'csv'
        : file.name.toLowerCase().endsWith('.xls')
          ? 'xls'
          : 'xlsx';

    const labelMeta: LabelMeta | null = (readResult.labels_found ?? 0) > 0
      ? { count: readResult.labels_found ?? 0, source: readResult.source ?? fileType }
      : null;

    set({
      parsedData: data,
      columns: cols,
      fileInfo: {
        name: file.name,
        size: file.size,
        type: fileType,
      },
      savMetadata: {
        variableMeasure: readResult.variable_measure ?? {},
        valueLabels: readResult.value_labels ?? {},
        pendingLabels: readResult.labels ?? {},
        missingCodes: readResult.missing_codes ?? {},
        globalMissingCode: readResult.global_missing_code ?? null,
        labelMeta,
      },
      scales: emptyScalesSlice(),
      wizard: {
        ...get().wizard,
        scaleNames: suggestedScaleNamesFromColumns(cols),
        researchTopic: '',
        autoSkippedSteps: new Set(),
        labelsPhaseAutoSkipped: false,
        variablesDataReady: false,
        variablesPhase: 1,
        detectScalesRan: false,
        manualMissingCodesText: '99',
        missingCodesEditOpen: false,
        detectedMissingCodes: { codes: [], columnMap: {}, global: null },
      },
      variables: emptyVariableSlice(),
    });
  },

  clearFileUpload: () =>
    set({
      parsedData: [],
      columns: [],
      fileInfo: null,
      savMetadata: emptySavMetadata(),
    }),

  setAnketFile: (file) =>
    set((s) => ({
      documents: {
        ...s.documents,
        anket: {
          ...s.documents.anket,
          file,
          loading: Boolean(file),
          fileName: file?.name ?? '',
          loaded: false,
          partial: false,
          itemCount: 0,
        },
      },
    })),

  setEtikFile: (file) =>
    set((s) => ({
      documents: {
        ...s.documents,
        etikKurul: {
          ...s.documents.etikKurul,
          file,
          loading: Boolean(file),
          fileName: file?.name ?? '',
          loaded: false,
          partial: false,
          hypothesisCount: 0,
        },
      },
    })),

  applyDocumentUpload: (response) => {
    const context = buildDocumentContext(response);
    const anket = context.anket ?? null;
    const etik = context.etik_kurul ?? null;
    const state = get();

    const anketUpdate = state.documents.anket.file
      ? {
          loading: false,
          loaded: true,
          fileName: state.documents.anket.file.name,
          data: anket,
          itemCount: countAnketItems(anket),
          partial: !anket || Boolean(anket?.parse_error) || countAnketItems(anket) === 0,
        }
      : {};

    const etikUpdate = state.documents.etikKurul.file
      ? {
          loading: false,
          loaded: true,
          fileName: state.documents.etikKurul.file.name,
          data: etik,
          hypothesisCount: countEtikHypotheses(etik),
          partial: !etik || Boolean(etik?.parse_error) || countEtikHypotheses(etik) === 0,
        }
      : {};

    const wizardPatch: Partial<WizardSlice> = {};
    if (etik && !etik.parse_error) {
      const topicText = topicFromEtikKurul(etik);
      if (topicText && !state.wizard.researchTopic) {
        wizardPatch.researchTopic = topicText;
      }
      if (etik.scale_names?.length && !state.wizard.scaleNames) {
        wizardPatch.scaleNames = etik.scale_names.join(', ');
      }
    }

    set((s) => ({
      documents: {
        ...s.documents,
        context,
        sessionId: response.session_id ?? s.documents.sessionId,
        anket: { ...s.documents.anket, ...anketUpdate },
        etikKurul: { ...s.documents.etikKurul, ...etikUpdate },
      },
      wizard: { ...s.wizard, ...wizardPatch },
    }));
  },

  resetAnketDocument: () =>
    set((s) => ({
      documents: {
        ...s.documents,
        anket: emptyDocumentSlice().anket,
        context: s.documents.context
          ? { ...s.documents.context, anket: null }
          : null,
      },
    })),

  resetEtikDocument: () =>
    set((s) => ({
      documents: {
        ...s.documents,
        etikKurul: emptyDocumentSlice().etikKurul,
        context: s.documents.context
          ? { ...s.documents.context, etik_kurul: null }
          : null,
      },
    })),

  setSavMetadata: (meta) =>
    set((s) => ({ savMetadata: { ...s.savMetadata, ...meta } })),

  updateVariable: (col, label) =>
    set((s) => ({
      variables: {
        ...s.variables,
        userLabels: { ...s.variables.userLabels, [col]: label },
      },
    })),

  goToStep: (step) =>
    set((s) => ({
      wizard: {
        ...s.wizard,
        currentStep: Math.max(0, Math.min(step, STEPS.length - 1)),
      },
    })),

  goToStepById: (stepId) => {
    const idx = STEPS.indexOf(stepId);
    if (idx >= 0) get().goToStep(idx);
  },

  markStepSkipped: (stepId) =>
    set((s) => {
      const next = new Set(s.wizard.autoSkippedSteps);
      next.add(stepId);
      return { wizard: { ...s.wizard, autoSkippedSteps: next } };
    }),

  unmarkStepSkipped: (stepId) =>
    set((s) => {
      const next = new Set(s.wizard.autoSkippedSteps);
      next.delete(stepId);
      return { wizard: { ...s.wizard, autoSkippedSteps: next } };
    }),

  setResearchTopic: (topic) =>
    set((s) => ({ wizard: { ...s.wizard, researchTopic: topic } })),

  setScaleNames: (names) =>
    set((s) => ({ wizard: { ...s.wizard, scaleNames: names } })),

  setScaleDetection: (response) =>
    set((s) => ({
      scales: {
        ...s.scales,
        detected: response.scales ?? [],
        registryMeta: {
          registry_matched: response.registry_matched ?? [],
          registry_unmatched: response.registry_unmatched ?? [],
          cutoffs: response.cutoffs ?? {},
        },
      },
      wizard: { ...s.wizard, detectScalesRan: true },
    })),

  setScaleMatches: (response) =>
    set((s) => ({
      scales: {
        ...s.scales,
        matchResults: response.matches ?? [],
        unmatchedColumns: response.unmatched_columns ?? [],
      },
    })),

  recomputeAutoSkips: () => {
    const state = get();
    const skipped = new Set<WizardStepId>();
    let scaleNames = state.wizard.scaleNames;
    let researchTopic = state.wizard.researchTopic;

    if (shouldSkipScalesStep(
      state.scales.registryMeta.registry_matched,
      state.scales.detected,
    )) {
      skipped.add('scales');
      const fromDetection = scalesFromDetection(state.scales.detected);
      if (fromDetection) scaleNames = fromDetection;
    } else if (state.scales.detected.length) {
      const fromDetection = scalesFromDetection(state.scales.detected);
      if (fromDetection) scaleNames = fromDetection;
    }

    const etik = state.documents.context?.etik_kurul;
    if (shouldSkipTopicStep(etik)) {
      skipped.add('topic');
      const topic = topicFromEtikKurul(etik);
      if (topic) researchTopic = topic;
    }

    set((s) => ({
      wizard: {
        ...s.wizard,
        autoSkippedSteps: skipped,
        scaleNames,
        researchTopic,
      },
    }));
  },

  loadVariablesStepData: async () => {
    const state = get();
    if (!state.parsedData.length || state.wizard.variablesDataReady) return;

    const result = await loadVariablesData({
      parsedData: state.parsedData,
      columns: state.columns,
      fileName: state.fileInfo?.name ?? 'veri',
      pendingLabels: state.savMetadata.pendingLabels ?? {},
      labelMeta: state.savMetadata.labelMeta,
      variableMeasure: state.savMetadata.variableMeasure ?? {},
      missingCodes: state.savMetadata.missingCodes ?? {},
      globalMissingCode: state.savMetadata.globalMissingCode,
      matchResults: state.scales.matchResults,
      showToast: (text) => get().showToast(text, 'success'),
      documentsContext: state.documents.context,
      sessionId: state.documents.sessionId,
    });

    set((s) => ({
      parsedData: result.parsedData,
      columns: result.columns,
      variables: {
        ...s.variables,
        aiExcluded: result.aiExcluded,
        itemVariantMap: result.itemVariantMap,
        catColumns: result.catColumns,
        contColumns: result.contColumns,
        excludeColumns: result.excludeColumns,
        selectedCat: result.selectedCat,
        selectedCont: result.selectedCont,
        userLabels: result.userLabels,
        fileInfoText: result.fileInfoText,
        lastRecommendations: {},
        derivedVarMap: {},
      },
      results: {
        ...s.results,
        missingData: result.missingData,
      },
      wizard: {
        ...s.wizard,
        variablesDataReady: true,
        detectedMissingCodes: result.detectedMissingCodes,
        manualMissingCodesText: result.manualMissingCodesText,
      },
    }));
  },

  applyClassifyResult: (cls) => {
    const state = get();
    if (cls.manual_required && !cls.categorical?.length && !cls.continuous?.length) {
      return;
    }

    const mapped = mapClassifyResponse(cls, state.variables.userLabels);
    if (!mapped.groupingCols.length && !mapped.outcomeCols.length) return;

    const prevSelectedCat = new Set(state.variables.selectedCat);
    const prevSelectedCont = new Set(state.variables.selectedCont);
    const { derivedVarMap } = state.variables;

    const selectedCat = new Set(
      mapped.groupingCols.filter((col) => {
        const rec = mapped.recommendations[col];
        if (resolveAiStatus(col, rec, derivedVarMap) === 'not_recommended') return false;
        if (prevSelectedCat.has(col)) return true;
        return !rec || rec.status !== 'skip';
      }),
    );
    const selectedCont = new Set(
      mapped.outcomeCols.filter((col) => {
        const rec = mapped.recommendations[col];
        if (resolveAiStatus(col, rec, derivedVarMap) === 'not_recommended') return false;
        if (prevSelectedCont.has(col)) return true;
        return !rec || rec.status !== 'skip';
      }),
    );

    const missingData = computeMissingData(
      [...mapped.groupingCols, ...mapped.outcomeCols],
      state.parsedData,
    );

    set((s) => ({
      variables: {
        ...s.variables,
        catColumns: mapped.groupingCols,
        contColumns: mapped.outcomeCols,
        selectedCat,
        selectedCont,
        lastRecommendations: mapped.recommendations,
      },
      results: { ...s.results, missingData },
    }));
  },

  applyDerivedList: (derived) => {
    const state = get();
    const next = applyDerivedPlacements(derived, {
      derivedVarMap: state.variables.derivedVarMap,
      userLabels: state.variables.userLabels,
      catColumns: state.variables.catColumns,
      contColumns: state.variables.contColumns,
      selectedCat: state.variables.selectedCat,
      selectedCont: state.variables.selectedCont,
    });
    set((s) => ({
      variables: {
        ...s.variables,
        ...next,
      },
    }));
  },

  toggleColumnSelection: (type, col, checked) =>
    set((s) => {
      const key = type === 'cat' ? 'selectedCat' : 'selectedCont';
      const next = new Set(s.variables[key]);
      if (checked) next.add(col);
      else next.delete(col);
      return {
        variables: { ...s.variables, [key]: next },
      };
    }),

  setVariablesPhase: (phase) =>
    set((s) => ({ wizard: { ...s.wizard, variablesPhase: phase } })),

  setShowAllLabelRows: (show) =>
    set((s) => ({ variables: { ...s.variables, showAllLabelRows: show } })),

  setMissingCodesEditOpen: (open) =>
    set((s) => ({ wizard: { ...s.wizard, missingCodesEditOpen: open } })),

  setManualMissingCodesText: (text) =>
    set((s) => ({ wizard: { ...s.wizard, manualMissingCodesText: text } })),

  setLabelsPhaseAutoSkipped: (skipped) =>
    set((s) => ({ wizard: { ...s.wizard, labelsPhaseAutoSkipped: skipped } })),

  applyHypothesisParse: (response) =>
    set((s) => ({
      hypotheses: {
        ...s.hypotheses,
        loading: false,
        approved: (response.hypotheses ?? []).map((h) => ({
          id: h.id,
          label: h.label,
          type: h.type ?? 'fark',
          candidate_ids: [...(h.candidate_ids ?? [])],
          var_hints: h.var_hints ?? [],
          summary: h.summary ?? '',
        })),
        unmatched: response.unmatched ?? [],
        unmatchedDisplay: response.unmatched_display ?? [],
        candidates: response.candidates ?? [],
        parseMeta: {
          ...(response.meta ?? {}),
          claude_used: response.meta?.claude_used ?? response.meta?.llm_provider === 'anthropic',
          gemini_used: response.meta?.gemini_used ?? !!response.meta?.enrich_provider,
        },
        editMode: false,
      },
    })),

  setHypothesesApproved: (approved) =>
    set((s) => ({ hypotheses: { ...s.hypotheses, isApproved: approved } })),

  setHypothesisEditMode: (edit) =>
    set((s) => ({ hypotheses: { ...s.hypotheses, editMode: edit } })),

  updateHypothesisCandidates: (idx, candidateIds) =>
    set((s) => {
      const approved = [...s.hypotheses.approved];
      if (!approved[idx]) return s;
      approved[idx] = { ...approved[idx], candidate_ids: candidateIds };
      return { hypotheses: { ...s.hypotheses, approved } };
    }),

  skipHypothesisReview: () =>
    set((s) => ({
      hypotheses: {
        ...s.hypotheses,
        approved: [],
        unmatched: [],
        isApproved: true,
        editMode: false,
      },
    })),

  applyPlanResponse: (response) => {
    const catalog = (response.catalog?.length
      ? response.catalog
      : catalogFromLegacy(response)).map(normalizeCatalogItem);
    const meta = { ...(response.meta ?? {}) };
    if (response.estimated_tables != null) meta.estimated_tables = response.estimated_tables;
    set((s) => ({
      plan: {
        ...s.plan,
        catalog,
        tests: syncTestsFromCatalog(catalog),
        excluded: response.excluded ?? [],
        meta,
        error: null,
      },
      hypotheses: { ...s.hypotheses, planLoading: false },
    }));
  },

  togglePlanCatalogItem: (index, enabled) =>
    set((s) => {
      const catalog = [...s.plan.catalog];
      const item = catalog[index];
      if (!item || item.cekirdek) return s;
      catalog[index] = { ...item, enabled };
      return {
        plan: {
          ...s.plan,
          catalog,
          tests: syncTestsFromCatalog(catalog),
          userTouched: true,
        },
      };
    }),

  togglePlanTier: (tier, enabled) =>
    set((s) => {
      const catalog = s.plan.catalog.map((t) => (
        t.tier === tier && !t.cekirdek ? { ...t, enabled } : t
      ));
      return {
        plan: {
          ...s.plan,
          catalog,
          tests: syncTestsFromCatalog(catalog),
          userTouched: true,
        },
      };
    }),

  setPlanProfile: (profile) =>
    set((s) => ({
      plan: { ...s.plan, profile, userTouched: false },
    })),

  setPlanActiveFilter: (filter) =>
    set((s) => ({ hypotheses: { ...s.hypotheses, activeFilter: filter } })),

  setAnalysisResults: (results, meta) =>
    set((s) => ({
      results: {
        ...s.results,
        analysis: results,
        meta: { ...s.results.meta, ...(meta ?? {}), research_topic: s.wizard.researchTopic },
        bulgular: {},
        bulguSummary: '',
      },
    })),

  appendAnalysisResult: (result) =>
    set((s) => ({
      results: {
        ...s.results,
        analysis: [...s.results.analysis, result],
        bulgular: {},
      },
    })),

  setBulgu: (index, text) =>
    set((s) => ({
      results: {
        ...s.results,
        bulgular: { ...s.results.bulgular, [String(index)]: text },
      },
    })),

  setBulguSummary: (text) =>
    set((s) => ({ results: { ...s.results, bulguSummary: text } })),

  clearBulgu: () =>
    set((s) => ({ results: { ...s.results, bulgular: {}, bulguSummary: '' } })),

  setAnalyzing: (v) =>
    set((s) => ({ results: { ...s.results, analyzing: v } })),

  setBulguLoading: (v) =>
    set((s) => ({ results: { ...s.results, bulguLoading: v } })),

  setQualityCheck: (result) =>
    set((s) => ({ review: { ...s.review, qualityCheck: result } })),

  setReviewScalesCache: (scales) =>
    set((s) => ({ review: { ...s.review, scalesCache: scales } })),

  toggleReviewScaleExpanded: (idx) =>
    set((s) => {
      const next = new Set(s.review.expandedScales);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return { review: { ...s.review, expandedScales: next } };
    }),

  setCustomTitle: (index, title) =>
    set((s) => {
      const customTitles = { ...s.review.customTitles };
      if (title) customTitles[String(index)] = title;
      else delete customTitles[String(index)];
      return { review: { ...s.review, customTitles } };
    }),

  applyReviewScaleName: (idx, newName) => {
    const name = (newName || '').trim();
    if (!name) return;
    const state = get();
    const scale = state.review.scalesCache[idx];
    if (!scale) return;
    const customLabels = { ...state.review.customLabels, [`scale:${scale.id}`]: name };
    const userLabels = { ...state.variables.userLabels };
    [...(scale.columns || []), ...(scale.items || [])].forEach((col) => {
      customLabels[col] = name;
      userLabels[col] = name;
    });
    const scalesCache = [...state.review.scalesCache];
    scalesCache[idx] = { ...scale, displayName: name };
    set({
      review: { ...state.review, customLabels, scalesCache },
      variables: { ...state.variables, userLabels },
    });
  },

  setReviewLoading: (v) =>
    set((s) => ({ review: { ...s.review, loading: v } })),

  setWordExporting: (v) =>
    set((s) => ({ review: { ...s.review, wordExporting: v } })),

  setReviewForceExport: (v) =>
    set((s) => ({ review: { ...s.review, forceExport: v } })),

  showToast: (text, type = 'info') =>
    set((s) => ({
      toasts: [
        ...s.toasts,
        { id: `${Date.now()}-${Math.random()}`, text, type },
      ],
    })),

  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  reset: () => set({ ...initialState, wizard: emptyWizardSlice(), toasts: [] }),
}));

export function getCurrentStepId(): WizardStepId {
  const { wizard } = useAppStore.getState();
  return STEPS[wizard.currentStep] ?? 'upload';
}
