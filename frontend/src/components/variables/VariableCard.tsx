import { AI_STATUS_LABELS, resolveAiStatus } from '../../lib/classify';
import { variableSummaryText } from '../../lib/variableSummary';
import { useAppStore } from '../../stores/useAppStore';
import type { ColumnRecommendation, DerivedVariable } from '../../types';

interface VariableCardProps {
  col: string;
  type: 'cat' | 'cont';
  rec?: ColumnRecommendation;
  checked: boolean;
  onToggle: (checked: boolean) => void;
}

type VariableRole = 'grouping' | 'outcome' | 'exclude';

function currentRole(col: string, catColumns: string[], contColumns: string[]): VariableRole {
  if (catColumns.includes(col)) return 'grouping';
  if (contColumns.includes(col)) return 'outcome';
  return 'exclude';
}

function moveVariableRole(col: string, role: VariableRole) {
  useAppStore.setState((s) => {
    let catColumns = s.variables.catColumns.filter((c) => c !== col);
    let contColumns = s.variables.contColumns.filter((c) => c !== col);
    const selectedCat = new Set(s.variables.selectedCat);
    const selectedCont = new Set(s.variables.selectedCont);
    selectedCat.delete(col);
    selectedCont.delete(col);

    if (role === 'grouping') {
      catColumns = [...catColumns, col];
      selectedCat.add(col);
    } else if (role === 'outcome') {
      contColumns = [...contColumns, col];
      selectedCont.add(col);
    }

    return {
      variables: {
        ...s.variables,
        catColumns,
        contColumns,
        selectedCat,
        selectedCont,
      },
    };
  });
}

export function VariableCard({ col, type, rec = {}, checked, onToggle }: VariableCardProps) {
  const userLabels = useAppStore((s) => s.variables.userLabels);
  const parsedData = useAppStore((s) => s.parsedData);
  const valueLabels = useAppStore((s) => s.savMetadata.valueLabels);
  const derivedVarMap = useAppStore((s) => s.variables.derivedVarMap) as Record<string, DerivedVariable>;
  const catColumns = useAppStore((s) => s.variables.catColumns);
  const contColumns = useAppStore((s) => s.variables.contColumns);

  const d = derivedVarMap[col];
  const aiStatus = resolveAiStatus(col, rec, derivedVarMap);
  const badge = AI_STATUS_LABELS[aiStatus];
  const isExcludedDerived = d?.action === 'exclude';
  const reviewOpen = aiStatus === 'review';
  const label = (userLabels[col] ?? '').trim() || col;
  const summary = variableSummaryText(col, parsedData, valueLabels);
  const role = currentRole(col, catColumns, contColumns);

  return (
    <div
      className={[
        'colCheckbox',
        checked ? 'selected' : '',
        isExcludedDerived ? 'colCheckboxDim' : '',
        reviewOpen ? 'colCheckboxReviewOpen' : '',
      ].filter(Boolean).join(' ')}
      style={{
        flexDirection: 'column',
        alignItems: 'stretch',
      }}
    >
      <label className="colCheckboxMain" style={{ display: 'flex', gap: 10, flex: 1, cursor: 'pointer', width: '100%' }}>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onToggle(e.target.checked)}
        />
        <div className="flex1">
          <div className="colName">{label}</div>
          <div className="colCode">{col}</div>
          <div className="colSample">{summary}</div>
          {d && d.action !== 'exclude' ? (
            <div className="derivedSource">Kaynak: {d.source ?? '—'}</div>
          ) : null}
          {isExcludedDerived ? (
            <div className="derivedSource">
              Kaynak: {d?.source ?? rec.source ?? '—'} · analiz dışı bırakın
            </div>
          ) : null}
          {rec.reason ? (
            <div className="textXs textMuted reasonNote">{rec.reason}</div>
          ) : null}
        </div>
        {d && d.action !== 'exclude' ? (
          <>
            <span className="badgeDerived">Türev</span>
            <span className={badge.cls}>{badge.label}</span>
          </>
        ) : (
          <span className={badge.cls}>{badge.label}</span>
        )}
      </label>
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginTop: 8,
          marginLeft: 'auto',
          width: 'fit-content',
          backgroundColor: '#ffffff',
          borderRadius: 4,
        }}
      >
        <select
          value={role}
          onChange={(e) => moveVariableRole(col, e.target.value as VariableRole)}
          onClick={(e) => e.stopPropagation()}
          onMouseDown={(e) => e.stopPropagation()}
          aria-label={`${col} değişken türü`}
          style={{
            display: 'block',
            fontSize: 11,
            padding: '2px 6px',
            border: '1px solid #d1d5db',
            borderRadius: 4,
            backgroundColor: '#ffffff',
            cursor: 'pointer',
            width: 'fit-content',
            color: 'var(--text)',
          }}
        >
          <option value="grouping">Gruplandırma</option>
          <option value="outcome">Analiz (bağımlı)</option>
          <option value="exclude">Dahil etme</option>
        </select>
      </div>
    </div>
  );
}
