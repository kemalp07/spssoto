import { useAppStore } from '../../stores/useAppStore';

export function MissingCodesEditor() {
  const detected = useAppStore((s) => s.wizard.detectedMissingCodes);
  const editOpen = useAppStore((s) => s.wizard.missingCodesEditOpen);
  const manualText = useAppStore((s) => s.wizard.manualMissingCodesText);
  const setEditOpen = useAppStore((s) => s.setMissingCodesEditOpen);
  const setManualText = useAppStore((s) => s.setManualMissingCodesText);

  if (!detected.codes.length && !manualText) return null;

  if (editOpen) {
    return (
      <div className="infoBar infoBarMissing">
        <label className="formLabel" htmlFor="missingCodesEditInput">
          Eksik veri kodları:
        </label>
        <input
          id="missingCodesEditInput"
          type="text"
          className="formInput formInputInline"
          value={manualText}
          placeholder="99, 998, 999"
          onChange={(e) => setManualText(e.target.value)}
        />
        <button type="button" className="btn btnGhost btnSm" onClick={() => setEditOpen(false)}>
          Tamam
        </button>
      </div>
    );
  }

  const parts = detected.codes.map((code) => {
    const n = (detected.columnMap[code] ?? []).length;
    return n ? `${code} değeri ${n} sütunda` : `${code} değeri`;
  });

  return (
    <div className="infoBar infoBarMissing">
      <span>{parts.join('; ')} kayıp veri olarak işaretlendi</span>
      <button type="button" className="btn btnGhost btnSm" onClick={() => setEditOpen(true)}>
        Düzenle
      </button>
    </div>
  );
}
