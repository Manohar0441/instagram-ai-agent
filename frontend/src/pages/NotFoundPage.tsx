import { Link } from "react-router-dom";

import "../components/layout/layout.css";

export function NotFoundPage() {
  return (
    <div className="centered">
      <div className="centered__panel">
        <div className="centered__brand">Instalysis</div>
        <div className="stack">
          <span className="eyebrow">404</span>
          <h1>That page does not exist</h1>
          <p className="muted">
            <Link to="/dashboard">Return to the dashboard</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
