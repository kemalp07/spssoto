import type {
  AnalysisResult,
  DetectedScale,
  ReviewScaleEntry,
  ScaleMatch,
} from '../types';

export function alphaReliabilityBadge(alpha: number | null | undefined): { cls: string; label: string } {
  if (alpha == null || Number.isNaN(alpha)) return { cls: '', label: 'α —' };
  if (alpha >= 0.70) return { cls: 'alphaOk', label: 'Güvenilir' };
  if (alpha >= 0.60) return { cls: 'alphaMid', label: 'Sınırda' };
  return { cls: 'alphaLow', label: 'Düşük' };
}

export function findCronbachForItems(
  itemCols: string[],
  analysisResults: AnalysisResult[],
): AnalysisResult | null {
  if (!itemCols?.length) return null;
  const key = [...itemCols].sort().join('|');
  return analysisResults.find((r) => {
    if (r.type !== 'cronbach' || !r.items) return false;
    return [...r.items].sort().join('|') === key;
  }) ?? null;
}

export function buildReviewScaleList(input: {
  detectedScales: DetectedScale[];
  matchResults: ScaleMatch[];
  scaleInfo: Record<string, { full_name?: string }>;
  customLabels: Record<string, string>;
  analysisResults: AnalysisResult[];
}): ReviewScaleEntry[] {
  const list: ReviewScaleEntry[] = [];
  const seen = new Set<string>();

  const addScale = (
    id: string,
    name: string,
    items: string[],
    match: ScaleMatch | undefined,
    scaleId?: string | null,
  ) => {
    if (!id || seen.has(id)) return;
    seen.add(id);
    const cols = match?.matched_columns ?? items ?? [];
    const itemCols = match?.item_columns ?? items ?? [];
    const cronbachCols = match?.cronbach_items ?? itemCols;
    const cb = findCronbachForItems(
      cronbachCols.length ? cronbachCols : items,
      input.analysisResults,
    );
    const alpha = cb?.alpha ?? null;
    const displayName = input.customLabels[`scale:${id}`] || name;
    const confidence = match?.confidence ?? (cols.length ? 'medium' : 'low');
    const okMatch = confidence === 'high' || (confidence === 'medium' && cols.length > 0);
    list.push({
      id,
      name,
      scaleId: scaleId ?? null,
      displayName,
      items: itemCols,
      cronbachItems: cronbachCols,
      columns: cols,
      itemCount: match?.item_count ?? itemCols.length ?? items?.length ?? 0,
      alpha,
      confidence,
      okMatch,
    });
  };

  input.detectedScales.forEach((ds, i) => {
    const match = input.matchResults.find(
      (m) => m.scale_name?.toLowerCase() === ds.name?.toLowerCase(),
    ) ?? input.matchResults[i];
    const items = (ds.items as string[] | undefined) ?? [];
    addScale(`ds_${i}`, ds.name ?? '', items, match, ds.id ?? ds.registry_id);
  });

  input.matchResults.forEach((m, i) => {
    if (!m?.scale_name) return;
    const id = `match_${i}_${m.scale_name}`;
    if (!seen.has(id) && !seen.has(`ds_${i}`)) {
      addScale(id, m.scale_name, m.item_columns ?? [], m);
    }
  });

  Object.entries(input.scaleInfo ?? {}).forEach(([shortKey, info]) => {
    const full = info?.full_name ?? shortKey;
    const id = `si_${shortKey}`;
    if (seen.has(id)) return;
    const match = input.matchResults.find(
      (m) => m.scale_name?.toLowerCase().includes(shortKey.toLowerCase())
        || full.toLowerCase().includes(shortKey.toLowerCase()),
    );
    addScale(id, full, match?.item_columns ?? [], match);
  });

  return list;
}
