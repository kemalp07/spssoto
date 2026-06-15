import type { BulguEntry } from '../types';

export const BULGU_PERSIST_KEY = 'statai-results';

export function clearBulguPersistStorage(): void {
  try {
    localStorage.removeItem(BULGU_PERSIST_KEY);
  } catch {
    /* ignore */
  }
}

export function normalizeBulguEntry(value: unknown): BulguEntry | null {
  if (!value) return null;
  if (typeof value === 'string') {
    return {
      text: value,
      lockedAt: new Date().toISOString(),
      version: 1,
      isLocked: false,
      previousVersions: [],
    };
  }
  if (typeof value === 'object' && value !== null && 'text' in value) {
    const entry = value as BulguEntry;
    return {
      text: String(entry.text ?? ''),
      lockedAt: entry.lockedAt ?? new Date().toISOString(),
      version: entry.version ?? 1,
      isLocked: Boolean(entry.isLocked),
      previousVersions: entry.previousVersions ?? [],
    };
  }
  return null;
}

export function bulgularForApi(
  bulgular: Record<string, BulguEntry | string>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(bulgular)) {
    const entry = typeof value === 'string' ? normalizeBulguEntry(value) : value;
    if (entry?.text) out[key] = entry.text;
  }
  return out;
}

export function bulgularForWordExport(
  bulgular: Record<string, BulguEntry | string>,
): Record<string, { text: string; version: number; lockedAt: string }> {
  const out: Record<string, { text: string; version: number; lockedAt: string }> = {};
  for (const [key, value] of Object.entries(bulgular)) {
    const entry = typeof value === 'string' ? normalizeBulguEntry(value) : value;
    if (!entry?.text) continue;
    out[key] = {
      text: entry.text,
      version: entry.version,
      lockedAt: entry.lockedAt,
    };
  }
  return out;
}

export function formatBulguDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('tr-TR', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  } catch {
    return iso;
  }
}

export function migratePersistedBulgular(
  bulgular: Record<string, unknown> | undefined,
): Record<string, BulguEntry> {
  if (!bulgular) return {};
  const migrated: Record<string, BulguEntry> = {};
  for (const [key, value] of Object.entries(bulgular)) {
    const entry = normalizeBulguEntry(value);
    if (entry) migrated[key] = entry;
  }
  return migrated;
}
