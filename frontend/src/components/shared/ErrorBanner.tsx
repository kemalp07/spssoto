interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div className="alert alertDanger" role="alert">
      <div>
        <strong>Hata:</strong> {message}
      </div>
      {onRetry ? (
        <button type="button" className="btn btnGhost btnSm" onClick={onRetry}>
          Tekrar dene
        </button>
      ) : null}
    </div>
  );
}
