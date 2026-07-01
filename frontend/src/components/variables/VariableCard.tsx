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

function currentRole(
  col: string,
  catColumns: string[],
  contColumns: string[],
  userExcluded: Set<string>,
): VariableRole {
  if (userExcluded.has(col)) return 'exclude';
  if (catColumns.includes(col)) return 'grouping';
  if (contColumns.includes(col)) return 'outcome';
  return 'exclude';
}

function moveVariableRole(col: string, role: VariableRole, displayType: 'cat' | 'cont') {
  useAppStore.setState((s) => {
    const userExcluded = new Set(s.variables.userExcluded);
    let catColumns = [...s.variables.catColumns];
    let contColumns = [...s.variables.contColumns];
    const selectedCat = new Set(s.variables.selectedCat);
    const selectedCont = new Set(s.variables.selectedCont);

    if (role === 'exclude') {
      userExcluded.add(col);
      selectedCat.delete(col);
      selectedCont.delete(col);
      if (displayType === 'cat' && !catColumns.includes(col)) {
        catColumns.push(col);
      }
      if (displayType === 'cont' && !contColumns.includes(col)) {
        contColumns.push(col);
      }
    } else {
      userExcluded.delete(col);
      catColumns = catColumns.filter((c) => c !== col);
      contColumns = contColumns.filter((c) => c !== col);
      selectedCat.delete(col);
      selectedCont.delete(col);
      if (role === 'grouping') {
        catColumns.push(col);
        selectedCat.add(col);
      } else {
        contColumns.push(col);
        selectedCont.add(col);
      }
    }

    return {
      variables: {
        ...s.variables,
        catColumns,
        contColumns,
        selectedCat,
        selectedCont,
        userExcluded,
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
  const userExcluded = useAppStore((s) => s.variables.userExcluded);

  const d = derivedVarMap[col];
  const aiStatus = resolveAiStatus(col, rec, derivedVarMap);
  const badge = AI_STATUS_LABELS[aiStatus];
  const isExcludedDerived = d?.action === 'exclude';
  const isUserExcluded = userExcluded.has(col);
  const reviewOpen = aiStatus === 'review';
  const label = (userLabels[col] ?? '').trim() || col;
  const summary = variableSummaryText(col, parsedData, valueLabels);
  const role = currentRole(col, catColumns, contColumns, userExcluded);

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
        opacity: isUserExcluded ? 0.4 : undefined,
      }}
    >
      <label
        className="colCheckboxMain"
        style={{
          display: 'flex',
          gap: 10,
          flex: 1,
          cursor: 'pointer',
          width: '100%',
          alignItems: 'flex-start',
        }}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={isUserExcluded}
        />
        <div className="flex1">
          <div className="colName">{label}</div>
          <div className="colCode">{col}</div>
          <div className="colSample">{summary}</div>
          {isUserExcluded ? (
            <div className="textXs textMuted" style={{ marginTop: 4, fontWeight: 600 }}>
              Dahil edilmeyecek
            </div>
          ) : null}
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
          onChange={(e) => moveVariableRole(col, e.target.value as VariableRole, type)}
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
