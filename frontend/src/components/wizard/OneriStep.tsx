import { useEffect, useRef, useState } from 'react';
import { useWizard } from '../../hooks/useWizard';
import { fetchAnalizOneri } from '../../lib/analizOneriApi';
import { detectScalesInline, scaleMatchingInline } from '../../lib/scaleApi';
import { useAppStore } from '../../stores/useAppStore';
import type { AnalizOneriResult } from '../../types';
import { ErrorBanner } from '../shared/ErrorBanner';
import { LoadingButton } from '../shared/LoadingButton';
import { WizardNav } from './StepPlaceholder';

interface OneriStepProps {
  onBack: () => void;
}

type ProposedAnalysis = {
  id: string;
  question: string;
  description: string;
};

type LegacyProposed = {
  id?: string;
  text?: string;
  question?: string;
  description?: string;
  subtitle?: string;
  neden?: string;
  analiz?: string;
};

type OneriDataWithProposed = AnalizOneriResult & {
  proposed_analyses?: LegacyProposed[];
};

const USER_ADDED_DESC = 'Kullanıcı tarafından eklendi';
const DEFAULT_DESC = 'Veri yapısına göre önerilen analiz';

function normalizeProposedItem(item: LegacyProposed, index: number): ProposedAnalysis {
  const question = (
    item.question
    || item.text
    || item.analiz
    || ''
  ).trim();
  const description = (
    item.description
    || item.subtitle
    || item.neden
    || DEFAULT_DESC
  ).trim();
  return {
    id: item.id || `proposed-${index}`,
    question,
    description,
  };
}

function gerekceToProposed(
  g: { analiz?: string; neden?: string },
  index: number,
): ProposedAnalysis {
  const question = (g.analiz || g.neden || '').trim();
  const description = (g.neden || DEFAULT_DESC).trim();
  return { id: `proposed-${index}`, question, description };
}

function readProposedAnalyses(oneri: AnalizOneriResult | null): ProposedAnalysis[] {
  if (!oneri) return [];
  const ext = oneri as OneriDataWithProposed;
  if (ext.proposed_analyses?.length) {
    return ext.proposed_analyses.map(normalizeProposedItem);
  }
  return (oneri.gerekceler ?? []).map(gerekceToProposed);
}

function saveProposedAnalyses(list: ProposedAnalysis[]) {
  useAppStore.setState((s) => ({
    oneri: {
      ...s.oneri,
      data: s.oneri.data
        ? { ...(s.oneri.data as OneriDataWithProposed), proposed_analyses: list }
        : s.oneri.data,
    },
  }));
}

export function OneriStep({ onBack }: OneriStepProps) {
  const { nextStep } = useWizard();
  const [proceeding, setProceeding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftQuestion, setDraftQuestion] = useState('');
  const [addingNew, setAddingNew] = useState(false);
  const [newQuestion, setNewQuestion] = useState('');
  const loading = useAppStore((s) => s.oneri.loading);
  const error = useAppStore((s) => s.oneri.error);
  const oneri = useAppStore((s) => s.oneri.data);
  const fetched = useAppStore((s) => s.oneri.fetched);
  const setOneriLoading = useAppStore((s) => s.setOneriLoading);
  const setOneriError = useAppStore((s) => s.setOneriError);
  const applyAnalizOneriResponse = useAppStore((s) => s.applyAnalizOneriResponse);
  const applyAnalizOneriEffects = useAppStore((s) => s.applyAnalizOneriEffects);
  const started = useRef(false);
  const initializedProposed = useRef(false);

  const proposedAnalyses = readProposedAnalyses(oneri);

  useEffect(() => {
    if (fetched || started.current) return;
    started.current = true;
    setOneriLoading(true);
    void fetchAnalizOneri()
      .then((response) => applyAnalizOneriResponse(response))
      .catch((err: Error) => setOneriError(err.message || 'Analiz önerisi alınamadı'));
  }, [
    fetched,
    setOneriLoading,
    setOneriError,
    applyAnalizOneriResponse,
  ]);

  useEffect(() => {
    if (!oneri || initializedProposed.current) return;
    const ext = oneri as OneriDataWithProposed;
    if (ext.proposed_analyses?.length) {
      initializedProposed.current = true;
      return;
    }
    const initial = (oneri.gerekceler ?? []).map(gerekceToProposed);
    if (!initial.length) return;
    initializedProposed.current = true;
    saveProposedAnalyses(initial);
  }, [oneri]);

  const handleNext = async () => {
    if (proceeding || loading) return;
    setProceeding(true);
    try {
      applyAnalizOneriEffects();
      await detectScalesInline();
      await scaleMatchingInline();
      await nextStep();
    } finally {
      setProceeding(false);
    }
  };

  const startEdit = (item: ProposedAnalysis) => {
    setEditingId(item.id);
    setDraftQuestion(item.question);
    setAddingNew(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraftQuestion('');
  };

  const saveEdit = () => {
    if (!editingId) return;
    const next = proposedAnalyses.map((item) => (
      item.id === editingId
        ? { ...item, question: draftQuestion.trim() }
        : item
    ));
    saveProposedAnalyses(next);
    cancelEdit();
  };

  const deleteItem = (id: string) => {
    saveProposedAnalyses(proposedAnalyses.filter((item) => item.id !== id));
    if (editingId === id) cancelEdit();
  };

  const addItem = () => {
    const question = newQuestion.trim();
    if (!question) return;
    saveProposedAnalyses([
      ...proposedAnalyses,
      {
        id: `proposed-${Date.now()}`,
        question,
        description: USER_ADDED_DESC,
      },
    ]);
    setNewQuestion('');
    setAddingNew(false);
  };

  const nextButton = (
    <LoadingButton
      variant="primary"
      loading={proceeding}
      loadingText="Hazırlanıyor..."
      disabled={loading && !oneri}
      onClick={() => void handleNext()}
    >
      Değişkenlere Git →
    </LoadingButton>
  );

  if (loading && !oneri) {
    return (
      <>
        <h2 className="wizardTitle">Analiz Planı Önerisi</h2>
        <p className="wizardSubtitle">Anket ve etik kurul belgeleriniz inceleniyor…</p>
        <div className="planLoadingState">
          <span className="spinner" style={{ width: 24, height: 24, borderWidth: 2 }} aria-hidden />
          <p className="planLoadingText">Önerilen analiz planı hazırlanıyor…</p>
        </div>
        <WizardNav onBack={onBack} showNext={false} extra={<span />} />
      </>
    );
  }

  return (
    <>
      <h2 className="wizardTitle">Analiz Planı Önerisi</h2>
      <p className="wizardSubtitle">
        Anket ve etik kurul belgelerinize göre önerilen analizler
      </p>

      {error ? <ErrorBanner message={error} /> : null}

      <div className="oneriCard">
        {oneri?.ozet ? (
          <p className="oneriOzet">{oneri.ozet}</p>
        ) : null}

        {proposedAnalyses.length > 0 ? (
          <>
            <h4 className="oneriSectionTitle">Araştırma soruları</h4>
            {proposedAnalyses.map((item) => (
              <div key={item.id} className="oneriItem" style={{ position: 'relative' }}>
                <div
                  style={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    display: 'flex',
                    gap: 6,
                  }}
                >
                  {editingId !== item.id ? (
                    <button
                      type="button"
                      className="btn btnGhost"
                      style={{ height: 28, padding: '0 8px', fontSize: 12 }}
                      onClick={() => startEdit(item)}
                      aria-label="Düzenle"
                    >
                      ✏️ Düzenle
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn btnGhost"
                    style={{
                      height: 28,
                      padding: '0 8px',
                      fontSize: 12,
                      color: 'var(--danger)',
                    }}
                    onClick={() => deleteItem(item.id)}
                    aria-label="Sil"
                  >
                    🗑️ Sil
                  </button>
                </div>

                {editingId === item.id ? (
                  <div style={{ marginTop: 28 }}>
                    <input
                      type="text"
                      className="formInput"
                      value={draftQuestion}
                      onChange={(e) => setDraftQuestion(e.target.value)}
                      style={{ width: '100%', marginBottom: 8 }}
                    />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button type="button" className="btn btnPrimary" onClick={saveEdit}>
                        Kaydet
                      </button>
                      <button type="button" className="btn btnGhost" onClick={cancelEdit}>
                        İptal
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="oneriNeden" style={{ marginTop: 24, color: 'var(--text)' }}>
                      {item.question}
                    </p>
                    {item.description ? (
                      <p className="oneriNeden">{item.description}</p>
                    ) : null}
                  </>
                )}
              </div>
            ))}

            {addingNew ? (
              <div className="oneriItem">
                <input
                  type="text"
                  className="formInput"
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  placeholder="Araştırma sorunuzu yazın..."
                  style={{ width: '100%', marginBottom: 8 }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') addItem();
                  }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" className="btn btnPrimary" onClick={addItem}>
                    Ekle
                  </button>
                  <button
                    type="button"
                    className="btn btnGhost"
                    onClick={() => {
                      setAddingNew(false);
                      setNewQuestion('');
                    }}
                  >
                    İptal
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="btn btnGhost"
                style={{ marginTop: 8 }}
                onClick={() => {
                  setAddingNew(true);
                  setEditingId(null);
                }}
              >
                + Araştırma Sorusu Ekle
              </button>
            )}
          </>
        ) : null}

        {(oneri?.olcekler?.length ?? 0) > 0 ? (
          <div className="oneriOlcekler">
            <span className="label">Tespit edilen ölçekler:</span>
            {oneri!.olcekler!.map((o) => (
              <span key={o.ad} className="olcekBadge">{o.ad}</span>
            ))}
          </div>
        ) : null}
      </div>

      <WizardNav
        onBack={onBack}
        showNext={false}
        extra={nextButton}
      />
    </>
  );
}
