import { regenerateBulguAt } from '../../hooks/useBulgu';
import { formatBulguDate, normalizeBulguEntry } from '../../lib/bulgu';
import { useAppStore } from '../../stores/useAppStore';
import type { AnalysisResult, BulguEntry } from '../../types';
import { ApaTable } from '../analysis/ApaTable';

interface ResultCardProps {
  result: AnalysisResult;
  index: number;
  bulgu?: BulguEntry | string;
}

export function ResultCard({ result, index, bulgu: bulguProp }: ResultCardProps) {
  const lockBulgu = useAppStore((s) => s.lockBulgu);
  const unlockBulgu = useAppStore((s) => s.unlockBulgu);
  const bulguLoading = useAppStore((s) => s.results.bulguLoading);

  const bulgu = normalizeBulguEntry(bulguProp);

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
          {bulgu ? (
            <>
              <div className="bulguHeader">
                <span className="bulguMeta">
                  v{bulgu.version} · {formatBulguDate(bulgu.lockedAt)}
                </span>
                <div className="bulguActions">
                  {bulgu.isLocked ? (
                    <>
                      <span className="badge badgeLocked">Kilitli</span>
                      <button
                        type="button"
                        onClick={() => unlockBulgu(index)}
                        className="btn btnGhost btnSm"
                      >
                        Kilidi Kaldır
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => lockBulgu(index)}
                        className="btn btnSuccess btnSm"
                      >
                        Kilitle
                      </button>
                      <button
                        type="button"
                        onClick={() => void regenerateBulguAt(index)}
                        className="btn btnGhost btnSm"
                        disabled={bulguLoading}
                      >
                        Yeniden Yaz
                      </button>
                    </>
                  )}
                </div>
              </div>
              <p className="bulguText">{bulgu.text}</p>
              {bulgu.previousVersions?.length ? (
                <details className="bulguHistory">
                  <summary className="textXs textMuted">Önceki versiyonlar</summary>
                  {bulgu.previousVersions.map((prev, i) => (
                    <p key={i} className="bulguText bulguTextMuted">{prev}</p>
                  ))}
                </details>
              ) : null}
            </>
          ) : (
            <>
              <div className="bulguLabel">Bulgu</div>
              <p className="bulguLoading">
                Bulgular bekleniyor. Oluşturmak için &quot;Tüm Bulguları Yaz&quot; butonuna basın.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
