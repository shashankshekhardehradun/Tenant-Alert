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

type BoroughRow = { borough: string; complaint_count: number };
type TrendRow = { day: string; complaint_count: number };
type TopTypeRow = { complaint_type: string; complaint_count: number };
export type NtaDemographicRow = {
  nta_code: string;
  nta_name: string;
  borough: string;
  total_population: number | null;
  approx_median_household_income: number | null;
  approx_median_gross_rent: number | null;
  poverty_rate: number | null;
  renter_share: number | null;
};

export type OverviewPayload = {
  start_date: string;
  end_date: string;
  source?: string;
  row_count?: number;
  by_borough: BoroughRow[];
  daily_trend: TrendRow[];
  top_complaint_types: TopTypeRow[];
};

export function DashboardCharts(props: {
  overview: OverviewPayload | null;
  demographics?: NtaDemographicRow[];
  error?: string;
}) {
  if (props.error) {
    return <p style={{ color: "#b42318" }}>{props.error}</p>;
  }

  if (!props.overview) {
    return <p>No analytics payload returned.</p>;
  }

  if (props.overview.row_count === 0) {
    return (
      <p style={{ color: "#475467" }}>
        No 311 rows found in BigQuery for{" "}
        <strong>
          {props.overview.start_date} → {props.overview.end_date}
        </strong>
        . Load more historical partitions into <code>bronze.raw_311_complaints</code> or expand the date range.
      </p>
    );
  }

  const boroughData = props.overview.by_borough.map((row) => ({
    borough: row.borough,
    complaints: row.complaint_count,
  }));

  const trendData = props.overview.daily_trend.map((row) => ({
    day: row.day,
    complaints: row.complaint_count,
  }));

  const topTypes = props.overview.top_complaint_types.map((row) => ({
    type: row.complaint_type.length > 42 ? `${row.complaint_type.slice(0, 42)}…` : row.complaint_type,
    complaints: row.complaint_count,
  }));

  const demographicByBorough = Object.values(
    (props.demographics ?? []).reduce<
      Record<string, { borough: string; population: number; incomeTotal: number; rentTotal: number }>
    >((acc, row) => {
      const population = Number(row.total_population ?? 0);
      const income = Number(row.approx_median_household_income ?? 0);
      const rent = Number(row.approx_median_gross_rent ?? 0);
      if (!row.borough || population <= 0) {
        return acc;
      }
      acc[row.borough] ??= { borough: row.borough, population: 0, incomeTotal: 0, rentTotal: 0 };
      acc[row.borough].population += population;
      acc[row.borough].incomeTotal += income * population;
      acc[row.borough].rentTotal += rent * population;
      return acc;
    }, {}),
  ).map((row) => ({
    borough: row.borough,
    medianIncome: Math.round(row.incomeTotal / row.population),
    medianRent: Math.round(row.rentTotal / row.population),
  }));

  return (
    <div style={{ display: "grid", gap: "1.5rem" }}>
      <section>
        <h2 style={{ margin: "0 0 0.75rem" }}>Dashboard window (UTC days)</h2>
        <p style={{ margin: 0, color: "#475467" }}>
          {props.overview.start_date} → {props.overview.end_date}
          {props.overview.source ? (
            <>
              {" "}
              · source: <strong>{props.overview.source}</strong>
            </>
          ) : null}
          {typeof props.overview.row_count === "number" ? (
            <>
              {" "}
              · <strong>{props.overview.row_count.toLocaleString()}</strong> complaints in range
            </>
          ) : null}
        </p>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Complaints by borough</h3>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <BarChart data={boroughData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="borough" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="complaints" name="Complaints" fill="#2f6fed" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Daily complaint volume</h3>
        <div style={{ width: "100%", height: 320 }}>
          <ResponsiveContainer>
            <LineChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="complaints" name="Complaints" stroke="#12a150" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 style={{ margin: "0 0 0.75rem" }}>Top complaint types</h3>
        <div style={{ width: "100%", height: 360 }}>
          <ResponsiveContainer>
            <BarChart
              layout="vertical"
              data={topTypes}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="type" width={220} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="complaints" name="Complaints" fill="#7c3aed" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {demographicByBorough.length > 0 ? (
        <section>
          <h3 style={{ margin: "0 0 0.75rem" }}>ACS demographics preview by borough</h3>
          <p style={{ margin: "0 0 0.75rem", color: "#475467" }}>
            Population-weighted NTA estimates. Median-style fields are approximate until we add
            distribution-based interpolation.
          </p>
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <BarChart
                data={demographicByBorough}
                margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="borough" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="medianIncome" name="Approx. median household income" fill="#0e9384" />
                <Bar dataKey="medianRent" name="Approx. median gross rent" fill="#f79009" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
    </div>
  );
}
