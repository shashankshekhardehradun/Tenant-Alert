import Link from "next/link";

import { getCrimeOverview } from "../crimeOverview";
import { CrimeDashboard } from "../../components/CrimeDashboard";
import { LiveNewsTicker } from "../../components/LiveNewsTicker";

export default async function GraphsPage() {
  const { overview, error, note } = await getCrimeOverview();
  return (
    <main className="bulletin-shell">
      <div className="bulletin-topline">
        <span>Friday Edition</span>
        <span>Your daily dose of NYC almost behaving</span>
        <span>Issue 311</span>
      </div>
      <header className="masthead">
        <div>
          <p className="kicker">Daily Bulletin</p>
          <h1 className="masthead-title">NYC Crime Pulse</h1>
          <p className="masthead-deck">
            Borough beefs, midnight spikes, socioeconomic context, and enough data engineering
            under the hood to make this corner-store tabloid suspiciously well informed.
          </p>
        </div>
        <aside className="price-box" aria-label="Bulletin price">
          <span>Only</span>
          <strong>25¢</strong>
          <span>plus tax and anxiety</span>
        </aside>
      </header>
      <nav className="bulletin-nav">
        <Link className="nav-link" href="/graphs">Front Page</Link>
        <Link className="nav-link" href="/map">The Map Room</Link>
        <Link className="nav-link" href="/risk">Risk Receipt</Link>
        <Link className="nav-link" href="/avoid">I Would Avoid</Link>
        <Link className="nav-link" href="/boroughs/manhattan">Borough Files</Link>
      </nav>
      <LiveNewsTicker fallbackItems={[
        "Stay woke. Stay safe. This is NYC.",
        "Data refreshed from BigQuery gold marts.",
        "Population-normalized risk now on page one.",
      ]} />
      {note ? (
        <p className="paper-card blotter-note" style={{ margin: "1rem 0 0", padding: "0.75rem" }}>{note}</p>
      ) : null}

      <div className="content-stack">
        <CrimeDashboard overview={overview} error={error} view="graphs" />
      </div>
    </main>
  );
}
