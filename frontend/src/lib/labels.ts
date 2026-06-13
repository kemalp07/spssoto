import { EXCLUDE_PATTERNS, ITEM_COL_PATTERN } from './constants';

export function getLabelPhaseColumns(columns: string[]): string[] {
  return columns.filter(
    (col) => !ITEM_COL_PATTERN.test(col) && !EXCLUDE_PATTERNS.some((p) => p.test(col)),
  );
}

export function isLabelComplete(
  col: string,
  userLabels: Record<string, string>,
  pendingLabels: Record<string, string> = {},
): boolean {
  const label = (userLabels[col] ?? pendingLabels[col] ?? '').trim();
  if (!label) return false;
  if (label === col) return false;
  return true;
}

export function shouldSkipLabelsPhase(
  columns: string[],
  userLabels: Record<string, string>,
  pendingLabels: Record<string, string> = {},
): boolean {
  const cols = getLabelPhaseColumns(columns);
  return cols.length > 0 && cols.every((col) => isLabelComplete(col, userLabels, pendingLabels));
}

export function getMissingLabelColumns(
  columns: string[],
  userLabels: Record<string, string>,
  pendingLabels: Record<string, string> = {},
): string[] {
  return getLabelPhaseColumns(columns).filter(
    (col) => !isLabelComplete(col, userLabels, pendingLabels),
  );
}

export function checkRequiredLabels(
  selectedCat: Set<string>,
  selectedCont: Set<string>,
  userLabels: Record<string, string>,
  nonItemColumns: Set<string>,
): string[] {
  const allSelected = [...selectedCat, ...selectedCont].filter((col) => nonItemColumns.has(col));
  return allSelected.filter((col) => {
    const label = (userLabels[col] ?? '').trim();
    return !label || label === col;
  });
}
