import { useState } from 'react';
import { runMultipleRegression } from '../../hooks/useAnalysis';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';

export function RegressionPanel() {
  const selectedCont = useAppStore((s) => s.variables.selectedCont);
  const allColumns = useAppStore((s) => s.columns);
  const userLabels = useAppStore((s) => s.variables.userLabels);
  const columns = [...selectedCont].filter((c) => allColumns.includes(c));

  const [open, setOpen] = useState(false);
  const [predictors, setPredictors] = useState<string[]>([]);
  const [outcome, setOutcome] = useState('');
  const [loading, setLoading] = useState(false);

  if (columns.length < 2) return null;

  const togglePredictor = (col: string) => {
    setPredictors((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col],
    );
  };

  const handleRun = async () => {
    setLoading(true);
    try {
      await runMultipleRegression(predictors, outcome);
    } finally {
      setLoading(false);
    }
  };

  const getLabel = (col: string) => userLabels[col] || col;

  return (
    <div className="regPanel mb2">
      <button
        type="button"
        className="regPanelToggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="regPanelTitle">📈 Etki Analizi</span>
        <span className="regPanelHint">
          Hangi değişkenler birbirini etkiliyor?
        </span>
        <span className="regPanelChevron">{open ? '▲' : '▼'}</span>
      </button>

      {open ? (
        <div className="regPanelBody">
          <p className="regPanelDesc">
            Örneğin: &quot;Online yemek siparişi arttıkça gece yeme de artıyor mu?&quot;
            gibi soruları test etmek için aşağıdan seçim yapın.
          </p>

          <div className="regGrid">
            <div>
              <label className="regLabel">
                Etkileyen değişkenler
                <span className="regLabelHint"> (birden fazla seçebilirsiniz)</span>
              </label>
              <div className="regCheckboxList">
                {columns.map((col) => (
                  <label key={col} className="regCheckItem">
                    <input
                      type="checkbox"
                      checked={predictors.includes(col)}
                      onChange={() => togglePredictor(col)}
                    />
                    {getLabel(col)}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="regLabel" htmlFor="regOutcome">
                Etkilenen değişken
              </label>
              <select
                id="regOutcome"
                className="formInput"
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
              >
                <option value="">Seçin</option>
                {columns
                  .filter((col) => !predictors.includes(col))
                  .map((col) => (
                    <option key={col} value={col}>
                      {getLabel(col)}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <LoadingButton
            variant="primary"
            loading={loading}
            disabled={predictors.length === 0 || !outcome}
            onClick={() => void handleRun()}
          >
            Analizi Çalıştır
          </LoadingButton>
        </div>
      ) : null}
    </div>
  );
}
