import { useState } from 'react';
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
  const relevance = item.relevance_flag ?? 'uygun';

  return (
    <div
      className={[
        'planCard',
        item.cekirdek ? 'planCardCore' : '',
        disabled ? 'disabled' : '',
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
          {(item.test || '') + (item.vars?.length ? ` · ${item.vars.join(' × ')}` : '')}
        </div>
        {item.reason ? (
          <div className="planDetail textMuted">{item.reason}</div>
        ) : null}
      </div>
      {item.hypothesis_id ? (
        <span className="planBadgeHyp">{item.hypothesis_id}</span>
      ) : null}
      {item.cekirdek ? (
        <span className="planBadgeKesin">Çekirdek</span>
      ) : item.butce_disi ? (
        <span className="planBadgeBudget">Bütçe dışı</span>
      ) : relevance === 'uygun' ? (
        <span className="planBadgeRec">Uygun</span>
      ) : relevance === 'olası' ? (
        <span className="planBadgeNot">Olası</span>
      ) : null}
    </div>
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
  const [accordionOpen, setAccordionOpen] = useState(false);

  const indexed = catalog.map((t, i) => ({ ...t, catalogIndex: i }));
  const core = indexed.filter((t) => t.cekirdek);
  const primary = indexed.filter(
    (t) => !t.cekirdek && t.display_section !== 'accordion',
  );
  const accordion = indexed.filter(
    (t) => !t.cekirdek && t.display_section === 'accordion',
  );
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

      {primary.length ? (
        <>
          <div className="planSectionHeader">
            <div className="planSectionLabel">Önerilen analizler ({primary.length})</div>
            <div className="planSectionActions">
              <button type="button" onClick={() => onToggleTier('onerilen', true)}>Tümünü seç</button>
              <button type="button" onClick={() => onToggleTier('onerilen', false)}>Temizle</button>
            </div>
          </div>
          <p className="textXs textMuted mb1">
            Uygun analizler varsayılan seçili; olası analizleri işaretleyerek ekleyebilirsiniz.
          </p>
          {primary.map((t) => (
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

      {accordion.length ? (
        <details
          className="planAccordion mt2"
          open={accordionOpen}
          onToggle={(e) => setAccordionOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="planSectionLabel" style={{ cursor: 'pointer' }}>
            Diğer analizler ({accordion.length})
          </summary>
          <p className="textXs textMuted mb1">
            Düşük öncelikli veya etik belgeyle zayıf eşleşen adaylar.
          </p>
          {accordion.map((t) => (
            <PlanCard
              key={t.catalogIndex}
              item={t}
              index={t.catalogIndex}
              activeFilter={activeFilter}
              onToggle={onToggleItem}
            />
          ))}
        </details>
      ) : null}

      <div className="planNote">
        📈 <strong>Regresyon:</strong> Sonuçlar adımında yordayıcı ve sonuç seçerek çoklu doğrusal regresyon çalıştırabilirsiniz.
      </div>
    </>
  );
}
