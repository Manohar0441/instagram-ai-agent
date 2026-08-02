import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../auth/useAuth";
import { Button } from "../ui";

const NAV_GROUPS = [
  {
    label: "Analytics",
    links: [
      { to: "/dashboard", label: "Overview", badge: "OV" },
      { to: "/trends", label: "Trends", badge: "TR" },
      { to: "/media", label: "Posts", badge: "PO" },
      { to: "/top-content", label: "Rankings", badge: "RA" },
    ],
  },
  {
    label: "Intelligence",
    links: [
      { to: "/chat", label: "Ask", badge: "AS" },
      { to: "/insights", label: "Insights", badge: "IN" },
      { to: "/recommendations", label: "Recommendations", badge: "RE" },
      { to: "/reports", label: "Reports", badge: "RP" },
    ],
  },
];

const COLLAPSE_STORAGE_KEY = "instalysis.nav-collapsed";

function readStoredCollapse(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppShell() {
  const { signOut } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(readStoredCollapse);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      // Non-fatal: the preference just won't survive a reload.
    }
  }, [collapsed]);

  // Below 900px the sidebar becomes an off-canvas drawer (see swiss.css).
  // Close it whenever the route changes or on Escape, and lock page scroll
  // while it's open so the content behind it can't be dragged around.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!drawerOpen) return;

    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [drawerOpen]);

  return (
    <div className="shell">
      <div className="nav__mobile-topbar">
        <NavLink to="/dashboard" className="nav__brand">
          <span className="nav__mark" aria-hidden="true">
            I
          </span>
          <span className="nav__brand-label">Instalysis</span>
        </NavLink>
        <button
          type="button"
          className="nav__hamburger"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          aria-expanded={drawerOpen}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="7" x2="21" y2="7"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="17" x2="21" y2="17"></line>
          </svg>
        </button>
      </div>

      {drawerOpen && (
        <div
          className="nav__backdrop"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      <nav
        className={`nav ${collapsed ? "nav--collapsed" : ""} ${drawerOpen ? "nav--drawer-open" : ""}`}
        aria-label="Main"
      >
        <div className="nav__head">
          <NavLink to="/dashboard" className="nav__brand">
            <span className="nav__mark" aria-hidden="true">
              I
            </span>
            <span className="nav__brand-label">Instalysis</span>
          </NavLink>
          <button
            type="button"
            className="nav__collapse-toggle"
            onClick={() => setCollapsed((current) => !current)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={collapsed}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              {collapsed ? (
                <polyline points="9 6 15 12 9 18"></polyline>
              ) : (
                <polyline points="15 6 9 12 15 18"></polyline>
              )}
            </svg>
          </button>
          <button
            type="button"
            className="nav__drawer-close"
            onClick={() => setDrawerOpen(false)}
            aria-label="Close menu"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="6" y1="6" x2="18" y2="18"></line>
              <line x1="6" y1="18" x2="18" y2="6"></line>
            </svg>
          </button>
        </div>

        {NAV_GROUPS.map((group) => (
          <div className="nav__group" key={group.label}>
            <span className="nav__group-label">{group.label}</span>
            {group.links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                title={collapsed ? link.label : undefined}
                className={({ isActive }) =>
                  `nav__link ${isActive ? "nav__link--active" : ""}`
                }
              >
                <span className="nav__link-badge" aria-hidden="true">
                  {link.badge}
                </span>
                <span className="nav__link-label">{link.label}</span>
              </NavLink>
            ))}
          </div>
        ))}

        <div className="nav__footer">
          <NavLink
            to="/settings"
            title={collapsed ? "Settings" : undefined}
            className={({ isActive }) =>
              `nav__link ${isActive ? "nav__link--active" : ""}`
            }
          >
            <span className="nav__link-badge" aria-hidden="true">
              SE
            </span>
            <span className="nav__link-label">Settings</span>
          </NavLink>
          <div className="nav__utility">
            <Button variant="quiet" small onClick={signOut}>
              {collapsed ? "Out" : "Sign out"}
            </Button>
          </div>
        </div>
      </nav>

      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}
