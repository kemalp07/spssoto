import type { PlanCatalogItem, PlanTestsResponse } from '../types';

const RULE_CODES = new Set([
  'ikincil_gruplandirma', 'turetilmis_tekrar', 'tekrarli_demografi',
  'yetersiz_n', 'dengesiz_grup', 'totoloji', 'cift_test',
]);

export function catalogFromLegacy(json: PlanTestsResponse): PlanCatalogItem[] {
  const items: PlanCatalogItem[] = [];
  (json.recommended ?? []).forEach((t) => {
    const tier = t.tier ?? 'onerilen';
    items.push({ ...t, tier, enabled_default: tier !== 'onerilmeyen' });
  });
  (json.excluded ?? []).forEach((t) => {
    if (RULE_CODES.has(t.reason_code ?? '')) return;
    items.push({ ...t, tier: 'onerilmeyen', enabled_default: false });
  });
  return items;
}

export function normalizeCatalogItem(t: PlanCatalogItem): PlanCatalogItem {
  const tier = t.tier ?? 'onerilen';
  const relevance = t.relevance_flag ?? 'uygun';
  const enabledDefault = t.enabled_default !== undefined
    ? t.enabled_default
    : (relevance === 'uygun' ? tier !== 'onerilmeyen' : false);
  return {
    ...t,
    tier,
    enabled: enabledDefault,
    enabled_default: enabledDefault,
    recommended: tier === 'kesin_onerilen' || tier === 'onerilen',
    cekirdek: Boolean(t.cekirdek),
    butce_disi: Boolean(t.butce_disi),
    merge_key: t.merge_key ?? t.id,
    hypothesis_id: t.hypothesis_id ?? null,
    display_section: t.display_section ?? 'primary',
    relevance_flag: relevance,
    relevance_score: t.relevance_score ?? 0,
  };
}

/**
 * Aktif planda üretilecek tablo sayısı.
 * Seçili aday sayısından düşük olabilir: birden fazla aday aynı merge_key ile
 * tek tabloda birleşir (ör. korelasyon matrisi, birleştirilmiş frekanslar).
 */
export function estimatePlanTableCount(catalog: PlanCatalogItem[]): number {
  const keys = new Set<string>();
  catalog.forEach((t) => {
    if (t.cekirdek || t.enabled !== false) {
      keys.add(t.merge_key ?? t.id ?? '');
    }
  });
  return keys.size;
}

export function buildTestHypothesisMap(catalog: PlanCatalogItem[]): Record<string, string> {
  const map: Record<string, string> = {};
  catalog.forEach((t) => {
    if (t.hypothesis_id && t.id) map[t.id] = t.hypothesis_id;
  });
  return map;
}

export function syncTestsFromCatalog(catalog: PlanCatalogItem[]): PlanCatalogItem[] {
  return catalog.filter((t) => t.cekirdek || t.enabled !== false);
}

export function countHypothesisTables(
  catalog: PlanCatalogItem[],
  hypothesisId: string,
): number {
  const keys = new Set<string>();
  catalog.forEach((t) => {
    if ((t.cekirdek || t.enabled !== false) && t.hypothesis_id === hypothesisId) {
      keys.add(t.merge_key ?? t.id ?? '');
    }
  });
  return keys.size;
}

export function planTotalBarText(
  catalog: PlanCatalogItem[],
  meta: Record<string, unknown>,
): string {
  const tableCount = estimatePlanTableCount(catalog);
  const catalogTotal = (meta.catalog_count as number) ?? catalog.length;
  const kesinCount = (meta.kesin_count as number)
    ?? catalog.filter((t) => t.tier === 'kesin_onerilen').length;
  const onerilenCount = (meta.onerilen_count as number)
    ?? catalog.filter((t) => t.tier === 'onerilen').length;
  const budget = (meta.table_budget as number) ?? 12;
  const aiNote = meta.scoring_used
    ? ' · Kural tabanlı seçim'
    : (meta.ai_used && (meta.llm_calls as number) > 0
      ? ' · Claude önerisi aktif'
      : (meta.ai_used === false ? '' : ''));
  const tok = meta.approx_input_tokens
    ? ` · ~${meta.approx_input_tokens} token`
    : '';
  return (
    `📋 ${tableCount} tablo · ${budget} tablo bütçesi`
    + ` · ${catalogTotal} uygun aday`
    + ` · ${kesinCount} kesin · ${onerilenCount} önerilen`
    + `${aiNote}${tok}`
  );
}

export const PLAN_PROFILES = [
  { id: 'oz' as const, label: 'Öz', approx: 15 },
  { id: 'standart' as const, label: 'Standart', approx: 30 },
  { id: 'kapsamli' as const, label: 'Kapsamlı', approx: 50 },
];

export type PlanProfileId = typeof PLAN_PROFILES[number]['id'];

export function buildHypothesisSummaryLine(
  h: { id: string; label?: string; summary?: string; candidate_ids?: string[] },
  candidates: Array<{ id: string; test?: string; label?: string }>,
): string {
  if (h.summary) return h.summary;
  const names: Record<string, string> = {
    ttest: 't-Testi', anova: 'ANOVA', chi_square: 'Ki-Kare',
    mann_whitney: 'Mann-Whitney', kruskal_wallis: 'Kruskal-Wallis',
    correlation: 'Korelasyon',
  };
  const parts = (h.candidate_ids ?? []).map((id) => {
    const c = candidates.find((x) => x.id === id);
    if (!c) return id;
    const tname = names[c.test ?? ''] ?? c.test ?? 'Test';
    let detail = c.label ?? id;
    for (const sep of ['—', '–', '-']) {
      if (detail.includes(sep)) {
        detail = detail.split(sep).slice(1).join(sep).trim();
        break;
      }
    }
    return `${tname} (${detail})`;
  });
  return `${h.id} → ${parts.join(', ') || h.label || '—'}`;
}
