"use client";

import { useEffect, useState } from "react";

type NewsTickerItem = {
  title: string;
  url?: string | null;
  source?: string | null;
  published_at?: string | null;
  borough?: string | null;
};

type NewsTickerPayload = {
  source: string;
  items: NewsTickerItem[];
  ticker_text: string;
};

export function LiveNewsTicker({ fallbackItems }: { fallbackItems: string[] }) {
  const [items, setItems] = useState<NewsTickerItem[]>(
    fallbackItems.map((title) => ({ title, source: "Local Desk", borough: "NYC" })),
  );
  const [source, setSource] = useState("local");

  useEffect(() => {
    const controller = new AbortController();
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    fetch(`${apiUrl}/news/ticker?limit=10`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`ticker api ${response.status}`);
        }
        return response.json() as Promise<NewsTickerPayload>;
      })
      .then((payload) => {
        if (payload.items.length > 0) {
          setItems(payload.items);
          setSource(payload.source);
        }
      })
      .catch(() => {
        setSource("local");
      });

    return () => controller.abort();
  }, []);

  const tickerItems = [...items, ...items.slice(0, 3)];

  return (
    <div className="ticker live-ticker news-ticker" aria-label="Latest NYC public safety headlines">
      <span className="ticker-source">WIRE: {source}</span>
      <div className="ticker-track">
        {tickerItems.map((item, index) => {
          const label = `${item.borough ?? "NYC"}: ${item.title}`;
          return item.url ? (
            <a href={item.url} key={`${item.title}-${index}`} rel="noreferrer" target="_blank">
              {label}
            </a>
          ) : (
            <span key={`${item.title}-${index}`}>{label}</span>
          );
        })}
      </div>
    </div>
  );
}
