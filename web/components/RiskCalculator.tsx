"use client";

import { useMemo, useState } from "react";

type RiskResponse = {
  score: number;
  category: string;
  verdict: string;
  persona: string;
  headline: string;
  borough: string;
  location: string;
  model_version: string;
  latest_data_day?: string | null;
  top_factors: Array<{ label: string; points: number; detail: string }>;
  receipt_lines: Array<{ label: string; value: number }>;
  model_feature_importance?: Array<{ feature: string; importance_weight?: number | null; importance_gain?: number | null }>;
  tip: string;
};

type FormState = {
  location: string;
  time_range: string;
  activity: string;
  awareness: string;
  appearance: string;
  movement: string;
  environment: string;
  group_context: string;
  chaos: string;
};

const OPTIONS = {
  location: [
    ["SOHO", "SoHo"],
    ["Lower Manhattan", "Lower Manhattan"],
    ["Lower East Side", "Lower East Side"],
    ["Williamsburg", "Williamsburg"],
    ["Bushwick", "Bushwick"],
    ["Coney Island", "Coney Island"],
    ["Midtown", "Midtown"],
    ["Astoria", "Astoria"],
    ["Flushing", "Flushing"],
    ["Jamaica", "Jamaica"],
    ["Bronx", "The Bronx"],
    ["Fordham", "Fordham"],
    ["Mott Haven", "Mott Haven"],
    ["Staten Island", "Staten Island"],
  ],
  time_range: [
    ["sun-still-doing-its-job", "Sun's still doing its job"],
    ["after-work-wander", "After work wander"],
    ["late-night-decisions", "Late night decisions"],
    ["you-should-probably-be-home", "You should probably be home"],
  ],
  activity: [
    ["just-walking", "Just walking"],
    ["walking-texting", "Walking + texting (bold)"],
    ["headphones-on", "Noise-canceling headphones ON"],
    ["post-drinks-confidence", "Post-drinks confidence"],
    ["lost-pretending", "Lost but pretending not to be"],
    ["tourist-mode", "Tourist mode activated"],
    ["rideshare-wait", "Waiting for rideshare"],
    ["late-night-food-run", "Late-night food run"],
    ["camera-out", "Camera out, full send"],
    ["shopping-bags", "Shopping bags swinging"],
  ],
  awareness: [
    ["head-on-swivel", "Head on a swivel"],
    ["casually-alert", "Casually alert"],
    ["vibing-not-observing", "Vibing, not observing"],
    ["main-character-energy", "Main character energy"],
  ],
  appearance: [
    ["corporate-clean", "Corporate clean"],
    ["low-key-local", "Low-key local"],
    ["standing-out", "Standing out a little"],
    ["rob-me-outfit", "Rob me outfit"],
  ],
  movement: [
    ["subway-platform", "Subway platform"],
    ["side-street", "Side street"],
    ["busy-avenue", "Busy avenue"],
    ["transit-hub", "Near transit hub"],
    ["tourist-zone", "Tourist-heavy zone"],
  ],
  environment: [
    ["bright-busy", "Bright & busy"],
    ["rainy-empty", "Rainy and empty"],
    ["sketchy-quiet", "Kinda sketchy quiet"],
    ["crowded-chaos", "Crowded chaos"],
  ],
  group_context: [
    ["solo-mission", "Solo mission"],
    ["with-a-friend", "With a friend"],
    ["group-energy", "Group energy"],
    ["lone-wolf-2am", "Lone wolf at 2AM"],
  ],
  chaos: [
    ["responsible-citizen", "Responsible citizen"],
    ["little-reckless", "A little reckless"],
    ["bad-decisions-pending", "Bad decisions pending"],
    ["lets-see-what-happens", "Let's see what happens"],
  ],
} as const;

const INITIAL_FORM: FormState = {
  location: "SOHO",
  time_range: "late-night-decisions",
  activity: "headphones-on",
  awareness: "vibing-not-observing",
  appearance: "standing-out",
  movement: "side-street",
  environment: "sketchy-quiet",
  group_context: "solo-mission",
  chaos: "little-reckless",
};

const FEATURE_MAPPING = [
  ["Location", "Neighborhood-to-borough lookup + latest feature row", "BQML baseline"],
  ["Time Range", "Representative hour bucket", "BQML hour feature + night factor"],
  ["Activity", "Behavior exposure modifier", "Behavior/vibe"],
  ["Awareness", "Attention penalty/discount", "Behavior/vibe"],
  ["Appearance", "Visibility signal weight", "Behavior/vibe"],
  ["Movement", "Street/transit context modifier", "Density context"],
  ["Environment", "Lighting/crowd/weather vibe weight", "Behavior/vibe"],
  ["Solo vs Group", "Group safety/context modifier", "Behavior/vibe"],
  ["Chaos Slider", "Recklessness modifier", "Behavior/vibe"],
];

function optionLabel(name: keyof typeof OPTIONS, value: string) {
  return OPTIONS[name].find(([optionValue]) => optionValue === value)?.[1] ?? value;
}

function OptionGroup({
  label,
  name,
  options,
  value,
  onChange,
}: {
  label: string;
  name: keyof FormState;
  options: readonly (readonly [string, string])[];
  value: string;
  onChange: (name: keyof FormState, value: string) => void;
}) {
  return (
    <fieldset className="risk-fieldset">
      <legend>{label}</legend>
      <div className="risk-chip-grid">
        {options.map(([optionValue, optionLabel]) => (
          <button
            className={value === optionValue ? "risk-chip active" : "risk-chip"}
            key={optionValue}
            onClick={() => onChange(name, optionValue)}
            type="button"
          >
            {optionLabel}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function RiskCalculator() {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [result, setResult] = useState<RiskResponse | null>(null);
  const [status, setStatus] = useState<string>("");
  const maxFactor = useMemo(
    () => Math.max(...(result?.top_factors.map((factor) => Math.abs(factor.points)) ?? [1]), 1),
    [result],
  );
  const selectedReceiptLines = [
    ["LOCATION", form.location],
    ["TIME", optionLabel("time_range", form.time_range)],
    ["ACTIVITY", optionLabel("activity", form.activity)],
    ["AWARENESS", optionLabel("awareness", form.awareness)],
    ["LOOK", optionLabel("appearance", form.appearance)],
    ["MOVEMENT", optionLabel("movement", form.movement)],
    ["OUTSIDE", optionLabel("environment", form.environment)],
    ["CREW", optionLabel("group_context", form.group_context)],
    ["CHAOS", optionLabel("chaos", form.chaos)],
  ];

  const updateField = (name: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [name]: value }));
    setResult(null);
    setStatus("");
  };

  const calculateRisk = async () => {
    setStatus("Printing receipt...");
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiUrl}/crime/risk-score`, {
        body: JSON.stringify(form),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setResult((await response.json()) as RiskResponse);
      setStatus("");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(
        message === "Failed to fetch"
          ? "Could not print fate receipt: API unreachable or blocked by CORS. Restart FastAPI and confirm NEXT_PUBLIC_API_URL points to it."
          : `Could not print fate receipt: ${message}`,
      );
    }
  };

  return (
    <section className="risk-layout">
      <div className="paper-card risk-form-card torn-edge">
        <span className="section-label">Risk Calculator</span>
        <h2>Bodega Receipt of Fate</h2>
        <p className="blotter-note">
          A tongue-in-cheek score powered by a BQML Random Forest baseline plus transparent context
          modifiers. The model predicts historical area/time incident pressure, not personal fate.
        </p>
        <OptionGroup label="Where are you?" name="location" options={OPTIONS.location} value={form.location} onChange={updateField} />
        <OptionGroup label="What time are you out?" name="time_range" options={OPTIONS.time_range} value={form.time_range} onChange={updateField} />
        <OptionGroup label="What are you doing?" name="activity" options={OPTIONS.activity} value={form.activity} onChange={updateField} />
        <OptionGroup label="How aware are you right now?" name="awareness" options={OPTIONS.awareness} value={form.awareness} onChange={updateField} />
        <OptionGroup label="How are you looking?" name="appearance" options={OPTIONS.appearance} value={form.appearance} onChange={updateField} />
        <OptionGroup label="Movement context" name="movement" options={OPTIONS.movement} value={form.movement} onChange={updateField} />
        <OptionGroup label="What's the vibe outside?" name="environment" options={OPTIONS.environment} value={form.environment} onChange={updateField} />
        <OptionGroup label="Who are you with?" name="group_context" options={OPTIONS.group_context} value={form.group_context} onChange={updateField} />
        <OptionGroup label="How chaotic are you feeling?" name="chaos" options={OPTIONS.chaos} value={form.chaos} onChange={updateField} />
        <button className="receipt-button" onClick={calculateRisk} type="button">Print My Fate</button>
        {status ? <p className="blotter-note">{status}</p> : null}
        <div className="feature-map-card">
          <h3>Actual Features vs UI Copy</h3>
          {FEATURE_MAPPING.map(([ui, actual, output]) => (
            <p key={ui}>
              <strong>{ui}</strong>
              <span>{actual}</span>
              <em>{output}</em>
            </p>
          ))}
        </div>
      </div>

      <aside className="receipt-stack">
        <div className="bodega-receipt">
          <h2>NYC Crime Roulette</h2>
          <p className="receipt-rule">-----------------------</p>
          <p>LOCATION: {result?.location.toUpperCase() ?? form.location.toUpperCase()}</p>
          <p>AREA: {result?.borough ?? "PENDING"}</p>
          <p>TIME: {optionLabel("time_range", form.time_range).toUpperCase()}</p>
          <p className="receipt-rule">-----------------------</p>
          <p className="receipt-verdict">YOU SAID:</p>
          {selectedReceiptLines.map(([label, value]) => (
            <p className="receipt-row" key={label}>
              <span>{label}</span>
              <strong>{value.toUpperCase()}</strong>
            </p>
          ))}
          <p className="receipt-rule">-----------------------</p>
          {result ? (
            <>
              {result.receipt_lines.map((line) => (
                <p className="receipt-row" key={line.label}>
                  <span>{line.label}</span>
                  <strong>{line.value >= 0 ? `+${line.value}` : line.value}</strong>
                </p>
              ))}
              <p className="receipt-rule">-----------------------</p>
              <p className="receipt-total">
                <span>TOTAL</span>
                <strong>{result.score}</strong>
              </p>
              <p className="receipt-verdict">VERDICT:</p>
              <blockquote>"{result.verdict}"</blockquote>
              <p className="receipt-persona">You are currently in: {result.persona}</p>
            </>
          ) : (
            <p className="receipt-empty">TOTAL ............ WAITING<br />VERDICT ......... PRESS PRINT</p>
          )}
        </div>

        <div className="paper-card explainability-panel">
          <span className="stamp">Why This Score?</span>
          <h3>{result?.headline ?? "HEADPHONES + MIDNIGHT = BAD IDEAS IN LOWER MANHATTAN"}</h3>
          <div className="handmade-bars">
            {(result?.top_factors ?? []).map((factor) => (
              <div className="handmade-bar" key={factor.label}>
                <span>{factor.label}</span>
                <i style={{ width: `${Math.max(8, (Math.abs(factor.points) / maxFactor) * 100)}%` }} />
                <strong>{factor.points >= 0 ? `+${factor.points}` : factor.points}</strong>
                <p>{factor.detail}</p>
              </div>
            ))}
          </div>
          {result?.model_feature_importance?.length ? (
            <div className="feature-importance-list">
              <h4>BQML Random Forest says these matter most</h4>
              {result.model_feature_importance.map((row) => (
                <p key={row.feature}>
                  <span>{row.feature}</span>
                  <strong>{Number(row.importance_gain ?? row.importance_weight ?? 0).toFixed(2)}</strong>
                </p>
              ))}
            </div>
          ) : null}
          <p className="risk-tip">{result?.tip ?? "Eyes up. Move with purpose."}</p>
        </div>
      </aside>
    </section>
  );
}
