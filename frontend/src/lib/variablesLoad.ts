import { apiCall } from '../api/client';
import { applyDocumentLabels, getUnlabeledColumns } from './autoLabels';
import { EXCLUDE_PATTERNS } from './constants';
import { classifyColumns } from './classify';
import { computeMissingData } from './derivedVariables';
import { normalizeDataDecimals } from './fileParse';
import { buildMissingCodesFromRead, type InferredMissingCodes } from './missingCodes';
import { documentContextPayload } from './wizardSkip';
import type { DataRow, DetectItemsResponse, ScaleMatch } from '../types';

function columnSamples(columns: string[], data: DataRow[]): Record<string, unknown[]> {
  const samples: Record<string, unknown[]> = {};
  columns.forEach((col) => {
    samples[col] = [...new Set(
      data.slice(0, 5).map((r) => r[col]).filter((v) => v !== '' && v != null),
    )].slice(0, 4);
  });
  return samples;
}

export async function detectItemColumns(
  columns: string[],
  samples: Record<string, unknown[]>,
  variableMeasure: Record<string, string>,
): Promise<DetectItemsResponse | null> {
  try {
    return await apiCall<DetectItemsResponse>('/detect-items', {
      columns,
      samples,
      variable_measure: variableMeasure,
    });
  } catch {
    return null;
  }
}

export interface VariablesLoadInput {
  parsedData: DataRow[];
  columns: string[];
  fileName: string;
  pendingLabels: Record<string, string>;
  labelMeta: { count: number; source: string } | null;
  variableMeasure: Record<string, string>;
  missingCodes: Record<string, string[]>;
  globalMissingCode: string | null;
  matchResults: ScaleMatch[];
  showToast: (text: string) => void;
  documentsContext: Parameters<typeof documentContextPayload>[0];
  sessionId: string | null;
}

export interface VariablesLoadResult {
  parsedData: DataRow[];
  columns: string[];
  aiExcluded: Set<string>;
  itemVariantMap: Record<string, string>;
  catColumns: string[];
  contColumns: string[];
  excludeColumns: string[];
  selectedCat: Set<string>;
  selectedCont: Set<string>;
  userLabels: Record<string, string>;
  fileInfoText: string;
  missingData: ReturnType<typeof computeMissingData>;
  detectedMissingCodes: InferredMissingCodes;
  manualMissingCodesText: string;
}

export function applyScaleMatchToColumns(
  matchResults: ScaleMatch[],
  contColumns: string[],
  selectedCont: Set<string>,
): { contColumns: string[]; selectedCont: Set<string> } {
  if (!matchResults.length) return { contColumns, selectedCont };
  const nextCont = [...contColumns];
  const nextSelected = new Set(selectedCont);
  matchResults.forEach((match) => {
    match.total_columns?.forEach((col) => {
      if (!nextCont.includes(col)) nextCont.push(col);
      nextSelected.add(col);
    });
  });
  return { contColumns: nextCont, selectedCont: nextSelected };
}

export async function loadVariablesData(input: VariablesLoadInput): Promise<VariablesLoadResult> {
  const normalized = normalizeDataDecimals(input.parsedData, input.columns);
  const columns = input.columns.length ? input.columns : Object.keys(normalized[0] ?? {});
  const samples = columnSamples(columns, normalized);

  const detection = await detectItemColumns(columns, samples, input.variableMeasure);
  const aiExcluded = new Set(detection?.item_columns ?? []);
  const itemVariantMap = detection?.item_variant_map ?? {};

  const nonItemColumns = columns.filter(
    (col) => !aiExcluded.has(col) && !EXCLUDE_PATTERNS.some((p) => p.test(col)),
  );
  const itemColumns = columns.filter(
    (col) => aiExcluded.has(col) || EXCLUDE_PATTERNS.some((p) => p.test(col)),
  );

  // ══════ 4 AŞAMALI ETİKET PIPELINE ══════

  // Aşama 1: SAV/SPSS labels
  const userLabels: Record<string, string> = {};
  nonItemColumns.forEach((col) => { userLabels[col] = col; });
  if (Object.keys(input.pendingLabels).length > 0) {
    Object.assign(userLabels, input.pendingLabels);
  }

  // Aşama 2+3: Anket + Etik Kurul belgelerinden etiket
  const documentScaleNames: string[] = [];
  if (input.documentsContext) {
    const ctx = input.documentsContext as Record<string, unknown>;
    const etik = ctx.etik_kurul as Record<string, unknown> | null;
    if (etik?.scale_names && Array.isArray(etik.scale_names)) {
      documentScaleNames.push(...(etik.scale_names as string[]));
    }
    const anket = ctx.anket as Record<string, unknown> | null;
    if (anket?.sections && Array.isArray(anket.sections)) {
      for (const sec of anket.sections as Array<{ name?: string }>) {
        if (sec.name) documentScaleNames.push(sec.name);
      }
    }
  }

  const afterDocs = applyDocumentLabels(
    userLabels,
    input.matchResults,
    documentScaleNames,
    nonItemColumns,
  );
  Object.assign(userLabels, afterDocs);

  // Aşama 4: Hâlâ boş kalanlar → AI (Gemini Flash, yoksa Haiku)
  const unlabeled = getUnlabeledColumns(userLabels, nonItemColumns);
  if (unlabeled.length > 0) {
    try {
      const aiResult = await apiCall<{ labels?: Record<string, string> }>(
        '/generate-labels',
        {
          columns: unlabeled,
          scale_names: documentScaleNames.length > 0 ? documentScaleNames : undefined,
          research_topic: '',
        },
        { timeout: 15_000 },
      );
      if (aiResult.labels) {
        for (const [col, label] of Object.entries(aiResult.labels)) {
          if (label && userLabels[col] === col) {
            userLabels[col] = label;
          }
        }
      }
    } catch {
      /* AI optional — ham isimlerle devam */
    }
  }

  const filledCount = nonItemColumns.filter((c) => userLabels[c] !== c).length;
  if (input.labelMeta && Object.keys(input.pendingLabels).length > 0) {
    const src = input.labelMeta.source === 'spss' ? "SPSS'den" : "Excel'den";
    input.showToast(`✅ ${input.labelMeta.count} etiket ${src} okundu`);
  } else if (filledCount > 0) {
    input.showToast(`✅ ${filledCount} etiket otomatik üretildi`);
  }

  const fb = classifyColumns(nonItemColumns, normalized);
  const groupingCols = fb.groupingCols;
  const outcomeCols = fb.outcomeCols;
  const excludeCols = [...new Set([...itemColumns, ...fb.excludeCols])];

  let contColumns = outcomeCols;
  let selectedCont = new Set(outcomeCols);
  const matched = applyScaleMatchToColumns(input.matchResults, contColumns, selectedCont);
  contColumns = matched.contColumns;
  selectedCont = matched.selectedCont;

  const allAnalysisCols = [...groupingCols, ...contColumns];
  allAnalysisCols.forEach((col) => {
    userLabels[col] = userLabels[col] ?? col;
  });

  const missingData = computeMissingData([...groupingCols, ...contColumns], normalized);
  const visible = groupingCols.length + contColumns.length;
  const fileInfoText = `${input.fileName} · ${normalized.length} satır · ${visible} analiz sütunu (${excludeCols.length} madde gizlendi)`;

  const detectedMissingCodes = buildMissingCodesFromRead({
    missing_codes: input.missingCodes,
    global_missing_code: input.globalMissingCode,
  });
  const manualMissingCodesText = detectedMissingCodes.codes.join(', ') || '99';

  return {
    parsedData: normalized,
    columns,
    aiExcluded,
    itemVariantMap,
    catColumns: groupingCols,
    contColumns,
    excludeColumns: excludeCols,
    selectedCat: new Set(groupingCols),
    selectedCont,
    userLabels,
    fileInfoText,
    missingData,
    detectedMissingCodes,
    manualMissingCodesText,
  };
}
