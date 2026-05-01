import Link from "next/link";

import { getCrimeOverview } from "../crimeOverview";
import { CrimeDashboard } from "../../components/CrimeDashboard";

export default async function MapPage() {
  const { overview, error, note } = await getCrimeOverview();
  return (
    <main style={{ margin: "2rem auto", maxWidth: 1200, fontFamily: "system-ui, sans-serif" }}>
      <nav style={{ display: "flex", gap: "1rem", marginBottom: "1.25rem" }}>
        <Link href="/graphs">Graphs</Link>
        <Link href="/map">Map</Link>
      </nav>
      <h1 style={{ margin: "0 0 0.5rem" }}>NYC Roulette map</h1>
      <p style={{ margin: "0 0 1.5rem", color: "#475467", maxWidth: "80ch" }}>
        Interactive geospatial view of sampled NYPD complaint events with density and event details.
      </p>
      {note ? (
        <p style={{ margin: "0 0 1rem", color: "#175cd3", maxWidth: "80ch" }}>{note}</p>
      ) : null}

      <CrimeDashboard overview={overview} error={error} view="map" />
    </main>
  );
}
