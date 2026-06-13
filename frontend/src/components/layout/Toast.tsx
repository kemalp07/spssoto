import { useAppStore } from '../../stores/useAppStore';

export function ToastStack() {
  const toasts = useAppStore((s) => s.toasts);
  const dismissToast = useAppStore((s) => s.dismissToast);

  if (!toasts.length) return null;

  return (
    <div className="toastStack" role="region" aria-label="Bildirimler" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast${toast.type.charAt(0).toUpperCase()}${toast.type.slice(1)}`}
          role="alert"
        >
          <span>{toast.text}</span>
          <button
            type="button"
            className="toastClose"
            aria-label="Kapat"
            onClick={() => dismissToast(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
