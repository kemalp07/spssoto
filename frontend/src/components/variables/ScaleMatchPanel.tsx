import { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import type { ScaleMatch } from '../../types';

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

function saveScaleItemColumns(scaleName: string, itemColumns: string[]) {
  useAppStore.setState((s) => ({
    scales: {
      ...s.scales,
      matchResults: s.scales.matchResults.map((match) => {
        if (match.scale_name !== scaleName) return match;
        const totalCols = match.total_columns ?? [];
        const matched_columns = [...new Set([...totalCols, ...itemColumns])];
        return {
          ...match,
          item_columns: itemColumns,
          matched_columns,
          item_count: itemColumns.length,
        };
      }),
    },
  }));
}

export function ScaleMatchPanel() {
  const matches = useAppStore((s) => s.scales.matchResults);
  const allColumns = useAppStore((s) => s.columns);
  const unmatched = useAppStore((s) => s.scales.unmatchedColumns);
  const [editingScale, setEditingScale] = useState<string | null>(null);
  const [draftColumns, setDraftColumns] = useState<string[]>([]);

  if (!matches.length) return null;

  const openEditor = (match: ScaleMatch) => {
    setEditingScale(match.scale_name);
    setDraftColumns([...(match.item_columns ?? [])]);
  };

  const cancelEditor = () => {
    setEditingScale(null);
    setDraftColumns([]);
  };

  const saveEditor = () => {
    if (!editingScale) return;
    saveScaleItemColumns(editingScale, draftColumns);
    cancelEditor();
  };

  const toggleColumn = (col: string, checked: boolean) => {
    setDraftColumns((prev) => {
      if (checked) return prev.includes(col) ? prev : [...prev, col];
      return prev.filter((c) => c !== col);
    });
  };

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

            {editingScale === match.scale_name ? (
              <div
                style={{
                  marginTop: 12,
                  padding: 12,
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg)',
                }}
              >
                <div className="textSm" style={{ marginBottom: 8, fontWeight: 500 }}>
                  Madde kolonlarını seçin
                </div>
                <div
                  style={{
                    maxHeight: 200,
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    marginBottom: 12,
                  }}
                >
                  {allColumns.map((col) => (
                    <label
                      key={col}
                      style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}
                    >
                      <input
                        type="checkbox"
                        checked={draftColumns.includes(col)}
                        onChange={(e) => toggleColumn(col, e.target.checked)}
                      />
                      <code>{col}</code>
                    </label>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" className="btn btnPrimary" onClick={saveEditor}>
                    Kaydet
                  </button>
                  <button type="button" className="btn btnGhost" onClick={cancelEditor}>
                    İptal
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="btn btnGhost"
                style={{
                  marginTop: 10,
                  height: 32,
                  fontSize: 12,
                  border: '1px solid var(--border)',
                }}
                onClick={() => openEditor(match)}
              >
                Maddeleri Düzenle
              </button>
            )}
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
