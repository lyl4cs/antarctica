/**
 * App shell: the header (logo + primary nav) around every page.
 *
 * React Router renders the current page into <Outlet />. NavLink adds the "active"
 * class for us, which styles.css turns into the sand pill from the design, and sets
 * aria-current="page" for screen readers.
 */
import { Link, NavLink, Outlet } from "react-router-dom";
import { LogoMark } from "./Logo";

export function Layout() {
  return (
    <div className="shell">
      <div className="container">
        <header className="site-header">
          <Link to="/" className="brand" aria-label="Sn0wy home">
            <LogoMark />
            <span className="brand-name" aria-hidden="true">
              sn0wy
            </span>
          </Link>
          <nav aria-label="Primary" className="nav">
            <NavLink to="/" end className="navlink">
              New scan
            </NavLink>
            <NavLink to="/history" className="navlink">
              History
            </NavLink>
          </nav>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
