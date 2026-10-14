import { Link } from "react-router-dom";
import { EmptyState } from "../components/States";
import { useTitle } from "../lib/useTitle";

export function NotFound() {
  useTitle("Not found");
  return (
    <main style={{ paddingTop: 28 }}>
      <EmptyState title="Nothing out here but ice">
        <p>That page doesn’t exist.</p>
        <Link to="/">Start a new scan</Link>
      </EmptyState>
    </main>
  );
}
