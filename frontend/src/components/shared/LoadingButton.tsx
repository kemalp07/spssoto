import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface LoadingButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  loadingText?: string;
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
}

const variantClass = {
  primary: 'btnPrimary',
  secondary: 'btnSecondary',
  ghost: 'btnGhost',
} as const;

export function LoadingButton({
  loading = false,
  loadingText = 'Yükleniyor...',
  children,
  variant = 'primary',
  disabled,
  className = '',
  ...rest
}: LoadingButtonProps) {
  return (
    <button
      type="button"
      className={`btn ${variantClass[variant]}${loading ? ' is-loading' : ''} ${className}`.trim()}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <>
          <span className="spinner" aria-hidden />
          {loadingText}
        </>
      ) : (
        children
      )}
    </button>
  );
}
