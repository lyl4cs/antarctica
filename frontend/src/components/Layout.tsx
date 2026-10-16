/**
 * App shell: the header (logo + primary nav) around every page.
 *
 * React Router renders the current page into <Outlet />. NavLink adds the "active"
 * class for us, which styles.css turns into the sand pill from the design, and sets
 * aria-current="page" for screen readers.
 */
import { Link, NavLink, Outlet } from "react-router-dom";
import { LogoMark } from "./Logo";

const REPO = "https://github.com/lyl4cs/sn0wy";

function GitHubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

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
        <footer className="site-footer">
          <span>
            sn0wy is open source. Found a fix that was confidently wrong?{" "}
            <a href={`${REPO}/issues/new?labels=bad-fix`} target="_blank" rel="noopener noreferrer">
              Tell me about it
            </a>
            .
          </span>
          <a className="repo-link" href={REPO} target="_blank" rel="noopener noreferrer">
            <GitHubMark />
            View on GitHub
          </a>
        </footer>
      </div>
    </div>
  );
}
