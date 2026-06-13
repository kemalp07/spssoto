import {
  EXCLUDE_PATTERNS,
  GROUPING_PATTERNS,
  OUTCOME_CAT_PATTERNS,
  OUTCOME_CONT_PATTERNS,
} from './constants';
import type { ColumnRecommendation, DataRow, DerivedVariable } from '../types';

export interface ClassifyFallback {
  groupingCols: string[];
  outcomeCols: string[];
  excludeCols: string[];
}

export interface ClassifyResponseShape {
  categorical?: string[];
  continuous?: string[];
  recommendations?: Record<string, ColumnRecommendation>;
  derived?: DerivedVariable[];
  manual_required?: boolean;
}

export interface MappedClassifyResult {
  groupingCols: string[];
  outcomeCols: string[];
  recommendations: Record<string, ColumnRecommendation>;
}

const FORCE_OUTCOME_SUFFIXES = [
  /_toplam$/i, /_total$/i, /_score$/i, /_puan$/i, /_skor$/i,
  /_sum$/i, /_mean$/i, /_avg$/i, /_ortalama$/i,
  /_grubu?$/i, /_group$/i, /_binary$/i,
  /_kategori$/i, /_category$/i, /_sinif$/i,
  /_level$/i, /_seviye$/i, /_risk$/i, /_durum$/i,
];

const MEASUREMENT_LABEL_KEYWORDS = [
  /\byaş\b/i, /\bage\b/i,
  /\bboy\b/i, /\bheight\b/i,
  /\bkilo\b/i, /\bweight\b/i, /\bağırlık\b/i,
  /\bbeden kitle\b/i, /\bbmi\b/i, /\bbki\b/i, /\bvki\b/i,
];

export function classifyColumns(cols: string[], data: DataRow[]): ClassifyFallback {
  const groupingCols: string[] = [];
  const outcomeCols: string[] = [];
  const excludeCols: string[] = [];

  cols.forEach((col) => {
    if (EXCLUDE_PATTERNS.some((p) => p.test(col))) {
      excludeCols.push(col);
      return;
    }
    if (GROUPING_PATTERNS.some((p) => p.test(col))) {
      groupingCols.push(col);
      return;
    }
    if (OUTCOME_CAT_PATTERNS.some((p) => p.test(col))) {
      outcomeCols.push(col);
      return;
    }
    if (OUTCOME_CONT_PATTERNS.some((p) => p.test(col))) {
      outcomeCols.push(col);
      return;
    }
    const vals = [...new Set(
      data.slice(0, 50).map((r) => r[col]).filter((v) => v !== '' && v != null),
    )];
    const numeric = vals.filter((v) => !Number.isNaN(parseFloat(String(v).replace(',', '.'))));
    if (numeric.length / vals.length > 0.8 && vals.length > 8) {
      outcomeCols.push(col);
    } else {
      groupingCols.push(col);
    }
  });

  return { groupingCols, outcomeCols, excludeCols };
}

function isForcedOutcome(col: string, label: string): boolean {
  if (FORCE_OUTCOME_SUFFIXES.some((p) => p.test(col))) return true;
  const text = label || col;
  return MEASUREMENT_LABEL_KEYWORDS.some((p) => p.test(text));
}

export function mapClassifyResponse(
  cls: ClassifyResponseShape,
  userLabels: Record<string, string>,
): MappedClassifyResult {
  const recs = cls.recommendations ?? {};

  let groupingCols = [
    ...(cls.categorical ?? []).filter((col) => (recs[col]?.role ?? 'grouping') === 'grouping'),
    ...(cls.continuous ?? []).filter((col) => recs[col]?.role === 'grouping'),
  ];

  let outcomeCols = [
    ...(cls.continuous ?? []).filter((col) => (recs[col]?.role ?? 'outcome') === 'outcome'),
    ...(cls.categorical ?? []).filter((col) => recs[col]?.role === 'outcome'),
  ];

  const allCols = [...(cls.categorical ?? []), ...(cls.continuous ?? [])];
  allCols.forEach((col) => {
    const label = userLabels[col] ?? '';
    if (isForcedOutcome(col, label)) {
      groupingCols = groupingCols.filter((c) => c !== col);
      if (!outcomeCols.includes(col)) outcomeCols.push(col);
    }
  });

  return { groupingCols, outcomeCols, recommendations: recs };
}

export type AiStatus = 'approved' | 'review' | 'not_recommended';

export function resolveAiStatus(
  col: string,
  rec: ColumnRecommendation = {},
  derivedVarMap: Record<string, DerivedVariable> = {},
): AiStatus {
  if (rec.ai_status) return rec.ai_status;
  const d = derivedVarMap[col];
  if (d?.ai_status) return d.ai_status;
  if (d?.action === 'exclude') return 'not_recommended';
  if (d && d.confidence !== 'high') return 'review';
  if (d) return 'approved';
  return rec.status === 'skip' ? 'not_recommended' : 'approved';
}

export const AI_STATUS_LABELS: Record<AiStatus, { label: string; cls: string }> = {
  approved: { label: 'AI Onaylı', cls: 'badgeAiApproved' },
  review: { label: 'Kontrol Edin', cls: 'badgeAiReview' },
  not_recommended: { label: 'Önerilmez', cls: 'badgeNotRec' },
};
