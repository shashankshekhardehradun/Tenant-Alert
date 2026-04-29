import { DashboardCharts } from "../components/DashboardCharts";
import type { OverviewPayload } from "../components/DashboardCharts";

function utcIsoDate(d: Date) {
  return d.toISOString().slice(0, 10);
}

function parseIsoDay(day: string): Date {
  return new Date(`${day}T00:00:00.000Z`);
}

type DataRangePayload = {
  min_day: string | null;
  max_day: string | null;
  row_count: number;
};

async function fetchJson<T>(url: string): Promise<{ ok: true; data: T } | { ok: false; status: number; text: string }> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    const text = await response.text();
    return { ok: false, status: response.status, text };
  }
  return { ok: true, data: (await response.json()) as T };
}

function clampLast90DaysUtc(minDay: string, maxDay: string): { start: string; end: string } {
  const minDate = parseIsoDay(minDay);
  const maxDate = parseIsoDay(maxDay);
  const todayUtc = new Date();
  const end = maxDate < todayUtc ? maxDate : todayUtc;
  const start = new Date(end);
  start.setUTCDate(end.getUTCDate() - 89);
  if (start < minDate) {
    start.setTime(minDate.getTime());
  }
  return { start: utcIsoDate(start), end: utcIsoDate(end) };
}

async function getAnalyticsOverview(
  apiUrl: string,
): Promise<{ overview: OverviewPayload | null; error?: string; note?: string }> {
  const end = new Date();
  const start = new Date(end);
  start.setUTCDate(end.getUTCDate() - 89);
  const preferred = { start: utcIsoDate(start), end: utcIsoDate(end) };

  const overviewUrl = (range: { start: string; end: string }) => {
    const url = new URL(`${apiUrl}/analytics/overview`);
    url.searchParams.set("start_date", range.start);
    url.searchParams.set("end_date", range.end);
    url.searchParams.set("top_n", "10");
    return url.toString();
  };

  try {
    const first = await fetchJson<OverviewPayload>(overviewUrl(preferred));
    if (!first.ok) {
      return { overview: null, error: `API error (${first.status}): ${first.text}` };
    }
    if ((first.data.row_count ?? 0) > 0) {
      return { overview: first.data };
    }

    const range = await fetchJson<DataRangePayload>(`${apiUrl}/analytics/data-range`);
    if (!range.ok) {
      return { overview: first.data, error: `API error (${range.status}): ${range.text}` };
    }
    if (!range.data.min_day || !range.data.max_day || range.data.row_count === 0) {
      return {
        overview: first.data,
        error: "BigQuery bronze table looks empty. Run a larger 311 backfill/load before charting.",
      };
    }

    const clamped = clampLast90DaysUtc(range.data.min_day, range.data.max_day);
    const second = await fetchJson<OverviewPayload>(overviewUrl(clamped));
    if (!second.ok) {
      return { overview: first.data, error: `API error (${second.status}): ${second.text}` };
    }

    return {
      overview: second.data,
      note: `No data in the last 90 UTC days. Showing the latest available 90-day window from bronze: ${clamped.start} → ${clamped.end}.`,
    };
  } catch (cause: unknown) {
    const message = cause instanceof Error ? cause.message : String(cause);
    return {
      overview: null,
      error:
        `Could not reach the API at ${apiUrl} (${message}). ` +
        "Start it with: uvicorn api.app.main:app --reload --port 8000 (from the repo root, venv active).",
    };
  }
}

export default async function HomePage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const { overview, error, note } = await getAnalyticsOverview(apiUrl);
  return (
    <main style={{ margin: "2rem auto", maxWidth: 1100, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ margin: "0 0 0.5rem" }}>Tenant Alert</h1>
      <p style={{ margin: "0 0 1.5rem", color: "#475467", maxWidth: "80ch" }}>
        NYC tenant analytics from 311 complaints. This dashboard reads aggregate metrics from the API backed by BigQuery.
      </p>
      {note ? (
        <p style={{ margin: "0 0 1rem", color: "#175cd3", maxWidth: "80ch" }}>{note}</p>
      ) : null}

      <DashboardCharts overview={overview} error={error} />
    </main>
  );
}
