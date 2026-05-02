import Link from "next/link";

import { getCrimeOverview } from "../crimeOverview";
import { CrimeDashboard } from "../../components/CrimeDashboard";
import { LiveNewsTicker } from "../../components/LiveNewsTicker";

export default async function MapPage() {
  const { overview, error, note } = await getCrimeOverview({ latestDayOnly: true, mapLimit: 5000 });
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
          <strong>LIVE</strong>
          <span>severity density</span>
        </aside>
      </header>
      <nav className="bulletin-nav">
        <Link className="nav-link" href="/graphs">Front Page</Link>
        <Link className="nav-link" href="/map">The Map Room</Link>
        <Link className="nav-link" href="/risk">Risk Receipt</Link>
        <Link className="nav-link" href="/boroughs/manhattan">Borough Files</Link>
      </nav>
      <LiveNewsTicker fallbackItems={[
        "Latest-day map only.",
        "Drag, filter, investigate.",
        "Every marker links back to source data.",
      ]} />
      {note ? (
        <p className="paper-card blotter-note" style={{ margin: "1rem 0 0", padding: "0.75rem" }}>{note}</p>
      ) : null}

      <div className="content-stack">
        <CrimeDashboard overview={overview} error={error} view="map" />
      </div>
    </main>
  );
}
