import {
  GROUPING_PATTERNS,
  OUTCOME_CAT_PATTERNS,
  OUTCOME_CONT_PATTERNS,
} from './constants';
import { normalizeDecimalValue } from './formatting';
import type { AnalysisVariable, DataRow } from '../types';

export function getValueLabelsForCol(
  col: string,
  valueLabels: Record<string, Record<string, string>>,
): Record<string, string> | null {
  if (!valueLabels[col]) return null;
  return Object.fromEntries(
    Object.entries(valueLabels[col]).map(([k, v]) => [String(k), String(v)]),
  );
}

function inferTypeAndRole(
  col: string,
  parsedData: DataRow[],
  defaultRole: 'grouping' | 'outcome',
): Pick<AnalysisVariable, 'type' | 'role'> {
  const isGroupingMeas = GROUPING_PATTERNS.some((p) => p.test(col));
  const vals = [...new Set(
    parsedData.slice(0, 20).map((r) => r[col]).filter((v) => v !== '' && v != null),
  )];
  const numericCount = vals.filter(
    (v) => !Number.isNaN(parseFloat(String(v).replace(',', '.'))),
  ).length;
  const isNumeric = vals.length > 0 && numericCount / vals.length > 0.8;
  const hasWideRange = isNumeric && vals.some(
    (v) => (parseFloat(String(v).replace(',', '.')) || 0) > 10,
  );

  if (OUTCOME_CAT_PATTERNS.some((p) => p.test(col))) {
    return { type: 'categorical', role: 'outcome' };
  }
  if (OUTCOME_CONT_PATTERNS.some((p) => p.test(col))) {
    return { type: 'continuous', role: 'outcome' };
  }

  if (defaultRole === 'grouping' && !isGroupingMeas) {
    return { type: 'categorical', role: 'grouping' };
  }

  const type = (isNumeric && hasWideRange) ? 'continuous' : 'categorical';
  let role: AnalysisVariable['role'] = defaultRole;
  if (defaultRole === 'outcome' && isGroupingMeas) role = 'grouping';
  return { type, role };
}

export function buildVariables(input: {
  selectedCat: Set<string>;
  selectedCont: Set<string>;
  userLabels: Record<string, string>;
  parsedData: DataRow[];
  valueLabels: Record<string, Record<string, string>>;
}): AnalysisVariable[] {
  const { selectedCat, selectedCont, userLabels, parsedData, valueLabels } = input;

  const toVar = (col: string, defaultRole: 'grouping' | 'outcome'): AnalysisVariable => {
    const { type, role } = inferTypeAndRole(col, parsedData, defaultRole);
    return {
      name: col,
      label: userLabels[col] || col,
      type,
      role,
      included: true,
      value_labels: getValueLabelsForCol(col, valueLabels),
    };
  };

  return [
    ...[...selectedCat].map((col) => toVar(col, 'grouping')),
    ...[...selectedCont].map((col) => toVar(col, 'outcome')),
  ];
}

export function buildAnalysisData(
  variables: AnalysisVariable[],
  parsedData: DataRow[],
): Array<{ values: Record<string, unknown> }> {
  return parsedData.map((row) => {
    const clean: Record<string, unknown> = {};
    variables.forEach((v) => {
      let val = row[v.name];
      if (typeof val === 'string') val = normalizeDecimalValue(val);
      clean[v.name] = val;
    });
    return { values: clean };
  });
}
