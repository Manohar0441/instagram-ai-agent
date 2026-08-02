import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="swiss-layout">
      {/* LEFT COLUMN: Structural Sidebar */}
      <aside className="swiss-sidebar">
        <div className="swiss-sidebar-top">
          <div className="swiss-brand">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 15L7.5 5H11.5L7 15H3Z" fill="#da291c"/>
              <path d="M11 19L15.5 9H19.5L15 19H11Z" fill="#da291c"/>
              <rect x="6" y="12" width="12" height="2.5" fill="#da291c"/>
            </svg>
            Instalysis.
          </div>
        </div>

        <div className="swiss-crosshair-container">
          <div className="crosshair-line-h"></div>
          <div className="crosshair-line-v"></div>
          <div className="crosshair-node"></div>
        </div>

        <div className="swiss-sidebar-bottom">
          <p className="sidebar-quote">
            <strong>Every page has a purpose.</strong>
            <br />
            This one cannot be found.
          </p>
        </div>
      </aside>

      {/* RIGHT COLUMN: Main Content */}
      <main className="swiss-main">
        <div className="swiss-content">
          <div className="swiss-header-block">
            <span className="eyebrow">Error 404</span>
            <h1 className="swiss-title">
              Lost,
              <br />
              not gone.
            </h1>
            <p className="swiss-subtitle">
              The page you&apos;re looking for doesn&apos;t exist, has been
              moved, or is no longer available.
            </p>
          </div>

          <Link to="/dashboard" className="swiss-button">
            <span>Return to dashboard</span>
            <svg className="button-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </Link>
        </div>
      </main>
    </div>
  );
}
