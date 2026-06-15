import { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import type { DetectedScale, RegistryMatch, ScaleCutoff } from '../../types';

interface DetectedScalesListProps {
  detected: DetectedScale[];
  registryMatched: RegistryMatch[];
  cutoffs: Record<string, ScaleCutoff>;
}

function registryBadge(scale: DetectedScale, registryMatched: RegistryMatch[]): string | null {
  const id = (scale.registry_id ?? scale.id ?? '').toLowerCase();
  const fromReg = registryMatched.some(
    (m) => (m.id ?? '').toLowerCase() === id
      || (m.name ?? '').toLowerCase() === (scale.name ?? '').toLowerCase(),
  );
  if (fromReg || scale.source === 'registry' || scale.source === 'registry+gemini') {
    return 'Veritabanında doğrulandı';
  }
  if (scale.source === 'gemini') return 'AI tarafından tespit edildi';
  return null;
}

function isRegistryVerified(scale: DetectedScale, registryMatched: RegistryMatch[]): boolean {
  const id = (scale.registry_id ?? scale.id ?? '').toLowerCase();
  return registryMatched.some(
    (m) => (m.id ?? '').toLowerCase() === id
      || (m.name ?? '').toLowerCase() === (scale.name ?? '').toLowerCase(),
  ) || scale.source === 'registry' || scale.source === 'registry+gemini';
}

function scaleItems(scale: DetectedScale): string[] {
  const raw = scale.items ?? scale.cronbach_items ?? [];
  return raw.map((item) => String(item)).filter(Boolean);
}

function defaultScaleRange(scale: DetectedScale, registryMatched: RegistryMatch[]): [number, number] {
  if (scale.scale_range && scale.scale_range.length >= 2) {
    return [scale.scale_range[0], scale.scale_range[1]];
  }
  const id = (scale.registry_id ?? scale.id ?? '').toLowerCase();
  const match = registryMatched.find((m) => (m.id ?? '').toLowerCase() === id);
  if (match?.scale_range && match.scale_range.length >= 2) {
    return [match.scale_range[0], match.scale_range[1]];
  }
  return [0, 4];
}

function defaultReverseItems(scale: DetectedScale, registryMatched: RegistryMatch[]): number[] {
  if (scale.reverse_items?.length) return [...scale.reverse_items];
  const id = (scale.registry_id ?? scale.id ?? '').toLowerCase();
  const match = registryMatched.find((m) => (m.id ?? '').toLowerCase() === id);
  return match?.reverse_items ? [...match.reverse_items] : [];
}

interface ScaleEditDraft {
  reverseItems: number[];
  rangeLo: number;
  rangeHi: number;
  newItemInput: string;
}

function ScaleCard({
  scale,
  index,
  registryMatched,
  cutoff,
}: {
  scale: DetectedScale;
  index: number;
  registryMatched: RegistryMatch[];
  cutoff?: ScaleCutoff;
}) {
  const updateDetectedScale = useAppStore((s) => s.updateDetectedScale);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ScaleEditDraft | null>(null);

  const badge = registryBadge(scale, registryMatched);
  const verified = isRegistryVerified(scale, registryMatched);
  const sid = scale.registry_id ?? scale.id ?? '';
  const items = scaleItems(scale);
  const reverseItems = defaultReverseItems(scale, registryMatched);
  const [rangeLo, rangeHi] = defaultScaleRange(scale, registryMatched);

  const openEdit = () => {
    setDraft({
      reverseItems: [...reverseItems],
      rangeLo,
      rangeHi,
      newItemInput: '',
    });
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraft(null);
  };

  const saveEdit = () => {
    if (!draft) return;
    updateDetectedScale(index, {
      reverse_items: [...draft.reverseItems].sort((a, b) => a - b),
      scale_range: [draft.rangeLo, draft.rangeHi],
    });
    setEditing(false);
    setDraft(null);
  };

  const removeReverseItem = (num: number) => {
    if (!draft) return;
    setDraft({
      ...draft,
      reverseItems: draft.reverseItems.filter((n) => n !== num),
    });
  };

  const addReverseItem = () => {
    if (!draft) return;
    const num = parseInt(draft.newItemInput.trim(), 10);
    if (!Number.isFinite(num) || num < 1) return;
    if (draft.reverseItems.includes(num)) {
      setDraft({ ...draft, newItemInput: '' });
      return;
    }
    setDraft({
      ...draft,
      reverseItems: [...draft.reverseItems, num].sort((a, b) => a - b),
      newItemInput: '',
    });
  };

  const itemRows: string[][] = [];
  for (let i = 0; i < items.length; i += 4) {
    itemRows.push(items.slice(i, i + 4));
  }

  return (
    <div className="detectedScaleCard" role="listitem">
      <div className="detectedScaleHead">
        <span className="detectedScaleIcon" aria-hidden>📊</span>
        <strong>{scale.name ?? sid}</strong>
        {verified ? (
          <span className="scaleVerifiedBadge">✓ Güvenilir</span>
        ) : null}
        {badge ? <span className="scaleSrcBadge registry">{badge}</span> : null}
      </div>

      <div className="detectedScaleDivider" />

      <div className="detectedScaleSection">
        <div className="detectedScaleSectionLabel">
          Maddeler (
          {items.length}
          ):
        </div>
        {itemRows.map((row) => (
          <div key={row.join('-')} className="scaleItemChipRow">
            {row.map((col) => (
              <span key={col} className="scaleItemChip">{col}</span>
            ))}
          </div>
        ))}
      </div>

      {reverseItems.length > 0 ? (
        <div className="detectedScaleSection">
          <div className="detectedScaleSectionLabel">Ters puanlanan:</div>
          <div className="scaleItemChipRow">
            {reverseItems.map((num) => (
              <span key={num} className="scaleReverseChip">
                madde
                {' '}
                {num}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="detectedScaleSection detectedScaleRangeLine">
        Skala:
        {' '}
        {rangeLo}
        {' '}
        –
        {' '}
        {rangeHi}
      </div>

      {cutoff?.value != null ? (
        <div className="scaleCutoffLine">
          Kesim noktası: ≥
          {cutoff.value}
          {cutoff.interpretation ? ` → ${cutoff.interpretation}` : ''}
        </div>
      ) : null}

      {scale.turkish_valid === false ? (
        <span className="scaleSrcBadge warn">Türkçe geçerlilik çalışması bulunamadı</span>
      ) : null}

      <div className="detectedScaleActions">
        <button type="button" className="btnGhost btnSm" onClick={openEdit}>
          Düzenle
        </button>
      </div>

      {editing && draft ? (
        <div className="detectedScaleEditPanel">
          <div className="detectedScaleSectionLabel">Ters maddeler:</div>
          <div className="scaleReverseEditRow">
            {draft.reverseItems.map((num) => (
              <span key={num} className="scaleReverseChip scaleReverseChipEditable">
                {num}
                <button
                  type="button"
                  className="scaleReverseRemove"
                  aria-label={`Madde ${num} ters kodlamadan çıkar`}
                  onClick={() => removeReverseItem(num)}
                >
                  ×
                </button>
              </span>
            ))}
            <span className="scaleReverseAddWrap">
              <input
                type="number"
                min={1}
                className="scaleNumInput"
                placeholder="no"
                value={draft.newItemInput}
                onChange={(e) => setDraft({ ...draft, newItemInput: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addReverseItem();
                  }
                }}
              />
              <button type="button" className="btnGhost btnSm" onClick={addReverseItem}>
                ↵
              </button>
            </span>
          </div>

          <div className="detectedScaleSectionLabel scaleRangeEditLabel">
            Skala aralığı:
          </div>
          <div className="scaleRangeEditRow">
            <input
              type="number"
              className="scaleNumInput"
              value={draft.rangeLo}
              onChange={(e) => setDraft({
                ...draft,
                rangeLo: parseInt(e.target.value, 10) || 0,
              })}
            />
            <span>–</span>
            <input
              type="number"
              className="scaleNumInput"
              value={draft.rangeHi}
              onChange={(e) => setDraft({
                ...draft,
                rangeHi: parseInt(e.target.value, 10) || 0,
              })}
            />
          </div>

          <div className="detectedScaleEditActions">
            <button type="button" className="btnPrimary btnSm" onClick={saveEdit}>
              Kaydet
            </button>
            <button type="button" className="btnGhost btnSm" onClick={cancelEdit}>
              İptal
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function DetectedScalesList({ detected, registryMatched, cutoffs }: DetectedScalesListProps) {
  if (!detected.length) return null;

  return (
    <div className="detectedScalesList" role="list" aria-label="Tespit edilen ölçekler">
      {detected.map((scale, index) => {
        const sid = scale.registry_id ?? scale.id ?? '';
        const cutoff = sid ? cutoffs[sid] : undefined;
        return (
          <ScaleCard
            key={`${scale.name}-${sid}-${index}`}
            scale={scale}
            index={index}
            registryMatched={registryMatched}
            cutoff={cutoff}
          />
        );
      })}
    </div>
  );
}
