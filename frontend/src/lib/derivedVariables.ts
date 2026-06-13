import type { DataRow, DerivedVariable, MissingDataEntry } from '../types';

export function computeMissingData(cols: string[], parsedData: DataRow[]): MissingDataEntry[] {
  const total = parsedData.length;
  if (!total) return [];
  return cols.map((col) => {
    const missing = parsedData.filter(
      (r) => r[col] === '' || r[col] === null || r[col] === undefined,
    ).length;
    const pct = Math.round((missing / total) * 1000) / 10;
    let warning: MissingDataEntry['warning'] = 'none';
    if (pct > 30) warning = 'high';
    else if (pct > 10) warning = 'medium';
    return { column: col, missing_pct: pct, missing_n: missing, warning };
  });
}

export interface DerivedPlacementResult {
  derivedVarMap: Record<string, DerivedVariable>;
  userLabels: Record<string, string>;
  catColumns: string[];
  contColumns: string[];
  selectedCat: Set<string>;
  selectedCont: Set<string>;
}

export function applyDerivedPlacements(
  derivedList: DerivedVariable[],
  state: {
    derivedVarMap: Record<string, DerivedVariable>;
    userLabels: Record<string, string>;
    catColumns: string[];
    contColumns: string[];
    selectedCat: Set<string>;
    selectedCont: Set<string>;
  },
): DerivedPlacementResult {
  const derivedVarMap: Record<string, DerivedVariable> = { ...state.derivedVarMap };
  const userLabels = { ...state.userLabels };
  let catColumns = [...state.catColumns];
  let contColumns = [...state.contColumns];
  const selectedCat = new Set(state.selectedCat);
  const selectedCont = new Set(state.selectedCont);

  (derivedList ?? []).forEach((d) => {
    derivedVarMap[d.name] = d;
    if (d.derived_label) {
      const cur = (userLabels[d.name] ?? '').trim();
      if (!cur || cur === d.name) userLabels[d.name] = d.derived_label;
    }
    if (d.action === 'move_to_grouping') {
      contColumns = contColumns.filter((c) => c !== d.name);
      selectedCont.delete(d.name);
      if (!catColumns.includes(d.name)) catColumns.push(d.name);
      selectedCat.add(d.name);
    } else if (d.action === 'exclude') {
      catColumns = catColumns.filter((c) => c !== d.name);
      selectedCat.delete(d.name);
      if (!contColumns.includes(d.name)) contColumns.push(d.name);
      selectedCont.delete(d.name);
    }
  });

  return { derivedVarMap, userLabels, catColumns, contColumns, selectedCat, selectedCont };
}

export function buildVariablesForDerivedDetection(
  catColumns: string[],
  contColumns: string[],
  userLabels: Record<string, string>,
  parsedData: DataRow[],
) {
  const cols = [...new Set([...catColumns, ...contColumns])];
  return cols.map((name) => {
    const vals = parsedData.map((r) => r[name]).filter((v) => v !== '' && v != null);
    const numeric = vals.filter((v) => !Number.isNaN(parseFloat(String(v))));
    const nuniq = new Set(vals.map((v) => String(v))).size;
    const type = (numeric.length / Math.max(vals.length, 1) > 0.8 && nuniq > 8)
      ? 'continuous'
      : 'categorical';
    const role = catColumns.includes(name) ? 'grouping' : 'outcome';
    return {
      name,
      label: userLabels[name] ?? name,
      type,
      role,
      included: true,
    };
  });
}
