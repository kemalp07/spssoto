import { resolveAiStatus } from '../../lib/classify';
import { useAppStore } from '../../stores/useAppStore';
import type { ColumnRecommendation } from '../../types';
import { VariableCard } from './VariableCard';

interface SelectionGridProps {
  title: string;
  type: 'cat' | 'cont';
  columns: string[];
  recommendations: Record<string, ColumnRecommendation>;
}

export function SelectionGrid({ title, type, columns, recommendations }: SelectionGridProps) {
  const selected = useAppStore((s) => (
    type === 'cat' ? s.variables.selectedCat : s.variables.selectedCont
  ));
  const derivedVarMap = useAppStore((s) => s.variables.derivedVarMap);
  const toggle = useAppStore((s) => s.toggleColumnSelection);

  return (
    <div className="selectionSection">
      <h3 className="selectionTitle">{title}</h3>
      <div className="colGrid">
        {columns.length ? columns.map((col) => {
          const rec = recommendations[col] ?? {};
          const aiStatus = resolveAiStatus(col, rec, derivedVarMap);
          const d = derivedVarMap[col];
          const isExcludedDerived = type === 'cont'
            && (d?.action === 'exclude' || aiStatus === 'not_recommended');
          const status = rec.status ?? 'optional';
          const checked = type === 'cat'
            ? aiStatus !== 'not_recommended' && status !== 'skip' && selected.has(col)
            : !isExcludedDerived && selected.has(col);

          return (
            <VariableCard
              key={col}
              col={col}
              type={type}
              rec={rec}
              checked={checked}
              onToggle={(v) => toggle(type, col, v)}
            />
          );
        }) : (
          <p className="textSm textMuted">
            {type === 'cat' ? 'Gruplandırma değişkeni bulunamadı.' : 'Analiz değişkeni bulunamadı.'}
          </p>
        )}
      </div>
    </div>
  );
}
