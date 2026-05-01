"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CrimeMap } from "./CrimeMap";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
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
type HourlyDensityRow = { day_of_week: number; hour: number; crime_count: number };
type DemographicBoroughRow = {
  borough: string;
  total_population: number;
  poverty_rate: number | null;
  renter_share: number | null;
  bachelors_or_higher_share: number | null;
  approx_median_household_income: number | null;
  approx_median_gross_rent: number | null;
  crime_count: number;
  crime_rate_per_100k: number | null;
};
type CrimeMapPoint = {
  complaint_id: string;
  source_dataset?: string | null;
  complaint_date: string;
  borough: string;
  law_category: string;
  offense_description: string;
  premise_type?: string | null;
  latitude: number;
  longitude: number;
};

type DashboardView = "all" | "graphs" | "map";

export type CrimeOverviewPayload = {
  source: string;
  start_date: string;
  end_date: string;
  row_count: number;
  by_borough: BoroughCrimeRow[];
  by_law_category: LawCategoryRow[];
  daily_trend: DailyCrimeRow[];
  top_offenses: TopOffenseRow[];
  hourly_density?: HourlyDensityRow[];
  demographics_by_borough?: DemographicBoroughRow[];
  map_points?: CrimeMapPoint[];
};

const BOROUGH_COLORS: Record<string, string> = {
  BRONX: "#c4320a",
  BROOKLYN: "#175cd3",
  MANHATTAN: "#7c3aed",
  QUEENS: "#067647",
  "STATEN ISLAND": "#b54708",
};

const VALID_BOROUGHS = new Set(Object.keys(BOROUGH_COLORS));

const LAW_CATEGORY_DESCRIPTIONS: Record<string, string> = {
  FELONY: "Most serious category, generally punishable by more than one year of incarceration.",
  MISDEMEANOR: "Mid-level criminal offense, generally less severe than a felony.",
  VIOLATION: "Lower-level offense, often not classified as a crime under NY state law.",
};

const LAW_CATEGORY_COLORS: Record<string, string> = {
  FELONY: "#b42318",
  MISDEMEANOR: "#f79009",
  VIOLATION: "#1570ef",
};

const DAY_LABELS: Record<number, string> = {
  1: "Sun",
  2: "Mon",
  3: "Tue",
  4: "Wed",
  5: "Thu",
  6: "Fri",
  7: "Sat",
};

const CARD_STYLE = {
  border: "1px solid #eaecf0",
  borderRadius: 18,
  padding: "1.1rem",
  background: "linear-gradient(180deg, #ffffff 0%, #fcfcfd 100%)",
  boxShadow: "0 12px 32px rgba(16, 24, 40, 0.07)",
} as const;

function isValidBorough(value: string | null | undefined) {
  return value ? VALID_BOROUGHS.has(value.toUpperCase()) : false;
}

function formatPercent(value: number | null | undefined) {
  return value == null ? "n/a" : `${(value * 100).toFixed(1)}%`;
}

function formatWholePercent(value: number) {
  return `${Math.round(value)}%`;
}

function formatCompact(value: number | null | undefined) {
  return value == null
    ? "n/a"
    : Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function formatCurrency(value: number | null | undefined) {
  return value == null
    ? "n/a"
    : Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(value);
}

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

function EventLegend({
  lawCategories,
  includeMapLegend,
}: {
  lawCategories: LawCategoryRow[];
  includeMapLegend: boolean;
}) {
  const categories = lawCategories
    .filter((row) => row.law_category)
    .map((row) => row.law_category.toUpperCase());
  const uniqueCategories = Array.from(new Set(categories));

  return (
    <section
      style={{
        ...CARD_STYLE,
      }}
    >
      <h3 style={{ margin: "0 0 0.75rem" }}>Event legend</h3>
      <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        <div>
          <h4 style={{ margin: "0 0 0.5rem" }}>Borough colors</h4>
          <div style={{ display: "grid", gap: "0.35rem" }}>
            {Object.entries(BOROUGH_COLORS).map(([borough, color]) => (
              <span key={borough} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span
                  aria-hidden="true"
                  style={{ width: 12, height: 12, borderRadius: 999, background: color }}
                />
                {borough}
              </span>
            ))}
          </div>
        </div>
        <div>
          <h4 style={{ margin: "0 0 0.5rem" }}>Event categories</h4>
          <div style={{ display: "grid", gap: "0.5rem" }}>
            {uniqueCategories.map((category) => (
              <p key={category} style={{ display: "flex", gap: "0.5rem", margin: 0 }}>
                <span
                  aria-hidden="true"
                  style={{
                    background: LAW_CATEGORY_COLORS[category] ?? "#667085",
                    borderRadius: 999,
                    flex: "0 0 auto",
                    height: 12,
                    marginTop: 4,
                    width: 12,
                  }}
                />
                <span>
                <strong>{category}</strong>:{" "}
                {LAW_CATEGORY_DESCRIPTIONS[category] ?? "NYPD law category from the source complaint data."}
                </span>
              </p>
            ))}
          </div>
        </div>
        {includeMapLegend ? (
        <div>
          <h4 style={{ margin: "0 0 0.5rem" }}>Map marks</h4>
          <p style={{ margin: 0 }}>
            Each dot is a sampled geocoded NYPD complaint event. The heat layer shows local event
            density. Hover a dot for offense details, source data, and Google Maps links.
          </p>
        </div>
        ) : null}
      </div>
    </section>
  );
}

function MetricCards({
  rowCount,
  boroughs,
  topOffense,
  density,
}: {
  rowCount: number;
  boroughs: BoroughCrimeRow[];
  topOffense?: TopOffenseRow;
  density: HourlyDensityRow[];
}) {
  const peakCell = density.reduce<HourlyDensityRow | null>(
    (best, row) => (!best || row.crime_count > best.crime_count ? row : best),
    null,
  );
  const topBorough = boroughs[0];
  const metrics = [
    { label: "Events in window", value: rowCount.toLocaleString(), detail: "Filtered to geocoded NYC records" },
    { label: "Highest borough", value: topBorough?.borough ?? "n/a", detail: `${formatCompact(topBorough?.crime_count)} events` },
    { label: "Top offense", value: topOffense?.offense_description ?? "n/a", detail: `${formatCompact(topOffense?.crime_count)} events` },
    {
      label: "Peak time cell",
      value: peakCell ? `${DAY_LABELS[peakCell.day_of_week]} ${peakCell.hour}:00` : "n/a",
      detail: `${formatCompact(peakCell?.crime_count)} events`,
    },
  ];

  return (
    <section style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))" }}>
      {metrics.map((metric) => (
        <div key={metric.label} style={{ ...CARD_STYLE, background: "linear-gradient(135deg, #111827 0%, #7a271a 100%)", color: "white" }}>
          <p style={{ margin: "0 0 0.35rem", opacity: 0.75 }}>{metric.label}</p>
          <strong style={{ display: "block", fontSize: "1.45rem", lineHeight: 1.1 }}>{metric.value}</strong>
          <p style={{ margin: "0.45rem 0 0", opacity: 0.75 }}>{metric.detail}</p>
        </div>
      ))}
    </section>
  );
}

function HourlyDensityPlot({ rows }: { rows: HourlyDensityRow[] }) {
  const maxCount = Math.max(...rows.map((row) => row.crime_count), 1);
  const byKey = new Map(rows.map((row) => [`${row.day_of_week}-${row.hour}`, row.crime_count]));

  return (
    <section style={CARD_STYLE}>
      <h3 style={{ margin: "0 0 0.4rem" }}>Crime density by hour and weekday</h3>
      <p style={{ margin: "0 0 1rem", color: "#475467" }}>
        Darker cells show the time blocks where reported events concentrate.
      </p>
      <div style={{ overflowX: "auto" }}>
        <div style={{ minWidth: 760 }}>
          <div style={{ display: "grid", gridTemplateColumns: "52px repeat(24, 1fr)", gap: 3, marginBottom: 4 }}>
            <span />
            {Array.from({ length: 24 }, (_, hour) => (
              <span key={hour} style={{ fontSize: 10, color: "#667085", textAlign: "center" }}>
                {hour}
              </span>
            ))}
          </div>
          {Object.entries(DAY_LABELS).map(([day, label]) => (
            <div key={day} style={{ display: "grid", gridTemplateColumns: "52px repeat(24, 1fr)", gap: 3, marginBottom: 3 }}>
              <strong style={{ fontSize: 12, color: "#475467" }}>{label}</strong>
              {Array.from({ length: 24 }, (_, hour) => {
                const count = byKey.get(`${day}-${hour}`) ?? 0;
                const intensity = count / maxCount;
                return (
                  <div
                    key={hour}
                    title={`${label} ${hour}:00 - ${count.toLocaleString()} events`}
                    style={{
                      height: 22,
                      borderRadius: 5,
                      background: `rgba(196, 50, 10, ${0.08 + intensity * 0.92})`,
                    }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function SocioeconomicScatter({ rows }: { rows: DemographicBoroughRow[] }) {
  const data = rows
    .filter((row) => isValidBorough(row.borough))
    .map((row) => ({
      ...row,
      povertyPct: (row.poverty_rate ?? 0) * 100,
      renterPct: (row.renter_share ?? 0) * 100,
      income: row.approx_median_household_income ?? 0,
      rate: row.crime_rate_per_100k ?? 0,
    }));

  return (
    <section style={CARD_STYLE}>
      <h3 style={{ margin: "0 0 0.4rem" }}>Crime rate vs economic context</h3>
      <p style={{ margin: "0 0 1rem", color: "#475467" }}>
        Poverty rate is the share of borough residents whose household income falls below the Census
        poverty threshold. A borough can have a high median income and still have a meaningful poverty
        rate because both numbers describe different parts of the income distribution. Bubble size
        reflects reported crimes per 100k residents in the selected window.
      </p>
      <div style={{ width: "100%", height: 360 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 20, right: 30, bottom: 35, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eaecf0" />
            <XAxis
              dataKey="povertyPct"
              domain={[0, "dataMax + 5"]}
              name="Poverty rate"
              tickFormatter={(value) => formatWholePercent(Number(value))}
              type="number"
            />
            <YAxis dataKey="income" name="Median household income" tickFormatter={(value) => `$${Math.round(Number(value) / 1000)}k`} />
            <ZAxis dataKey="rate" range={[180, 900]} name="Crime rate per 100k" />
            <Tooltip
              formatter={(value, name) => {
                if (name === "Median household income") return [formatCurrency(Number(value)), name];
                if (name === "Poverty rate") return [formatWholePercent(Number(value)), name];
                if (name === "Crime rate per 100k") return [Number(value).toFixed(1), name];
                return [value, name];
              }}
              cursor={{ strokeDasharray: "3 3" }}
            />
            <Scatter name="Boroughs" data={data}>
              {data.map((row) => (
                <Cell key={row.borough} fill={BOROUGH_COLORS[row.borough] ?? "#175cd3"} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div
        style={{
          display: "grid",
          gap: "0.5rem",
          gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
          marginTop: "0.75rem",
          color: "#475467",
          fontSize: 13,
        }}
      >
        <span><strong>X axis:</strong> Census poverty rate</span>
        <span><strong>Y axis:</strong> median household income</span>
        <span><strong>Bubble size:</strong> crimes per 100k residents</span>
        <span><strong>Color:</strong> borough</span>
      </div>
    </section>
  );
}

function RotatableRiskSpace({ rows }: { rows: DemographicBoroughRow[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState("Loading 3D view...");
  const data = useMemo(() => rows.filter((row) => isValidBorough(row.borough)), [rows]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || data.length === 0) {
      setStatus(data.length === 0 ? "No demographic data available for the 3D view." : "Loading 3D view...");
      return;
    }

    let cancelled = false;
    import("plotly.js-dist-min")
      .then((Plotly) => {
        if (cancelled) {
          return;
        }

        const x = data.map((row) => Number(((row.poverty_rate ?? 0) * 100).toFixed(1)));
        const y = data.map((row) => Number(((row.renter_share ?? 0) * 100).toFixed(1)));
        const z = data.map((row) => Math.round(row.approx_median_household_income ?? 0));
        const crimeRates = data.map((row) => Number((row.crime_rate_per_100k ?? 0).toFixed(1)));
        const text = data.map(
          (row) =>
            `${row.borough}<br>` +
            `Poverty: ${formatPercent(row.poverty_rate)}<br>` +
            `Renter share: ${formatPercent(row.renter_share)}<br>` +
            `Median income: ${formatCurrency(row.approx_median_household_income)}<br>` +
            `Crime rate: ${(row.crime_rate_per_100k ?? 0).toFixed(1)} per 100k`,
        );

        Plotly.newPlot(
          element,
          [
            {
              x,
              y,
              z,
              text,
              mode: "markers",
              type: "scatter3d",
              marker: {
                color: crimeRates,
                colorscale: [
                  [0, "#1570ef"],
                  [0.5, "#f79009"],
                  [1, "#b42318"],
                ],
                line: { color: "#ffffff", width: 1 },
                opacity: 0.9,
                size: data.map((row) => 12 + ((row.crime_rate_per_100k ?? 0) / 750) * 18),
                showscale: true,
                colorbar: { title: "Crimes per 100k" },
              },
              hovertemplate: "%{text}<extra></extra>",
            },
          ],
          {
            autosize: true,
            margin: { l: 0, r: 0, t: 0, b: 0 },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            scene: {
              xaxis: { title: "Poverty rate (%)", tickformat: ".0f" },
              yaxis: { title: "Renter share (%)", tickformat: ".0f" },
              zaxis: { title: "Median income ($)", tickprefix: "$" },
              camera: { eye: { x: 1.55, y: 1.65, z: 1.25 } },
            },
          },
          {
            displaylogo: false,
            responsive: true,
            scrollZoom: true,
          },
        ).then(() => setStatus(""));
      })
      .catch(() => setStatus("Could not load the interactive 3D chart."));

    return () => {
      cancelled = true;
      import("plotly.js-dist-min").then((Plotly) => Plotly.purge(element));
    };
  }, [data]);

  return (
    <section style={CARD_STYLE}>
      <h3 style={{ margin: "0 0 0.4rem" }}>Rotatable socioeconomic crime space</h3>
      <p style={{ margin: "0 0 1rem", color: "#475467" }}>
        Drag to rotate 360 degrees. Each point is a borough: x = poverty rate, y = renter share,
        z = median household income, and color/size = observed crime rate per 100k residents.
      </p>
      {status ? <p style={{ color: "#475467", margin: 0 }}>{status}</p> : null}
      <div ref={containerRef} style={{ height: 520, width: "100%" }} />
    </section>
  );
}

export function CrimeDashboard(props: {
  overview: CrimeOverviewPayload | null;
  error?: string;
  view?: DashboardView;
}) {
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

  const view = props.view ?? "all";
  const showMap = view === "all" || view === "map";
  const showGraphs = view === "all" || view === "graphs";
  const boroughData = props.overview.by_borough
    .filter((row) => isValidBorough(row.borough))
    .map((row) => ({
      borough: row.borough,
      crimes: row.crime_count,
    }));
  const lawData = props.overview.by_law_category.map((row) => ({
    category: row.law_category,
    crimes: row.crime_count,
  }));
  const hourlyDensity = props.overview.hourly_density ?? [];
  const demographics = props.overview.demographics_by_borough ?? [];
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
  const mapPoints = (props.overview.map_points ?? []).filter((point) => isValidBorough(point.borough));

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

      <EventLegend lawCategories={props.overview.by_law_category} includeMapLegend={showMap} />

      {showMap ? (
      <section>
        <h3 style={{ margin: "0 0 0.5rem" }}>Crime location sample</h3>
        <p style={{ margin: "0 0 0.75rem", color: "#475467" }}>
          Showing up to {mapPoints.length.toLocaleString()} geocoded events sampled from the selected
          window. Hover a dot for event context.
        </p>
        <CrimeMap points={mapPoints} />
      </section>
      ) : null}

      {showGraphs ? (
      <>
      <MetricCards
        rowCount={props.overview.row_count}
        boroughs={props.overview.by_borough.filter((row) => isValidBorough(row.borough))}
        topOffense={props.overview.top_offenses[0]}
        density={hourlyDensity}
      />

      <section style={CARD_STYLE}>
        <h3 style={{ margin: "0 0 0.75rem" }}>Reported crime by borough</h3>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={boroughData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eaecf0" />
              <XAxis dataKey="borough" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="crimes" name="Reported events" radius={[10, 10, 0, 0]}>
                {boroughData.map((row) => (
                  <Cell key={row.borough} fill={BOROUGH_COLORS[row.borough] ?? "#c4320a"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section style={CARD_STYLE}>
        <h3 style={{ margin: "0 0 0.75rem" }}>Daily reported crime trend</h3>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <AreaChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="crimeTrend" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#c4320a" stopOpacity={0.55} />
                  <stop offset="95%" stopColor="#c4320a" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#eaecf0" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis />
              <Tooltip content={<DailyCrimeTooltip />} />
              <Legend />
              <Area
                type="monotone"
                dataKey="crimes"
                name="Reported events"
                stroke="#7a271a"
                strokeWidth={2}
                fill="url(#crimeTrend)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section style={CARD_STYLE}>
        <h3 style={{ margin: "0 0 0.75rem" }}>Severity mix</h3>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={lawData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eaecf0" />
              <XAxis dataKey="category" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="crimes" name="Reported events" radius={[10, 10, 0, 0]}>
                {lawData.map((row) => (
                  <Cell
                    key={row.category}
                    fill={LAW_CATEGORY_COLORS[row.category?.toUpperCase()] ?? "#667085"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <HourlyDensityPlot rows={hourlyDensity} />

      <SocioeconomicScatter rows={demographics} />

      <RotatableRiskSpace rows={demographics} />

      <section style={CARD_STYLE}>
        <h3 style={{ margin: "0 0 0.75rem" }}>Top reported offenses</h3>
        <div style={{ width: "100%", height: 360 }}>
          <ResponsiveContainer>
            <BarChart
              layout="vertical"
              data={offenseData}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#eaecf0" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="offense" width={220} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="crimes" name="Reported events" fill="#175cd3" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
      </>
      ) : null}
    </div>
  );
}
