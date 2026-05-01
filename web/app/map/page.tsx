import Link from "next/link";

import { getCrimeOverview } from "../crimeOverview";
import { CrimeDashboard } from "../../components/CrimeDashboard";

export default async function MapPage() {
  const { overview, error, note } = await getCrimeOverview();
  return (
    <main className="bulletin-shell">
      <div className="bulletin-topline">
        <span>Map Room</span>
        <span>Field notes from the five boroughs</span>
        <span>Street Ledger</span>
      </div>
      <header className="masthead">
        <div>
          <p className="kicker">The Street Ledger</p>
          <h1 className="masthead-title">NYC Hot Spots</h1>
          <p className="masthead-deck">
            A crime-desk map with Google tilt, deck.gl density columns, severity filters,
            Street View jump-outs, and enough red ink to make the night shift nervous.
          </p>
        </div>
        <aside className="price-box" aria-label="Map room status">
          <span>Layer</span>
          <strong>3D</strong>
          <span>density mode</span>
        </aside>
      </header>
      <nav className="bulletin-nav">
        <Link className="nav-link" href="/graphs">Front Page</Link>
        <Link className="nav-link" href="/map">The Map Room</Link>
      </nav>
      <div className="ticker">Drag, tilt, filter, investigate. Every marker links back to source data.</div>
      {note ? (
        <p className="paper-card blotter-note" style={{ margin: "1rem 0 0", padding: "0.75rem" }}>{note}</p>
      ) : null}

      <div className="content-stack">
        <CrimeDashboard overview={overview} error={error} view="map" />
      </div>
    </main>
  );
}
