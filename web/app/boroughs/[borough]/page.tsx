import Link from "next/link";
import { notFound } from "next/navigation";

import { getCrimeOverview } from "../../crimeOverview";
import { CrimeDashboard } from "../../../components/CrimeDashboard";

const BOROUGHS: Record<string, string> = {
  bronx: "BRONX",
  brooklyn: "BROOKLYN",
  manhattan: "MANHATTAN",
  queens: "QUEENS",
  "staten-island": "STATEN ISLAND",
};

const BOROUGH_LINKS = Object.entries(BOROUGHS);

export function generateStaticParams() {
  return Object.keys(BOROUGHS).map((borough) => ({ borough }));
}

export default async function BoroughPage({ params }: { params: { borough: string } }) {
  const borough = BOROUGHS[params.borough];
  if (!borough) {
    notFound();
  }

  const { overview, error, note } = await getCrimeOverview({ borough, mapLimit: 1500 });

  return (
    <main className="bulletin-shell borough-dossier">
      <div className="bulletin-topline">
        <span>Borough File</span>
        <span>Local report card, not a moral scorecard</span>
        <span>{borough}</span>
      </div>
      <header className="masthead">
        <div>
          <p className="kicker">Neighborhood Report Card</p>
          <h1 className="masthead-title">{borough}</h1>
          <p className="masthead-deck">
            A borough-specific pull of the same NYPD complaint mart, with local incident mix,
            demographics, timing, and map evidence filtered to this file.
          </p>
        </div>
        <aside className="price-box" aria-label="Borough score">
          <span>File</span>
          <strong>{borough.slice(0, 2)}</strong>
          <span>local edition</span>
        </aside>
      </header>
      <nav className="bulletin-nav">
        <Link className="nav-link" href="/graphs">Front Page</Link>
        <Link className="nav-link" href="/map">The Map Room</Link>
        {BOROUGH_LINKS.map(([slug, label]) => (
          <Link className="nav-link" href={`/boroughs/${slug}`} key={slug}>
            {label}
          </Link>
        ))}
      </nav>
      <div className="ticker live-ticker">
        <span>{borough} dossier active</span>
        <span>Charts filtered by borough</span>
        <span>Map pins link back to source records</span>
        <span>{borough} dossier active</span>
      </div>
      {note ? (
        <p className="paper-card blotter-note" style={{ margin: "1rem 0 0", padding: "0.75rem" }}>{note}</p>
      ) : null}

      <div className="content-stack">
        <CrimeDashboard overview={overview} error={error} view="all" />
      </div>
    </main>
  );
}
