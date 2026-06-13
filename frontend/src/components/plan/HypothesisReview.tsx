import { buildHypothesisSummaryLine } from '../../lib/planCatalog';
import {
  approveHypothesesAndLoadPlan,
  skipHypothesisReviewAndLoadPlan,
} from '../../hooks/usePlan';
import { useAppStore } from '../../stores/useAppStore';
import { LoadingButton } from '../shared/LoadingButton';

export function HypothesisReview() {
  const approved = useAppStore((s) => s.hypotheses.approved);
  const candidates = useAppStore((s) => s.hypotheses.candidates);
  const unmatchedDisplay = useAppStore((s) => s.hypotheses.unmatchedDisplay);
  const editMode = useAppStore((s) => s.hypotheses.editMode);
  const parseMeta = useAppStore((s) => s.hypotheses.parseMeta);
  const setEditMode = useAppStore((s) => s.setHypothesisEditMode);
  const updateCandidates = useAppStore((s) => s.updateHypothesisCandidates);

  const decider = parseMeta.claude_used
    ? 'Claude karar verici'
    : (parseMeta.gemini_used ? 'Gemini (Claude yok)' : 'Kural tabanlı');

  if (editMode) {
    return (
      <div className="hypothesisReview">
        <h3 className="wizardTitle" style={{ fontSize: '1.1rem' }}>🔬 Hipotez eşlemesini düzenle</h3>
        <p className="textSm textMuted mb2">Her soru için test adaylarını seçin.</p>
        {unmatchedDisplay.length ? (
          <div className="alert alertWarn textSm mb2">
            Şu sorular veriyle eşleştirilemedi: {unmatchedDisplay.join('; ')}
          </div>
        ) : null}
        {approved.map((h, idx) => (
          <div key={h.id} className="hypothesisReviewRow">
            <div className="flex1">
              <strong>{h.id}</strong> — {h.label}
            </div>
            <select
              className="formInput hypothesisSelect"
              multiple
              size={3}
              value={h.candidate_ids ?? []}
              onChange={(e) => {
                const ids = [...e.target.selectedOptions].map((o) => o.value);
                updateCandidates(idx, ids);
              }}
            >
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>{c.label || c.id}</option>
              ))}
            </select>
          </div>
        ))}
        <div className="wizardNav" style={{ marginTop: 16 }}>
          <button type="button" className="btn btnGhost" onClick={() => setEditMode(false)}>
            ← Özet
          </button>
          <LoadingButton variant="primary" onClick={() => approveHypothesesAndLoadPlan()}>
            Onayla ve Devam Et
          </LoadingButton>
        </div>
      </div>
    );
  }

  const lines = approved.map((h) => buildHypothesisSummaryLine(h, candidates));

  return (
    <div className="hypothesisReview">
      <h3 className="wizardTitle" style={{ fontSize: '1.1rem' }}>🔬 Araştırma sorusu eşlemesi</h3>
      <p className="textSm textMuted mb2">
        Çekirdek tablolar (demografi, tanımlayıcı, güvenirlik) otomatik eklenir.
      </p>
      <div className="hypothesisSummaryCard">
        <div className="wizardTitle" style={{ fontSize: '1.05rem', marginBottom: 6 }}>
          Sistem şunu anladı:
        </div>
        <div className="textXs textMuted mb1">{decider}</div>
        <div className="hypothesisSummaryLines">
          {lines.length ? lines.map((line, i) => <div key={i}>{line}</div>) : (
            <p className="textSm textMuted">Otomatik hipotez eşlemesi bulunamadı; hipotezsiz devam edebilirsiniz.</p>
          )}
        </div>
        <div className="hypothesisSummaryActions">
          <LoadingButton variant="primary" onClick={() => approveHypothesesAndLoadPlan()}>
            Onayla ve Devam Et
          </LoadingButton>
          <button type="button" className="btn btnSecondary" onClick={() => setEditMode(true)}>
            Düzenle
          </button>
          <button type="button" className="btn btnGhost" onClick={() => skipHypothesisReviewAndLoadPlan()}>
            Hipotezsiz devam
          </button>
        </div>
      </div>
    </div>
  );
}
