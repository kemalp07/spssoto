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
  onSkip?: () => void;
  backLabel?: string;
  nextLabel?: string;
  skipLabel?: string;
  showBack?: boolean;
  showNext?: boolean;
  showSkip?: boolean;
  hint?: string;
  extra?: ReactNode;
}

export function WizardNav({
  onBack,
  onNext,
  onSkip,
  backLabel = '‹ Geri',
  nextLabel = 'Devam →',
  skipLabel = 'Atla →',
  showBack = true,
  showNext = true,
  showSkip = false,
  hint,
  extra,
}: WizardNavProps) {
  return (
    <div className="wizardNav">
      {showBack ? (
        <button type="button" className="wizardNavBack" onClick={onBack}>
          {backLabel}
        </button>
      ) : (
        <span />
      )}
      {showSkip && onSkip ? (
        <button type="button" className="wizardNavSkip" onClick={onSkip}>
          {skipLabel}
        </button>
      ) : hint ? (
        <span className="stepMeta">{hint}</span>
      ) : (
        <span />
      )}
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
