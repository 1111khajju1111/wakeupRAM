import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../store/AuthContext";
import { useTheme } from "../theme/ThemeProvider";

const navItems = [
  ["/", "Home", "01"],
  ["/today", "Today", "02"],
  ["/habits", "Habits", "03"],
  ["/insights", "Insights", "04"],
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { user, logout } = useAuth();
  const { resolvedMode, mode, setMode } = useTheme();
  const displayName = user?.profile?.display_name || "Ram";

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="brand-mark" to="/" aria-label="Wake Up Ram home">
          <span className="brand-mark__glyph">WR</span>
          <span><strong>WAKE UP</strong><small>RAM</small></span>
        </Link>
        <div className="header-actions">
          <button className="icon-button" type="button" onClick={() => setMode(mode === "dark" ? "light" : "dark")} aria-label="Toggle theme">
            {resolvedMode === "dark" ? "L" : "D"}
          </button>
          <button className="profile-chip" type="button" onClick={() => void logout()} title="Sign out">
            <span>{displayName.slice(0, 1).toUpperCase()}</span>
          </button>
        </div>
      </header>

      <div className="app-shell__content">{children}</div>

      <nav className="bottom-nav" aria-label="Primary navigation">
        {navItems.map(([path, label, index]) => {
          const active = path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);
          return <Link key={path} className={active ? "bottom-nav__item bottom-nav__item--active" : "bottom-nav__item"} to={path}>
            <span className="bottom-nav__index">{index}</span><span>{label}</span>
          </Link>;
        })}
        <Link className={location.pathname === "/call" ? "bottom-nav__item bottom-nav__item--active bottom-nav__talk" : "bottom-nav__item bottom-nav__talk"} to="/call">
          <span className="bottom-nav__index">+</span><span>Talk</span>
        </Link>
      </nav>
    </div>
  );
}
