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

export function VariableCard({ col, type, rec = {}, checked, onToggle }: VariableCardProps) {
  const userLabels = useAppStore((s) => s.variables.userLabels);
  const parsedData = useAppStore((s) => s.parsedData);
  const valueLabels = useAppStore((s) => s.savMetadata.valueLabels);
  const derivedVarMap = useAppStore((s) => s.variables.derivedVarMap) as Record<string, DerivedVariable>;

  const d = derivedVarMap[col];
  const aiStatus = resolveAiStatus(col, rec, derivedVarMap);
  const badge = AI_STATUS_LABELS[aiStatus];
  const isExcludedDerived = type === 'cont' && (d?.action === 'exclude' || aiStatus === 'not_recommended');
  const reviewOpen = aiStatus === 'review';
  const label = (userLabels[col] ?? '').trim() || col;
  const summary = variableSummaryText(col, parsedData, valueLabels);

  return (
    <label
      className={[
        'colCheckbox',
        checked ? 'selected' : '',
        isExcludedDerived ? 'colCheckboxDim' : '',
        reviewOpen ? 'colCheckboxReviewOpen' : '',
      ].filter(Boolean).join(' ')}
    >
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
  );
}
