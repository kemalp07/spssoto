import { buildAnalysisData, buildVariables } from './buildVariables';
import { buildTestHypothesisMap } from './planCatalog';
import { getMissingCodesFromState } from './missingCodes';
import type {
  HypothesisEntry,
  PlanCatalogItem,
  SavMetadata,
  VariableSlice,
  WizardSlice,
} from '../types';

export interface AnalysisPayloadState {
  parsedData: Record<string, unknown>[];
  variables: VariableSlice;
  savMetadata: SavMetadata;
  wizard: WizardSlice;
  scales: { scaleInfo: Record<string, unknown> };
  plan: { catalog: PlanCatalogItem[]; profile: string };
  hypotheses: { approved: HypothesisEntry[] };
}

export function getAnalysisContext(state: AnalysisPayloadState) {
  const variables = buildVariables({
    selectedCat: state.variables.selectedCat,
    selectedCont: state.variables.selectedCont,
    userLabels: state.variables.userLabels,
    parsedData: state.parsedData,
    valueLabels: state.savMetadata.valueLabels,
  });
  const data = buildAnalysisData(variables, state.parsedData);
  const missing_codes = getMissingCodesFromState(
    state.wizard.detectedMissingCodes,
    state.wizard.manualMissingCodesText,
    state.wizard.missingCodesEditOpen,
  );
  return { variables, data, missing_codes };
}

export function buildAnalyzePayload(
  state: AnalysisPayloadState,
  enabledTests?: string[],
) {
  const { variables, data, missing_codes } = getAnalysisContext(state);
  return {
    variables,
    data,
    missing_codes,
    scale_info: state.scales.scaleInfo,
    test_hypothesis_map: buildTestHypothesisMap(state.plan.catalog),
    hypotheses: state.hypotheses.approved.length ? state.hypotheses.approved : undefined,
    enabled_tests: enabledTests,
  };
}

export function buildPlanPayload(state: AnalysisPayloadState) {
  const { variables, data, missing_codes } = getAnalysisContext(state);
  return {
    variables,
    data,
    missing_codes,
    research_aim: state.wizard.researchTopic.trim(),
    use_ai: true,
    profile: state.plan.profile,
    hypotheses: state.hypotheses.approved.length ? state.hypotheses.approved : undefined,
  };
}

export function buildHypothesisPayload(state: AnalysisPayloadState) {
  const { variables, data, missing_codes } = getAnalysisContext(state);
  return {
    variables,
    data,
    missing_codes,
    research_aim: state.wizard.researchTopic.trim(),
    use_ai: true,
  };
}
