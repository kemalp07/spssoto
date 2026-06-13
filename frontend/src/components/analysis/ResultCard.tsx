import { ApaTable } from '../analysis/ApaTable';
import type { AnalysisResult } from '../../types';

interface ResultCardProps {
  result: AnalysisResult;
  bulgu?: string;
}

export function ResultCard({ result, bulgu }: ResultCardProps) {
  const sigBadge = result.significant !== undefined ? (
    <span className={`sigBadge ${result.significant ? 'yes' : 'no'}`}>
      {result.significant ? 'p < .05' : 'ns'}
    </span>
  ) : null;

  return (
    <div className="resultCard">
      <div className="resultBody">
        {sigBadge ? (
          <div className="resultBadges">{sigBadge}</div>
        ) : null}
        <ApaTable result={result} />
        <div className="bulguBox">
          <div className="bulguLabel">✨ Bulgu</div>
          {bulgu ? (
            <p className="bulguText">{bulgu}</p>
          ) : (
            <p className="bulguLoading">
              Bulgular bekleniyor. Oluşturmak için &quot;Tüm Bulguları Yaz&quot; butonuna basın.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
