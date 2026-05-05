import type { CrimeOverviewPayload } from "../components/CrimeDashboard";

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

type CrimeOverviewOptions = {
  borough?: string;
  latestDayOnly?: boolean;
  mapLimit?: number;
};

function buildOverviewUrl(
  apiUrl: string,
  range: { start: string; end: string },
  options: CrimeOverviewOptions,
): string {
  const url = new URL(`${apiUrl}/crime/overview`);
  url.searchParams.set("start_date", range.start);
  url.searchParams.set("end_date", range.end);
  url.searchParams.set("top_n", "10");
  url.searchParams.set("map_limit", String(options.mapLimit ?? 2000));
  if (options.borough) {
    url.searchParams.set("borough", options.borough);
  }
  return url.toString();
}

/** Overlay `top_offenses` from a single-day slice (latest filing day) for a populated blotter chart. */
async function mergeLatestDayTopOffenses(
  apiUrl: string,
  overview: CrimeOverviewPayload,
  maxDay: string,
  options: CrimeOverviewOptions,
): Promise<CrimeOverviewPayload> {
  const dayUrl = buildOverviewUrl(apiUrl, { start: maxDay, end: maxDay }, options);
  const latest = await fetchJson<CrimeOverviewPayload>(dayUrl);
  if (!latest.ok || !(latest.data.top_offenses?.length ?? 0)) {
    return overview;
  }
  return { ...overview, top_offenses: latest.data.top_offenses ?? overview.top_offenses };
}

export async function getCrimeOverview(options: CrimeOverviewOptions = {}): Promise<{
  overview: CrimeOverviewPayload | null;
  error?: string;
  note?: string;
}> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const end = new Date();
  const start = new Date(end);
  start.setUTCDate(end.getUTCDate() - 89);
  const preferred = { start: utcIsoDate(start), end: utcIsoDate(end) };

  try {
    if (options.latestDayOnly) {
      const range = await fetchJson<DataRangePayload>(`${apiUrl}/crime/data-range`);
      if (!range.ok) {
        return { overview: null, error: `API error (${range.status}): ${range.text}` };
      }
      if (!range.data.max_day || range.data.row_count === 0) {
        return {
          overview: null,
          error: "BigQuery crime marts look empty. Ingest NYPD complaints and run dbt before charting.",
        };
      }
      const latest = { start: range.data.max_day, end: range.data.max_day };
      const latestResponse = await fetchJson<CrimeOverviewPayload>(
        buildOverviewUrl(apiUrl, latest, options),
      );
      if (!latestResponse.ok) {
        return { overview: null, error: `API error (${latestResponse.status}): ${latestResponse.text}` };
      }
      return {
        overview: latestResponse.data,
        note: `Map room is showing the latest available filing day only: ${range.data.max_day}.`,
      };
    }

    const range = await fetchJson<DataRangePayload>(`${apiUrl}/crime/data-range`);

    let windowRange = preferred;
    if (range.ok && range.data.min_day && range.data.max_day && range.data.row_count > 0) {
      windowRange = clampLast90DaysUtc(range.data.min_day, range.data.max_day);
    }

    const main = await fetchJson<CrimeOverviewPayload>(buildOverviewUrl(apiUrl, windowRange, options));
    if (!main.ok) {
      return { overview: null, error: `API error (${main.status}): ${main.text}` };
    }

    let overview = main.data;
    let note: string | undefined;

    if (range.ok && range.data.max_day && range.data.row_count > 0) {
      overview = await mergeLatestDayTopOffenses(apiUrl, overview, range.data.max_day, options);
      note = `Charts use the latest ${windowRange.end} filing window in BigQuery; top offenses use the latest day (${range.data.max_day}).`;
    }

    if ((overview.row_count ?? 0) > 0) {
      return { overview, note };
    }

    if (!range.ok) {
      return { overview, error: `API error (${range.status}): ${range.text}` };
    }
    if (!range.data.min_day || !range.data.max_day || range.data.row_count === 0) {
      return {
        overview,
        error: "BigQuery crime marts look empty. Ingest NYPD complaints and run dbt before charting.",
      };
    }

    const clamped = clampLast90DaysUtc(range.data.min_day, range.data.max_day);
    const second = await fetchJson<CrimeOverviewPayload>(buildOverviewUrl(apiUrl, clamped, options));
    if (!second.ok) {
      return { overview, error: `API error (${second.status}): ${second.text}` };
    }

    let overview2 = second.data;
    if (range.data.max_day) {
      overview2 = await mergeLatestDayTopOffenses(apiUrl, overview2, range.data.max_day, options);
    }

    return {
      overview: overview2,
      note: `No crime data in the last 90 UTC days. Showing the latest available window: ${clamped.start} -> ${clamped.end}. Top offenses use latest day (${range.data.max_day}).`,
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
