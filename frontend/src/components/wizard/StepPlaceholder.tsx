import type { ReactNode } from 'react';

interface StepPlaceholderProps {
  icon: string;
  title: string;
  subtitle: string;
  children?: ReactNode;
}

export function StepPlaceholder({ icon, title, subtitle, children }: StepPlaceholderProps) {
  return (
    <>
      <div className="wizardTitle" aria-level={2}>
        {icon} {title}
      </div>
      <p className="wizardSubtitle">{subtitle}</p>
      <div className="placeholderBody">
        {children ?? 'Bu adımın React bileşenleri bir sonraki migration aşamasında eklenecek.'}
      </div>
    </>
  );
}

interface WizardNavProps {
  onBack?: () => void;
  onNext?: () => void;
  backLabel?: string;
  nextLabel?: string;
  showBack?: boolean;
  showNext?: boolean;
  hint?: string;
  extra?: ReactNode;
}

export function WizardNav({
  onBack,
  onNext,
  backLabel = '← Geri',
  nextLabel = 'Devam →',
  showBack = true,
  showNext = true,
  hint,
  extra,
}: WizardNavProps) {
  return (
    <div className="wizardNav">
      {showBack ? (
        <button type="button" className="btn btnGhost" onClick={onBack}>
          {backLabel}
        </button>
      ) : (
        <span />
      )}
      {hint ? <span className="stepMeta">{hint}</span> : <span />}
      {showNext ? (
        <button type="button" className="btn btnPrimary" onClick={onNext}>
          {nextLabel}
        </button>
      ) : (
        extra ?? <span />
      )}
    </div>
  );
}
