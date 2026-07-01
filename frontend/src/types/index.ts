export type WizardStepId =
  | 'upload'
  | 'anket'
  | 'etikkurul'
  | 'oneri'
  | 'variables'
  | 'plan'
  | 'results'
  | 'review';

export type FileType = 'sav' | 'xlsx' | 'csv' | 'xls';

export interface FileInfo {
  name: string;
  size: number;
  type: FileType;
}

export type DataRow = Record<string, unknown>;

export interface SavMetadata {
  variableMeasure: Record<string, string>;
  valueLabels: Record<string, Record<string, string>>;
  pendingLabels: Record<string, string>;
  missingCodes: Record<string, string[]>;
  globalMissingCode: string | null;
  labelMeta: LabelMeta | null;
}

export interface ColumnRecommendation {
  role?: 'grouping' | 'outcome';
  status?: 'recommended' | 'optional' | 'skip';
  ai_status?: 'approved' | 'review' | 'not_recommended';
  reason?: string;
  source?: string;
}

export interface DerivedVariable {
  name: string;
  action?: 'move_to_grouping' | 'exclude';
  derived_label?: string;
  source?: string;
  confidence?: string;
  ai_status?: 'approved' | 'review' | 'not_recommended';
}

export interface MissingDataEntry {
  column: string;
  missing_pct: number;
  missing_n: number;
  warning: 'none' | 'medium' | 'high';
}

export interface DetectItemsResponse {
  item_columns?: string[];
  item_columns_display?: string[];
  item_variant_map?: Record<string, string>;
}

export interface ClassifyResponse {
  categorical?: string[];
  continuous?: string[];
  recommendations?: Record<string, ColumnRecommendation>;
  derived?: DerivedVariable[];
  manual_required?: boolean;
  augmented_columns?: Record<string, unknown[]>;
}

export interface DetectDerivedResponse {
  derived?: DerivedVariable[];
}

export interface VariableSlice {
  catColumns: string[];
  contColumns: string[];
  selectedCat: Set<string>;
  selectedCont: Set<string>;
  excludeColumns: string[];
  userLabels: Record<string, string>;
  itemVariantMap: Record<string, string>;
  derivedVarMap: Record<string, DerivedVariable>;
  lastRecommendations: Record<string, ColumnRecommendation>;
  aiExcluded: Set<string>;
  userExcluded: Set<string>;
  fileInfoText: string;
  showAllLabelRows: boolean;
}

export interface ScalesSlice {
  detected: DetectedScale[];
  registryMeta: {
    registry_matched: RegistryMatch[];
    registry_unmatched: unknown[];
    cutoffs: Record<string, ScaleCutoff>;
  };
  scaleInfo: Record<string, unknown>;
  approvedCutoffs: unknown[];
  matchResults: ScaleMatch[];
  unmatchedColumns: string[];
}

export interface DetectedScale {
  name?: string;
  id?: string;
  registry_id?: string;
  registry_confidence?: string;
  source?: string;
  turkish_valid?: boolean;
  items?: unknown[];
  reverse_items?: number[];
  scale_range?: number[];
  cronbach_items?: string[];
}

export interface RegistryMatch {
  id?: string;
  name?: string;
  confidence?: string;
  cols?: string[];
  reverse_items?: number[];
  scale_range?: number[];
}

export interface ScaleCutoff {
  value?: number;
  interpretation?: string;
}

export interface DetectedMissingCodes {
  codes: string[];
  columnMap: Record<string, string[]>;
  global: string | null;
}

export interface ScaleMatch {
  scale_name: string;
  scale_id?: string;
  registry_id?: string;
  confidence?: string;
  total_columns?: string[];
  item_columns?: string[];
  matched_columns?: string[];
  cronbach_items?: string[];
  item_count?: number;
}

export interface DetectScalesResponse {
  scales: DetectedScale[];
  registry_matched: RegistryMatch[];
  registry_unmatched: unknown[];
  cutoffs: Record<string, ScaleCutoff>;
}

export interface MatchScalesResponse {
  matches: ScaleMatch[];
  unmatched_columns?: string[];
}

export interface DocumentSlice {
  anket: {
    loading: boolean;
    fileName: string;
    data: unknown;
    loaded: boolean;
    partial: boolean;
    itemCount: number;
    file: File | null;
  };
  etikKurul: {
    loading: boolean;
    fileName: string;
    data: unknown;
    loaded: boolean;
    partial: boolean;
    hypothesisCount: number;
    file: File | null;
  };
  context: DocumentContext | null;
  sessionId: string | null;
  ethicsFile: { base64: string | null; type: string | null; name: string };
  pdfContextMap: Record<string, string>;
}

export interface DocumentContext {
  anket?: AnketParseResult | null;
  etik_kurul?: EtikKurulParseResult | null;
}

export interface AnketParseResult {
  parse_error?: boolean;
  raw_text?: string;
  sections?: Array<{
    title?: string;
    items?: Array<{ no?: number | string; text?: string; reverse_hint?: boolean }>;
  }>;
}

export interface AnalizOneriGerekce {
  analiz?: string;
  neden?: string;
  degiskenler?: string[];
  tip?: string;
}

export interface AnalizOneriScale {
  ad?: string;
  prefix?: string;
  maddeler_prefix?: string;
  neden?: string;
}

export interface AnalizOneriResult {
  ozet?: string;
  analiz?: string;
  gerekceler?: AnalizOneriGerekce[];
  olcekler?: AnalizOneriScale[];
  gruplama_degiskenleri?: string[];
  outcome_degiskenleri?: string[];
}

export interface AnalizOneriResponse {
  oneri?: AnalizOneriResult;
  meta?: Record<string, unknown>;
}

export interface OneriSlice {
  loading: boolean;
  error: string | null;
  data: AnalizOneriResult | null;
  yorum: string | null;
  meta: Record<string, unknown> | null;
  fetched: boolean;
}

export interface EtikKurulParseResult {
  parse_error?: boolean;
  hypotheses?: string[];
  aim?: string;
  scale_names?: string[];
  raw_text?: string;
}

export interface UploadDocumentsResponse {
  session_id: string;
  anket?: AnketParseResult | null;
  etik_kurul?: EtikKurulParseResult | null;
  document_context: DocumentContext;
}

export interface HypothesisEntry {
  id: string;
  label?: string;
  type?: string;
  candidate_ids?: string[];
  var_hints?: string[];
  summary?: string;
}

export interface HypothesisCandidate {
  id: string;
  test?: string;
  label?: string;
}

export interface HypothesesSlice {
  approved: HypothesisEntry[];
  candidates: HypothesisCandidate[];
  unmatched: unknown[];
  unmatchedDisplay: string[];
  isApproved: boolean;
  editMode: boolean;
  activeFilter: string | null;
  parseMeta: Record<string, unknown>;
  loading: boolean;
  planLoading: boolean;
}

export type PlanTier = 'kesin_onerilen' | 'onerilen' | 'onerilmeyen';

export interface PlanCatalogItem {
  id?: string;
  label?: string;
  test?: string;
  vars?: string[];
  tier?: PlanTier | string;
  enabled?: boolean;
  enabled_default?: boolean;
  recommended?: boolean;
  cekirdek?: boolean;
  butce_disi?: boolean;
  merge_key?: string;
  hypothesis_id?: string | null;
  reason?: string;
  reason_code?: string;
  relevance_flag?: 'uygun' | 'olası' | 'düşük_öncelik' | string;
  relevance_score?: number;
  display_section?: 'primary' | 'accordion' | string;
  decision_log?: Record<string, unknown>;
}

export interface PlanTestsResponse {
  catalog?: PlanCatalogItem[];
  recommended?: PlanCatalogItem[];
  excluded?: PlanCatalogItem[];
  meta?: Record<string, unknown>;
  estimated_tables?: number;
}

export interface ParseHypothesesResponse {
  hypotheses?: HypothesisEntry[];
  unmatched?: unknown[];
  unmatched_display?: string[];
  candidates?: HypothesisCandidate[];
  meta?: Record<string, unknown>;
}

export type PlanProfileId = 'oz' | 'standart' | 'kapsamli';

export interface PlanSlice {
  tests: PlanCatalogItem[];
  catalog: PlanCatalogItem[];
  excluded: PlanCatalogItem[];
  meta: Record<string, unknown>;
  profile: PlanProfileId;
  userTouched: boolean;
  error: string | null;
}

export interface AnalysisVariable {
  name: string;
  label: string;
  type: 'categorical' | 'continuous';
  role: 'grouping' | 'outcome';
  included: boolean;
  value_labels?: Record<string, string> | null;
}

export interface AnalysisResult {
  type?: string;
  title?: string;
  headers?: string[];
  rows?: unknown[][];
  note?: string;
  significant?: boolean;
  p?: number | string;
  table_number?: number;
  column?: string;
  var1?: string;
  var2?: string;
  variable?: string;
  variables?: string[];
  hypothesis_id?: string;
  alpha?: number;
  items?: string[];
}

export interface QualityCheckResult {
  overall?: string;
  has_errors?: boolean;
  findings?: Array<{ severity?: string; table_no?: number | null; message?: string }>;
  stale_backend?: boolean;
}

export interface ReviewScaleEntry {
  id: string;
  name: string;
  scaleId: string | null;
  displayName: string;
  items: string[];
  cronbachItems: string[];
  columns: string[];
  itemCount: number;
  alpha: number | null;
  confidence: string;
  okMatch: boolean;
}

export interface BulguEntry {
  text: string;
  lockedAt: string;
  version: number;
  isLocked: boolean;
  previousVersions?: string[];
}

export interface ResultsSlice {
  analysis: AnalysisResult[];
  meta: Record<string, unknown>;
  missingData: MissingDataEntry[];
  cronbach: AnalysisResult[];
  bulgular: Record<string, BulguEntry>;
  bulguSummary: string;
  analyzing: boolean;
  bulguLoading: boolean;
}

export interface ReviewSlice {
  qualityCheck: QualityCheckResult | null;
  forceExport: boolean;
  expandedScales: Set<number>;
  scalesCache: ReviewScaleEntry[];
  customTitles: Record<string, string>;
  customLabels: Record<string, string>;
  loading: boolean;
  wordExporting: boolean;
}

export interface WizardSlice {
  currentStep: number;
  autoSkippedSteps: Set<WizardStepId>;
  variablesPhase: 1 | 2;
  variablesDataReady: boolean;
  classifyDone: boolean;
  labelsPhaseAutoSkipped: boolean;
  researchTopic: string;
  scaleNames: string;
  detectScalesRan: boolean;
  manualMissingCodesText: string;
  missingCodesEditOpen: boolean;
  detectedMissingCodes: DetectedMissingCodes;
}

export interface ToastMessage {
  id: string;
  text: string;
  type: 'info' | 'success' | 'error';
}

export interface ReadFileResponse {
  data: DataRow[];
  columns?: string[];
  labels?: Record<string, string>;
  value_labels?: Record<string, Record<string, string>>;
  variable_measure?: Record<string, string>;
  missing_codes?: Record<string, string[]>;
  global_missing_code?: string | null;
  labels_found?: number;
  source?: string;
  row_count?: number;
}

export interface LabelMeta {
  count: number;
  source: string;
}
