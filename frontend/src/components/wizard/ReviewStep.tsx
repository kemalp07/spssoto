import { useEffect, useState } from 'react';
import { getTableCaption } from '../../lib/apaTable';
import { alphaReliabilityBadge } from '../../lib/reviewScales';
import { downloadWord, initReviewStep } from '../../hooks/useReview';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from './StepPlaceholder';

interface ReviewStepProps {
  onBack: () => void;
}

function QualityBand() {
  const qc = useAppStore((s) => s.review.qualityCheck);
  if (!qc) return <div className="qualityBand issue">Tutarlılık kontrolü çalıştırılamadı.</div>;
  const findings = qc.findings ?? [];
  if (qc.overall === 'temiz' || !findings.length) {
    return <div className="qualityBand clean">✓ Tutarlılık kontrolü temiz</div>;
  }
  const hasError = qc.has_errors || findings.some((f) => f.severity === 'hata');
  return (
    <div className={`qualityBand ${hasError ? 'error' : 'issue'}`}>
      <strong>Tutarlılık bulguları</strong>
      {findings.map((f, i) => (
        <div key={i} className="qualityFinding">
          <span className={`qualitySev ${f.severity === 'hata' ? 'hata' : 'uyari'}`}>
            {f.severity === 'hata' ? 'Hata' : 'Uyarı'}
          </span>
          <div className="flex1">{f.message}</div>
        </div>
      ))}
    </div>
  );
}

export function ReviewStep({ onBack }: ReviewStepProps) {
  const loading = useAppStore((s) => s.review.loading);
  const wordExporting = useAppStore((s) => s.review.wordExporting);
  const scales = useAppStore((s) => s.review.scalesCache);
  const expanded = useAppStore((s) => s.review.expandedScales);
  const results = useAppStore((s) => s.results.analysis);
  const customTitles = useAppStore((s) => s.review.customTitles);
  const toggleExpanded = useAppStore((s) => s.toggleReviewScaleExpanded);
  const applyScaleName = useAppStore((s) => s.applyReviewScaleName);
  const setCustomTitle = useAppStore((s) => s.setCustomTitle);
  const hasResults = results.length > 0;
  const [editingTitle, setEditingTitle] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    if (hasResults) void initReviewStep();
  }, [hasResults]);

  return (
    <div className="reviewWrap">
      <div className="reviewHeader">
        <div className="reviewHeaderText">
          <h2>Gözden Geçir</h2>
          <p>Word çıktısından önce ölçek eşleşmelerini ve tablo başlıklarını kontrol edin.</p>
        </div>
        <LoadingButton
          variant="primary"
          loading={wordExporting}
          loadingText="Word hazırlanıyor..."
          disabled={!hasResults}
          onClick={() => void downloadWord()}
        >
          Word&apos;e Aktar
        </LoadingButton>
      </div>

      {loading ? (
        <div className="emptyState"><p>Yükleniyor...</p></div>
      ) : (
        <div id="reviewContent">
          <QualityBand />
          <div className="reviewSection">
            <div className="reviewSectionTitle">Ölçek Eşleşmeleri</div>
            {scales.length ? scales.map((s, idx) => {
              const ab = alphaReliabilityBadge(s.alpha);
              const open = expanded.has(idx);
              return (
                <div key={s.id} className={`reviewCard${open ? ' open' : ''}`}>
                  <button
                    type="button"
                    className="reviewCardHead"
                    onClick={() => toggleExpanded(idx)}
                  >
                    <div>
                      <div className="reviewScaleName">{s.displayName}</div>
                      <div className="reviewScaleMeta">
                        {s.itemCount ? `${s.itemCount} madde` : 'Madde aralığı belirsiz'}
                        {s.alpha != null ? ` · Cronbach α = ${s.alpha.toFixed(3)}` : ''}
                        {s.alpha != null ? (
                          <span className={`reviewBadge ${ab.cls}`}>{ab.label}</span>
                        ) : null}
                      </div>
                    </div>
                    <div className={`reviewStatus ${s.okMatch ? 'ok' : 'warn'}`}>
                      {s.okMatch ? '✓ Eşleşti' : '⚠ Kontrol edin'}
                    </div>
                  </button>
                  {open ? (
                    <div className="reviewCardBody">
                      <div className="textXs textMuted mb2">Eşleşen sütunlar</div>
                      <div className="reviewChips">
                        {(s.columns.length ? s.columns : s.items).map((c) => (
                          <span key={c} className="reviewChip">{c}</span>
                        ))}
                      </div>
                      <label className="regLabel">Ölçek adı</label>
                      <input
                        className="formInput"
                        type="text"
                        defaultValue={s.displayName}
                        onBlur={(e) => applyScaleName(idx, e.target.value)}
                      />
                    </div>
                  ) : null}
                </div>
              );
            }) : (
              <div className="reviewEmpty">Ölçek tespit edilmedi — analiz yine de tamamlandı.</div>
            )}
          </div>

          <div className="reviewSection">
            <div className="reviewSectionTitle">Tablo Başlıkları</div>
            <div className="reviewTitleList">
              {results.length ? results.map((r, i) => {
                const num = r.table_number ?? (i + 1);
                const caption = getTableCaption(r, i, customTitles);
                const edited = Boolean(customTitles[String(i)]);
                if (editingTitle === i) {
                  return (
                    <div key={i} className={`reviewTitleRow${edited ? ' edited' : ''}`}>
                      <span className="reviewTableBadge">Tablo {num}</span>
                      <input
                        className="formInput"
                        value={editValue}
                        autoFocus
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            setCustomTitle(i, editValue.trim() || null);
                            setEditingTitle(null);
                          }
                          if (e.key === 'Escape') setEditingTitle(null);
                        }}
                        onBlur={() => {
                          setCustomTitle(i, editValue.trim() || null);
                          setEditingTitle(null);
                        }}
                      />
                    </div>
                  );
                }
                return (
                  <div key={i} className={`reviewTitleRow${edited ? ' edited' : ''}`}>
                    <span className="reviewTableBadge">Tablo {num}</span>
                    <span className="reviewTitleText">{caption}</span>
                    <button
                      type="button"
                      className="reviewEditBtn"
                      title="Düzenle"
                      onClick={() => {
                        setEditingTitle(i);
                        setEditValue(caption);
                      }}
                    >
                      ✎
                    </button>
                  </div>
                );
              }) : (
                <div className="reviewEmpty">Henüz tablo sonucu yok.</div>
              )}
            </div>
          </div>
        </div>
      )}

      <WizardNav onBack={onBack} showNext={false} backLabel="← Sonuçlara Dön" />
    </div>
  );
}
