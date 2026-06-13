export function escHtml(text: unknown): string {
  const s = String(text ?? '');
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function escAttr(text: unknown): string {
  return escHtml(text).replace(/'/g, '&#39;');
}

export function normalizeDecimalValue(val: unknown): unknown {
  if (val === '' || val === null || val === undefined) return val;
  if (typeof val === 'number') return val;
  const s = String(val).trim();
  if (/^-?\d{1,3}(\.\d{3})+,\d+$/.test(s)) return s.replace(/\./g, '').replace(',', '.');
  if (/^-?\d+,\d+$/.test(s)) return s.replace(',', '.');
  return val;
}
