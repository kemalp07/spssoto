import { useAppStore } from '../../stores/useAppStore';

function confClass(c?: string) {
  if (c === 'high') return 'confHigh';
  if (c === 'medium') return 'confMedium';
  return 'confLow';
}

function confLabel(c?: string) {
  if (c === 'high') return '✓ Güvenilir';
  if (c === 'medium') return '~ Olası';
  return '? Belirsiz';
}

export function ScaleMatchPanel() {
  const matches = useAppStore((s) => s.scales.matchResults);
  const unmatched = useAppStore((s) => s.scales.unmatchedColumns);

  if (!matches.length) return null;

  return (
    <div className="scaleMatchPanel mb2">
      <div className="panel">
        <div className="panelTitle">🔗 Ölçek → Kolon Eşleştirmesi</div>
        <p className="panelDesc">
          Ölçekler veritabanından otomatik tanındı; kolonlar buna göre eşleştirildi.
          Yanlış eşleşmeleri düzeltebilirsiniz.
        </p>
        {matches.map((match) => (
          <div key={match.scale_name} className="scaleMatchCard">
            <div className="scaleMatchHead">
              <span className="scaleMatchName">{match.scale_name}</span>
              <span className={`confBadge ${confClass(match.confidence)}`}>
                {confLabel(match.confidence)}
              </span>
            </div>
            {match.total_columns?.length ? (
              <div className="scaleMatchDetail">
                Toplam puan:{' '}
                {match.total_columns.map((c) => (
                  <code key={c}>{c}</code>
                ))}
              </div>
            ) : null}
            {match.item_columns?.length ? (
              <div className="scaleMatchDetail">
                Maddeler ({match.item_columns.length}):{' '}
                {match.item_columns.slice(0, 5).map((c) => (
                  <code key={c}>{c}</code>
                ))}
                {match.item_columns.length > 5 ? (
                  <span>{` +${match.item_columns.length - 5} daha`}</span>
                ) : null}
              </div>
            ) : null}
            {!match.matched_columns?.length ? (
              <div className="scaleMatchDetail textDanger">
                ⚠️ Eşleşen kolon bulunamadı — kolon adlarını kontrol edin
              </div>
            ) : null}
          </div>
        ))}
        {unmatched.length ? (
          <div className="textXs textMuted mt2">
            Eşleşmeyen kolonlar (demografik/diğer):{' '}
            {unmatched.slice(0, 8).join(', ')}
            {unmatched.length > 8 ? '...' : ''}
          </div>
        ) : null}
      </div>
    </div>
  );
}
