import { useMemo } from 'react';
import { getLabelPhaseColumns, isLabelComplete } from '../../lib/labels';
import { useAppStore } from '../../stores/useAppStore';

export function LabelEditor() {
  const columns = useAppStore((s) => s.columns);
  const parsedData = useAppStore((s) => s.parsedData);
  const userLabels = useAppStore((s) => s.variables.userLabels);
  const pendingLabels = useAppStore((s) => s.savMetadata.pendingLabels);
  const showAll = useAppStore((s) => s.variables.showAllLabelRows);
  const setShowAll = useAppStore((s) => s.setShowAllLabelRows);
  const updateVariable = useAppStore((s) => s.updateVariable);

  const allCols = useMemo(() => getLabelPhaseColumns(columns), [columns]);
  const emptyCols = useMemo(
    () => allCols.filter((col) => !isLabelComplete(col, userLabels, pendingLabels)),
    [allCols, userLabels, pendingLabels],
  );
  const visibleCols = (showAll || emptyCols.length === 0) ? allCols : emptyCols;
  const showToggle = !showAll && emptyCols.length > 0 && emptyCols.length !== allCols.length;

  return (
    <>
      {showToggle ? (
        <button
          type="button"
          className="labelShowAllLink"
          onClick={() => setShowAll(true)}
        >
          Tümünü göster
        </button>
      ) : null}
      <div className="labelPhaseGrid">
        {visibleCols.map((col) => {
          const samples = [...new Set(
            (parsedData.length ? parsedData : []).slice(0, 5)
              .map((r) => r[col])
              .filter((v) => v !== '' && v != null),
          )].slice(0, 4);
          const value = userLabels[col] ?? pendingLabels[col] ?? col;
          return (
            <div key={col} className="labelRow">
              <span className="labelRowCode">{col}</span>
              <span className="textXs textMuted">{samples.join(', ') || '—'}</span>
              <input
                type="text"
                className="formInput formInputSm"
                placeholder="Türkçe isim girin"
                value={value}
                onChange={(e) => updateVariable(col, e.target.value.trim() || col)}
              />
            </div>
          );
        })}
      </div>
    </>
  );
}
