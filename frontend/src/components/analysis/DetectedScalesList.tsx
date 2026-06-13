import type { DetectedScale, RegistryMatch, ScaleCutoff } from '../../types';

interface DetectedScalesListProps {
  detected: DetectedScale[];
  registryMatched: RegistryMatch[];
  cutoffs: Record<string, ScaleCutoff>;
}

function registryBadge(scale: DetectedScale, registryMatched: RegistryMatch[]): string | null {
  const id = (scale.registry_id ?? scale.id ?? '').toLowerCase();
  const fromReg = registryMatched.some(
    (m) => (m.id ?? '').toLowerCase() === id || (m.name ?? '').toLowerCase() === (scale.name ?? '').toLowerCase(),
  );
  if (fromReg || scale.source === 'registry' || scale.source === 'registry+gemini') {
    return 'Veritabanında doğrulandı';
  }
  if (scale.source === 'gemini') return 'AI tarafından tespit edildi';
  return null;
}

export function DetectedScalesList({ detected, registryMatched, cutoffs }: DetectedScalesListProps) {
  if (!detected.length) return null;

  return (
    <div className="detectedScalesList" role="list" aria-label="Tespit edilen ölçekler">
      {detected.map((scale) => {
        const badge = registryBadge(scale, registryMatched);
        const sid = scale.registry_id ?? scale.id ?? '';
        const cutoff = sid ? cutoffs[sid] : undefined;
        return (
          <div key={`${scale.name}-${sid}`} className="detectedScaleCard" role="listitem">
            <div className="detectedScaleHead">
              <strong>{scale.name ?? sid}</strong>
              {badge ? <span className="scaleSrcBadge registry">{badge}</span> : null}
            </div>
            {cutoff?.value != null ? (
              <div className="scaleCutoffLine">
                Kesim noktası: ≥{cutoff.value}
                {cutoff.interpretation ? ` → ${cutoff.interpretation}` : ''}
              </div>
            ) : null}
            {scale.turkish_valid === false ? (
              <span className="scaleSrcBadge warn">Türkçe geçerlilik çalışması bulunamadı</span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
