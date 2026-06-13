import { useState } from 'react';
import { runMultipleRegression } from '../../hooks/useAnalysis';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';

export function RegressionPanel() {
  const columns = useAppStore((s) => [...s.variables.selectedCont].filter((c) => s.columns.includes(c)));
  const userLabels = useAppStore((s) => s.variables.userLabels);
  const [predictors, setPredictors] = useState<string[]>([]);
  const [outcome, setOutcome] = useState('');
  const [loading, setLoading] = useState(false);

  if (columns.length < 2) return null;

  const togglePredictor = (col: string) => {
    setPredictors((prev) => (
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    ));
  };

  const handleRun = async () => {
    setLoading(true);
    try {
      await runMultipleRegression(predictors, outcome);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="regPanel mb2">
      <div className="panelTitle">📈 Çoklu Doğrusal Regresyon</div>
      <p className="panelDesc">
        Birden fazla sürekli yordayıcı ve bir sonuç değişkeni seçerek OLS regresyonu çalıştırın.
      </p>
      <div className="regGrid">
        <div>
          <label className="regLabel">Yordayıcılar</label>
          <div className="regCheckboxList">
            {columns.map((col) => (
              <label key={col} className="regCheckItem">
                <input
                  type="checkbox"
                  checked={predictors.includes(col)}
                  onChange={() => togglePredictor(col)}
                />
                {userLabels[col] || col} ({col})
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="regLabel" htmlFor="regOutcome">Sonuç değişkeni</label>
          <select
            id="regOutcome"
            className="formInput"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
          >
            <option value="">Seçin</option>
            {columns.map((col) => (
              <option key={col} value={col}>
                {userLabels[col] || col} ({col})
              </option>
            ))}
          </select>
        </div>
      </div>
      <LoadingButton variant="primary" loading={loading} onClick={() => void handleRun()}>
        Regresyon Çalıştır
      </LoadingButton>
    </div>
  );
}
