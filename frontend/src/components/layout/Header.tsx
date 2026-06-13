export function Header() {
  return (
    <header className="appHeader" role="banner">
      <div className="appHeaderInner">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div className="logo">
            Stat<span className="logoAccent">AI</span>
          </div>
          <div style={{ width: 1, height: 16, background: 'var(--border)' }} aria-hidden />
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>Akademik istatistik</span>
        </div>
        <span className="badge" aria-label="Beta sürüm">Beta</span>
      </div>
    </header>
  );
}
