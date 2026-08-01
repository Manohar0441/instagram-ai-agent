import { Link } from "react-router-dom";

import "../styles/swiss.css";

export function NotFoundPage() {
  return (
    <div className="login-page">
      <div className="login-layout">

        {/* LEFT PANEL */}

        <aside className="login-sidebar">

          <div className="sidebar-grid" />

          <header className="brand-block">

            <div className="brand-logo">

              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
              >
                <path d="M3 15L7.5 5H11.5L7 15H3Z" fill="#DA291C"/>
                <path d="M11 19L15.5 9H19.5L15 19H11Z" fill="#DA291C"/>
                <rect x="6" y="12" width="12" height="2.5" fill="#DA291C"/>
              </svg>

            </div>

            <div className="brand-copy">
              <h2>Instalysis.</h2>
              <p>
                AI Powered
                <br />
                Instagram Analytics
              </p>
            </div>

          </header>

          <div className="sidebar-divider" />

          <section className="sidebar-message">
            <h3>Every page has a purpose.</h3>

            <p>
              Unfortunately this one cannot be found.
            </p>
          </section>

          <footer className="sidebar-footer">
            <span>v1.0</span>
            <span>© 2026 Instalysis</span>
          </footer>

        </aside>

        {/* RIGHT PANEL */}

        <main className="login-main">

          <div className="login-content">

            <span className="eyebrow">
              ERROR 404
            </span>

            <h1 className="login-title">
              Lost,
              <br />
              not gone.
            </h1>

            <p className="login-subtitle">
              The page you're looking for doesn't exist,
              has been moved, or is no longer available.
            </p>

            <div style={{ marginTop: "48px" }}>

              <Link
                to="/dashboard"
                className="login-button"
              >
                <span>Return to Dashboard</span>

                <span className="button-icon">
                  →
                </span>

              </Link>

            </div>

          </div>

        </main>

      </div>
    </div>
  );
}