"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

type BoroughCrimeRow = { borough: string; crime_count: number };
type LawCategoryRow = { law_category: string; crime_count: number };
type DailyOffenseBreakdown = { offense_description: string; crime_count: number };
type DailyCrimeRow = {
  day: string;
  crime_count: number;
  top_offenses?: DailyOffenseBreakdown[];
};
type TopOffenseRow = { offense_description: string; law_category: string; crime_count: number };
type CrimeMapPoint = {
  complaint_id: string;
  complaint_date: string;
  borough: string;
  law_category: string;
  offense_description: string;
  premise_type?: string | null;
  latitude: number;
  longitude: number;
};

export type CrimeOverviewPayload = {
  source: string;
  start_date: string;
  end_date: string;
  row_count: number;
  by_borough: BoroughCrimeRow[];
  by_law_category: LawCategoryRow[];
  daily_trend: DailyCrimeRow[];
  top_offenses: TopOffenseRow[];
  map_points?: CrimeMapPoint[];
};

const NYC_BOUNDS = {
  minLat: 40.45,
  maxLat: 40.95,
  minLng: -74.3,
  maxLng: -73.65,
};

const BOROUGH_COLORS: Record<string, string> = {
  BRONX: "#c4320a",
  BROOKLYN: "#175cd3",
  MANHATTAN: "#7c3aed",
  QUEENS: "#067647",
  "STATEN ISLAND": "#b54708",
};

function DailyCrimeTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) {
    return null;
  }

  const row = payload[0]?.payload as { crimes?: number; topOffenses?: DailyOffenseBreakdown[] };
  return (
    <div
      style={{
        background: "white",
        border: "1px solid #d0d5dd",
        borderRadius: 8,
        boxShadow: "0 8px 24px rgba(16, 24, 40, 0.12)",
        padding: "0.75rem",
        maxWidth: 320,
      }}
    >
      <strong>{label}</strong>
      <p style={{ margin: "0.35rem 0" }}>{Number(row.crimes ?? 0).toLocaleString()} events</p>
      {row.topOffenses?.length ? (
        <>
          <p style={{ margin: "0.5rem 0 0.25rem", color: "#475467" }}>Top offense types</p>
          <ol style={{ margin: 0, paddingLeft: "1.25rem" }}>
            {row.topOffenses.map((offense) => (
              <li key={offense.offense_description}>
                {offense.offense_description}: {offense.crime_count.toLocaleString()}
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </div>
  );
}

function CrimeMap({ points }: { points: CrimeMapPoint[] }) {
  if (!points.length) {
    return <p style={{ color: "#475467" }}>No geocoded crime points available for this window.</p>;
  }

  const plottedPoints = points.map((point) => {
    const x = ((point.longitude - NYC_BOUNDS.minLng) / (NYC_BOUNDS.maxLng - NYC_BOUNDS.minLng)) * 100;
    const y = 100 - ((point.latitude - NYC_BOUNDS.minLat) / (NYC_BOUNDS.maxLat - NYC_BOUNDS.minLat)) * 100;
    return { ...point, x, y };
  });

  return (
    <div
      style={{
        border: "1px solid #d0d5dd",
        borderRadius: 12,
        background: "linear-gradient(135deg, #f8fafc 0%, #eef4ff 100%)",
        overflow: "hidden",
      }}
    >
      <svg viewBox="0 0 100 100" role="img" aria-label="Sampled crime event locations across NYC">
        <rect x="0" y="0" width="100" height="100" fill="transparent" />
        <path
          d="M48 5 C56 16 58 31 54 46 C51 60 49 72 52 94"
          fill="none"
          stroke="#98a2b3"
          strokeDasharray="1.5 2"
          strokeWidth="0.5"
        />
        {plottedPoints.map((point) => (
          <circle
            key={point.complaint_id}
            cx={point.x}
            cy={point.y}
            r="0.75"
            fill={BOROUGH_COLORS[point.borough] ?? "#344054"}
            opacity="0.7"
          >
            <title>
              {point.complaint_date} · {point.borough} · {point.offense_description}
              {point.premise_type ? ` · ${point.premise_type}` : ""}
            </title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

export function CrimeDashboard(props: { overview: CrimeOverviewPayload | null; error?: string }) {
  if (props.error) {
    return <p style={{ color: "#b42318" }}>{props.error}</p>;
  }

  if (!props.overview) {
    return <p>No crime analytics payload returned yet.</p>;
  }

  if (props.overview.row_count === 0) {
    return (
      <p style={{ color: "#475467" }}>
        No NYPD crime rows found for {props.overview.start_date} → {props.overview.end_date}.
        Ingest NYPD complaints and run dbt to populate <code>gold.gold_fct_crime_events</code>.
      </p>
    );
  }

  const boroughData = props.overview.by_borough.map((row) => ({
    borough: row.borough,
    crimes: row.crime_count,
  }));
  const lawData = props.overview.by_law_category.map((row) => ({
    category: row.law_category,
    crimes: row.crime_count,
  }));
  const trendData = props.overview.daily_trend.map((row) => ({
    day: row.day,
    crimes: row.crime_count,
    topOffenses: row.top_offenses ?? [],
  }));
  const offenseData = props.overview.top_offenses.map((row) => ({
    offense:
      row.offense_description.length > 38
        ? `${row.offense_description.slice(0, 38)}...`
        : row.offense_description,
    crimes: row.crime_count,
  }));
  const mapPoints = props.overview.map_points ?? [];

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <section>
        <h2 style={{ margin: "0 0 0.75rem" }}>NYC Roulette crime window</h2>
        <p style={{ margin: 0, color: "#475467" }}>
          {props.overview.start_date} → {props.overview.end_date} ·{" "}
          <strong>{props.overview.row_count.toLocaleString()}</strong> reported events · source:{" "}
          <strong>{props.overview.source}</strong>
        </p>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.5rem" }}>Crime location sample</h3>
        <p style={{ margin: "0 0 0.75rem", color: "#475467" }}>
          Showing up to {mapPoints.length.toLocaleString()} geocoded events sampled from the selected
          window. Hover a dot for event context.
        </p>
        <CrimeMap points={mapPoints} />
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Reported crime by borough</h3>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={boroughData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="borough" />
              <YAxis />
              <Tooltip content={<DailyCrimeTooltip />} />
              <Legend />
              <Bar dataKey="crimes" name="Reported events" fill="#c4320a" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Daily reported crime trend</h3>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="crimes"
                name="Reported events"
                stroke="#7a271a"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Severity mix</h3>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={lawData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="category" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="crimes" name="Reported events" fill="#7c3aed" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Top reported offenses</h3>
        <div style={{ width: "100%", height: 360 }}>
          <ResponsiveContainer>
            <BarChart
              layout="vertical"
              data={offenseData}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="offense" width={220} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="crimes" name="Reported events" fill="#175cd3" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
