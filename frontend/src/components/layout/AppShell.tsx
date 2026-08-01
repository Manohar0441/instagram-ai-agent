import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../auth/useAuth";
import { Button } from "../ui";
import "./layout.css";

const NAV_GROUPS = [
  {
    label: "Analytics",
    links: [
      { to: "/dashboard", label: "Overview" },
      { to: "/trends", label: "Trends" },
      { to: "/media", label: "Posts" },
      { to: "/top-content", label: "Rankings" },
    ],
  },
  {
    label: "Intelligence",
    links: [
      { to: "/chat", label: "Ask" },
      { to: "/insights", label: "Insights" },
      { to: "/recommendations", label: "Recommendations" },
      { to: "/reports", label: "Reports" },
    ],
  },
];

export function AppShell() {
  const { signOut } = useAuth();

  return (
    <div className="shell">
      <nav className="nav" aria-label="Main">
        <NavLink to="/dashboard" className="nav__brand">
          Instalysis
        </NavLink>

        {NAV_GROUPS.map((group) => (
          <div className="nav__group" key={group.label}>
            <span className="nav__group-label">{group.label}</span>
            {group.links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `nav__link ${isActive ? "nav__link--active" : ""}`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </div>
        ))}

        <div className="nav__footer">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `nav__link ${isActive ? "nav__link--active" : ""}`
            }
          >
            Settings
          </NavLink>
          <Button variant="quiet" small onClick={signOut}>
            Sign out
          </Button>
        </div>
      </nav>

      <main className="shell__main">
        <Outlet />
      </main>
    </div>
  );
}
