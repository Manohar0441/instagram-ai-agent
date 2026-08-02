import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * A last-resort safety net for render crashes that would otherwise leave a
 * blank or half-drawn screen with no way forward except an unprompted
 * manual reload. React error boundaries only catch errors thrown during
 * render, not in event handlers or async code - see useChunkErrorReload
 * for the other common cause of a "stuck" screen (a stale lazy-loaded
 * route chunk after a new deploy).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="swiss-layout">
          <aside className="swiss-sidebar">
            <div className="swiss-sidebar-top">
              <div className="swiss-brand">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 15L7.5 5H11.5L7 15H3Z" fill="#da291c" />
                  <path d="M11 19L15.5 9H19.5L15 19H11Z" fill="#da291c" />
                  <rect x="6" y="12" width="12" height="2.5" fill="#da291c" />
                </svg>
                Instalysis.
              </div>
            </div>
          </aside>
          <main className="swiss-main">
            <div className="swiss-content">
              <div className="swiss-header-block">
                <span className="eyebrow">Something went wrong</span>
                <h1 className="swiss-title" style={{ fontSize: "3rem" }}>
                  That didn&apos;t load right.
                </h1>
                <p className="swiss-subtitle">
                  A part of the page hit an unexpected error. Reloading
                  usually fixes it.
                </p>
              </div>
              <button
                type="button"
                className="swiss-button"
                onClick={() => window.location.reload()}
              >
                <span>Reload the page</span>
                <svg className="button-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                  <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
              </button>
            </div>
          </main>
        </div>
      );
    }

    return this.props.children;
  }
}
