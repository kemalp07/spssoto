import type { AnalysisResult } from '../types';

export function splitApaTitle(title: unknown): { num: string; caption: string } {
  const t = String(title ?? '');
  const plain = t.replace(/<\/?em>/gi, '');
  const m = plain.match(/^(Tablo\s+\d+)\.\s*(.*)$/i);
  if (!m) return { num: t, caption: '' };
  const capMatch = t.match(/^Tablo\s+\d+\.\s*(.*)$/i);
  return { num: m[1], caption: capMatch ? capMatch[1].trim() : m[2] };
}

export function stripHtml(s: unknown): string {
  return String(s).replace(/<[^>]+>/g, '');
}

export function getTableCaption(
  result: AnalysisResult,
  index: number,
  customTitles: Record<string, string>,
): string {
  if (customTitles[String(index)]) return customTitles[String(index)];
  const { caption } = splitApaTitle(result.title ?? '');
  return caption || stripHtml(result.title ?? '');
}
