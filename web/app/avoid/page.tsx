import Link from "next/link";

import { LiveNewsTicker } from "../../components/LiveNewsTicker";

type AvoidabilityItem = {
  borough: string;
  latest_signal_day?: string | null;
  latest_crime_day?: string | null;
  latest_mta_day?: string | null;
  street_signal_count_24h?: number | null;
  street_signal_count_7d?: number | null;
  avg_spike_ratio?: number | null;
  open_ratio?: number | null;
  street_signal_score?: number | null;
  crime_count_90d?: number | null;
  crime_pressure_score?: number | null;
  late_night_pressure_score?: number | null;
  transit_chaos_score?: number | null;
  transit_alert_count?: number | null;
  affected_route_count?: number | null;
  avoidability_score?: number | null;
  avoidability_band?: string | null;
  top_signal_category?: string | null;
  top_signal_count?: number | null;
  top_signal_spike_ratio?: number | null;
  top_complaint_type?: string | null;
  top_descriptor?: string | null;
  top_incident_zip?: string | null;
  top_transit_mode?: string | null;
  top_transit_route?: string | null;
  top_transit_alert_type?: string | null;
  top_transit_header?: string | null;
  avoid_if?: string | null;
  stamp_label?: string | null;
  advice_copy?: string | null;
};

type AvoidabilityPayload = {
  source: string;
  items: AvoidabilityItem[];
  count: number;
};

const FALLBACK_ITEMS: AvoidabilityItem[] = [
  {
    borough: "NYC",
    avoidability_score: 0,
    avoidability_band: "Waiting on the wire",
    avoid_if: "Avoid if you hate placeholder copy",
    stamp_label: "DAG WARMING UP",
    advice_copy:
      "The avoidability desk is waiting for the first 311 street-signal rollup. Run the daily refresh job to print the watchlist.",
  },
];

function formatNumber(value?: number | null) {
  return (value ?? 0).toLocaleString();
}

function formatPct(value?: number | null) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

async function getAvoidability(): Promise<{ payload: AvoidabilityPayload; error?: string }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiUrl}/avoidability/rankings?limit=10`, { cache: "no-store" });
    if (!response.ok) {
      return {
        payload: { source: "fallback", items: FALLBACK_ITEMS, count: FALLBACK_ITEMS.length },
        error: `Avoidability API error (${response.status})`,
      };
    }
    const payload = (await response.json()) as AvoidabilityPayload;
    return {
      payload:
        payload.items.length > 0
          ? payload
          : { source: "fallback", items: FALLBACK_ITEMS, count: FALLBACK_ITEMS.length },
    };
  } catch (cause: unknown) {
    const message = cause instanceof Error ? cause.message : String(cause);
    return {
      payload: { source: "fallback", items: FALLBACK_ITEMS, count: FALLBACK_ITEMS.length },
      error: `Could not reach avoidability API: ${message}`,
    };
  }
}

export default async function AvoidPage() {
  const { payload, error } = await getAvoidability();
  const top = payload.items[0];

  return (
    <main className="bulletin-shell avoid-page">
      <div className="bulletin-topline">
        <span>Bad Idea Desk</span>
        <span>311 street signals + historical pressure</span>
        <span>Daily watchlist</span>
      </div>
      <header className="masthead">
        <div>
          <p className="kicker">Tonight's Friend Text</p>
          <h1 className="masthead-title">I Would Avoid</h1>
          <p className="masthead-deck">
            A tongue-in-cheek daily watchlist blending fresh 311 street-signal complaints with
            historical NYPD pressure. Not a safety advisory. More like your most dramatic friend
            checking the block before you leave.
          </p>
        </div>
        <aside className="price-box" aria-label="Avoidability leader">
          <span>Top vibe</span>
          <strong>{top?.avoidability_score ?? 0}</strong>
          <span>{top?.borough ?? "NYC"}</span>
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
        "Not every bad idea is a crime.",
        "Sometimes the train is cursed and the block is loud.",
        "Street-vibe desk is open.",
      ]} />
      {error ? (
        <p className="paper-card blotter-note" style={{ margin: "1rem 0 0", padding: "0.75rem" }}>{error}</p>
      ) : null}

      <div className="content-stack avoid-layout">
        <section className="paper-card torn-edge avoid-hero">
          <span className="section-label">Filed Window</span>
          <h2>I would avoid if...</h2>
          <p>
            Latest 311 street-signal day: <strong>{top?.latest_signal_day ?? "pending"}</strong> ·
            latest NYPD complaint day: <strong>{top?.latest_crime_day ?? "pending"}</strong> ·
            latest MTA alert pull: <strong>{top?.latest_mta_day ?? "pending"}</strong> ·
            source: <strong>{payload.source}</strong>
          </p>
        </section>

        <section className="avoid-card-grid">
          {payload.items.map((item, index) => (
            <article className="paper-card avoid-card" key={`${item.borough}-${index}`}>
              <div className="avoid-card-header">
                <span className="stamp">{item.stamp_label ?? "FRIEND TEXT"}</span>
                <strong>#{index + 1}</strong>
              </div>
              <h2>{item.borough}</h2>
              <p className="avoid-score">
                <span>{item.avoidability_band ?? "Questionable vibes"}</span>
                <strong>{item.avoidability_score ?? 0}</strong>
              </p>
              <p className="mini-headline">{item.avoid_if ?? "Avoid if the vibes are off"}</p>
              <p>{item.advice_copy}</p>
              <div className="avoid-stat-grid">
                <div>
                  <span>Street signals</span>
                  <strong>{formatNumber(item.street_signal_count_24h)}</strong>
                  <em>last day</em>
                </div>
                <div>
                  <span>7-day noise</span>
                  <strong>{formatNumber(item.street_signal_count_7d)}</strong>
                  <em>all signals</em>
                </div>
                <div>
                  <span>Transit alerts</span>
                  <strong>{formatNumber(item.transit_alert_count)}</strong>
                  <em>{formatNumber(item.affected_route_count)} routes</em>
                </div>
              </div>
              <div className="classified-item">
                Top signal: {item.top_complaint_type ?? item.top_signal_category ?? "street signal"}
                {item.top_descriptor ? ` · ${item.top_descriptor}` : ""}
                {item.top_incident_zip ? ` · ZIP ${item.top_incident_zip}` : ""}
              </div>
              {item.top_transit_header ? (
                <div className="classified-item">
                  Transit chaos: {item.top_transit_mode ? `${item.top_transit_mode.toUpperCase()} ` : ""}
                  {item.top_transit_route ? `[${item.top_transit_route}] ` : ""}
                  {item.top_transit_alert_type ?? "Service alert"} · {item.top_transit_header}
                </div>
              ) : null}
            </article>
          ))}
        </section>

        <section className="paper-card avoid-explainer">
          <span className="section-label">Why This Exists</span>
          <h3>Crime data is the reputation. 311 is the group chat.</h3>
          <p>
            NYPD complaint data can lag, so the watchlist uses it as a historical pressure baseline
            and lets daily 311 street signals provide freshness: noise, parking chaos, dark lights,
            grime, street conditions, and public-space calls.
          </p>
        </section>
      </div>
    </main>
  );
}
