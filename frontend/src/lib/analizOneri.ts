import type {
  AnketParseResult,
  AnalizOneriResult,
  AnalizOneriScale,
  DetectedScale,
  EtikKurulParseResult,
} from '../types';

export function anketTextFromContext(anket?: AnketParseResult | null): string {
  if (!anket?.sections?.length || anket.parse_error) return '';
  return anket.sections
    .map((sec) => {
      const title = sec.title?.trim() || '';
      const items = (sec.items ?? [])
        .map((item) => {
          const no = item.no != null ? `${item.no}. ` : '';
          return `${no}${item.text ?? ''}`.trim();
        })
        .filter(Boolean)
        .join('\n');
      return [title, items].filter(Boolean).join('\n');
    })
    .filter(Boolean)
    .join('\n\n');
}

export function etikTextFromContext(etik?: EtikKurulParseResult | null): string {
  if (!etik) return '';
  const parts: string[] = [];
  if (etik.aim?.trim()) parts.push(`Amaç: ${etik.aim.trim()}`);
  for (const h of etik.hypotheses ?? []) {
    if (h?.trim()) parts.push(h.trim());
  }
  if (etik.scale_names?.length) {
    parts.push(`Ölçekler: ${etik.scale_names.join(', ')}`);
  }
  if (!parts.length) {
    return 'Etik kurul belgesi yüklendi ancak metin çıkarılamadı.';
  }
  return parts.join('\n');
}

export function normalizeColumnHint(hint: string): string {
  return hint.toLowerCase().replace(/[^a-z0-9_]/g, '');
}

export function matchColumnHint(columns: string[], hint: string): string | undefined {
  const norm = normalizeColumnHint(hint);
  if (!norm) return undefined;
  const exact = columns.find((c) => normalizeColumnHint(c) === norm);
  if (exact) return exact;
  return columns.find((c) => {
    const cn = normalizeColumnHint(c);
    return cn.includes(norm) || norm.includes(cn);
  });
}

export function scalesFromOneriOlcekler(
  olcekler: AnalizOneriScale[],
  columns: string[],
): DetectedScale[] {
  const itemPattern = /_\d+(_ters|_T)?$/i;
  const out: DetectedScale[] = [];
  for (const scale of olcekler ?? []) {
    const prefix = (scale.maddeler_prefix || scale.ad || '').trim();
    if (!prefix) continue;
    const pfx = prefix.toLowerCase();
    const items = columns.filter(
      (c) => c.toLowerCase().startsWith(pfx) && itemPattern.test(c),
    );
    if (items.length < 2) continue;
    out.push({
      name: scale.ad || prefix.toUpperCase(),
      id: pfx,
      items,
      cronbach_items: items,
      source: 'oneri',
      registry_confidence: 'medium',
    });
  }
  return out;
}

export function researchTopicFromOneri(
  oneri: AnalizOneriResult | null,
  etik?: EtikKurulParseResult | null,
): string {
  const hyps = (etik?.hypotheses ?? []).filter(Boolean);
  if (hyps.length) return hyps.join('\n');
  if (etik?.aim?.trim()) return etik.aim.trim();
  if (oneri?.ozet?.trim()) return oneri.ozet.trim();
  const lines = (oneri?.gerekceler ?? [])
    .map((g) => g.analiz)
    .filter(Boolean) as string[];
  return lines.join('\n');
}
