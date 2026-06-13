import {
  countHypothesisTables,
  estimatePlanTableCount,
  planTotalBarText,
  PLAN_PROFILES,
} from '../../lib/planCatalog';
import { useAppStore } from '../../stores/useAppStore';
import type { PlanCatalogItem } from '../../types';

interface PlanCatalogProps {
  onToggleItem: (index: number, enabled: boolean) => void;
  onToggleTier: (tier: string, enabled: boolean) => void;
  onSetProfile: (profile: typeof PLAN_PROFILES[number]['id']) => void;
  onFilterHypothesis: (id: string | null) => void;
}

function PlanCard({
  item,
  index,
  activeFilter,
  onToggle,
}: {
  item: PlanCatalogItem & { catalogIndex: number };
  index: number;
  activeFilter: string | null;
  onToggle: (index: number, enabled: boolean) => void;
}) {
  const locked = item.cekirdek;
  const disabled = !locked && item.enabled === false;
  const highlight = activeFilter && item.hypothesis_id === activeFilter;

  return (
    <div
      className={[
        'planCard',
        item.cekirdek ? 'planCardCore' : '',
        disabled ? 'disabled' : '',
        item.tier === 'onerilmeyen' ? 'planCardExcluded' : '',
        highlight ? 'planCardHypHighlight' : '',
      ].filter(Boolean).join(' ')}
    >
      {locked ? (
        <span className="planLock" title="Çekirdek tablo — kapatılamaz">🔒</span>
      ) : (
        <input
          type="checkbox"
          checked={item.enabled !== false}
          onChange={(e) => onToggle(index, e.target.checked)}
        />
      )}
      <div className="flex1">
        <div className="planLabel">{item.label || item.id}</div>
        <div className="planDetail">
          {(item.test || '') + (item.vars?.length ? ` · ${item.vars.join(', ')}` : '')}
        </div>
        {item.reason ? (
          <div className="planDetail planDetailWarn">{item.reason}</div>
        ) : null}
      </div>
      {item.hypothesis_id ? (
        <span className="planBadgeHyp">{item.hypothesis_id}</span>
      ) : null}
      {item.cekirdek ? (
        <span className="planBadgeKesin">Çekirdek</span>
      ) : item.butce_disi ? (
        <span className="planBadgeBudget">Bütçe dışı</span>
      ) : item.tier === 'kesin_onerilen' ? (
        <span className="planBadgeKesin">⭐ Kesin</span>
      ) : item.tier === 'onerilen' ? (
        <span className="planBadgeRec">✅ Önerilen</span>
      ) : (
        <span className="planBadgeNot">○ Düşük öncelik</span>
      )}
    </div>
  );
}

function CatalogSection({
  title,
  hint,
  tier,
  catalog,
  activeFilter,
  onToggle,
  onToggleTier,
}: {
  title: string;
  hint?: string;
  tier: string;
  catalog: (PlanCatalogItem & { catalogIndex: number })[];
  activeFilter: string | null;
  onToggle: (index: number, enabled: boolean) => void;
  onToggleTier: (tier: string, enabled: boolean) => void;
}) {
  const items = catalog.filter((t) => t.tier === tier && !t.cekirdek);
  if (!items.length) return null;
  return (
    <>
      <div className="planSectionHeader">
        <div className="planSectionLabel">{title} ({items.length})</div>
        <div className="planSectionActions">
          <button type="button" onClick={() => onToggleTier(tier, true)}>Tümünü seç</button>
          <button type="button" onClick={() => onToggleTier(tier, false)}>Temizle</button>
        </div>
      </div>
      {hint ? <p className="textXs textMuted mb1">{hint}</p> : null}
      {items.map((t) => (
        <PlanCard
          key={t.catalogIndex}
          item={t}
          index={t.catalogIndex}
          activeFilter={activeFilter}
          onToggle={onToggle}
        />
      ))}
    </>
  );
}

export function PlanCatalogView({
  onToggleItem,
  onToggleTier,
  onSetProfile,
  onFilterHypothesis,
}: PlanCatalogProps) {
  const catalog = useAppStore((s) => s.plan.catalog);
  const meta = useAppStore((s) => s.plan.meta);
  const profile = useAppStore((s) => s.plan.profile);
  const activeFilter = useAppStore((s) => s.hypotheses.activeFilter);
  const approved = useAppStore((s) => s.hypotheses.approved);

  const indexed = catalog.map((t, i) => ({ ...t, catalogIndex: i }));
  const core = indexed.filter((t) => t.cekirdek);
  const tableCount = estimatePlanTableCount(catalog);

  return (
    <>
      <div className="planToolbar">
        <div className="planProfileSegments">
          {PLAN_PROFILES.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`planProfileBtn${profile === p.id ? ' active' : ''}`}
              onClick={() => onSetProfile(p.id)}
            >
              <span>{p.label}</span>
              <span className="planProfileApprox">≈{p.approx} tablo</span>
            </button>
          ))}
        </div>
        <div className="planTableCounterCard">
          Bu plan <strong>{tableCount}</strong> tablo üretecek
        </div>
      </div>

      {approved.length ? (
        <div className="hypothesisToolbar">
          <div className="textSm textMuted mb1">
            Araştırma soruları — karta tıklayınca ilgili testler vurgulanır
          </div>
          <div className="hypothesisCards">
            {approved.map((h) => (
              <button
                key={h.id}
                type="button"
                className={`hypothesisCard${activeFilter === h.id ? ' active' : ''}`}
                onClick={() => onFilterHypothesis(activeFilter === h.id ? null : h.id)}
              >
                <div className="hypothesisCardId">{h.id}</div>
                <div className="hypothesisCardLabel">{h.label}</div>
                <div className="hypothesisCardCount">
                  {countHypothesisTables(catalog, h.id)} tablo
                </div>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="alert alertInfo textSm planTotalBar">
        {planTotalBarText(catalog, meta)}
      </div>

      {core.length ? (
        <>
          <div className="planSectionLabel">Çekirdek tablolar ({core.length})</div>
          <p className="textXs textMuted mb1">Her planda zorunlu; tablo bütçesine dahildir.</p>
          {core.map((t) => (
            <PlanCard
              key={t.catalogIndex}
              item={t}
              index={t.catalogIndex}
              activeFilter={activeFilter}
              onToggle={onToggleItem}
            />
          ))}
        </>
      ) : null}

      <CatalogSection
        title="Kesin önerilen"
        hint="Varsayılan seçili — tez için temel paket"
        tier="kesin_onerilen"
        catalog={indexed}
        activeFilter={activeFilter}
        onToggle={onToggleItem}
        onToggleTier={onToggleTier}
      />
      <CatalogSection
        title="Önerilen"
        hint="Araştırma amacına uygun ek testler"
        tier="onerilen"
        catalog={indexed}
        activeFilter={activeFilter}
        onToggle={onToggleItem}
        onToggleTier={onToggleTier}
      />
      <CatalogSection
        title="Önerilmeyen"
        hint="İsterseniz işaretleyip analize dahil edin"
        tier="onerilmeyen"
        catalog={indexed}
        activeFilter={activeFilter}
        onToggle={onToggleItem}
        onToggleTier={onToggleTier}
      />

      <div className="planNote">
        📈 <strong>Regresyon:</strong> Sonuçlar adımında yordayıcı ve sonuç seçerek çoklu doğrusal regresyon çalıştırabilirsiniz.
      </div>
    </>
  );
}
