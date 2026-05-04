import Link from "next/link";

import { LiveNewsTicker } from "../../components/LiveNewsTicker";
import { RiskCalculator } from "../../components/RiskCalculator";

export default function RiskPage() {
  return (
    <main className="bulletin-shell">
      <div className="bulletin-topline">
        <span>Risk Desk</span>
        <span>Bodega receipt, BigQuery backbone</span>
        <span>Fate printer online</span>
      </div>
      <header className="masthead">
        <div>
          <p className="kicker">NYC Crime Roulette</p>
          <h1 className="masthead-title">Receipt of Fate</h1>
          <p className="masthead-deck">
            A playful risk calculator styled like your bodega receipt, backed by historical
            borough/hour crime density and transparent behavior/context factors.
          </p>
        </div>
        <aside className="price-box" aria-label="Risk receipt status">
          <span>Model</span>
          <strong>v0</strong>
          <span>explainable index</span>
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
        "Friend advice meets tabloid math.",
        "No protected traits used for scoring.",
        "Receipt printer warmed up.",
      ]} />
      <div className="content-stack">
        <RiskCalculator />
      </div>
    </main>
  );
}
