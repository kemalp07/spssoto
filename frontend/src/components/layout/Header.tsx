export function Header() {
  return (
    <header className="appHeader" role="banner">
      <div className="headerLeft">
        <div className="logo">
          Stat<span className="logoAccent">AI</span>
        </div>
        <div className="headerDivider" aria-hidden />
        <span className="headerSubtitle">Akademik istatistik</span>
      </div>
      <span className="badge" aria-label="Beta sürüm">Beta</span>
    </header>
  );
}
