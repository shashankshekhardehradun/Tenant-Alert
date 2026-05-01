"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { importLibrary, setOptions } from "@googlemaps/js-api-loader";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { HeatmapLayer, HexagonLayer } from "@deck.gl/aggregation-layers";
import { ScatterplotLayer } from "@deck.gl/layers";

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

type ViewMode = "density" | "incidents" | "heat";
type HoverInfo = { x: number; y: number; point: CrimeMapPoint } | null;

const LAW_CATEGORY_COLORS: Record<string, [number, number, number]> = {
  FELONY: [180, 35, 24],
  MISDEMEANOR: [247, 144, 9],
  VIOLATION: [21, 112, 239],
};

const BOROUGH_CAMERA: Record<string, google.maps.LatLngLiteral> = {
  BRONX: { lat: 40.8448, lng: -73.8648 },
  BROOKLYN: { lat: 40.6501, lng: -73.9496 },
  MANHATTAN: { lat: 40.7831, lng: -73.9712 },
  QUEENS: { lat: 40.7282, lng: -73.7949 },
  "STATEN ISLAND": { lat: 40.5795, lng: -74.1502 },
};

const ALL_SEVERITIES = ["FELONY", "MISDEMEANOR", "VIOLATION"];

function sourceRecordUrl(point: CrimeMapPoint) {
  const dataset = point.source_dataset === "ytd" ? "5uac-w243" : "qgea-i56i";
  return `https://data.cityofnewyork.us/resource/${dataset}.json?cmplnt_num=${encodeURIComponent(point.complaint_id)}`;
}

function googleMapsUrl(point: CrimeMapPoint) {
  return `https://www.google.com/maps/search/?api=1&query=${point.latitude},${point.longitude}`;
}

function streetViewUrl(point: CrimeMapPoint) {
  return `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${point.latitude},${point.longitude}`;
}

function colorForSeverity(category: string): [number, number, number] {
  return LAW_CATEGORY_COLORS[category?.toUpperCase()] ?? [102, 112, 133];
}

function formatCategory(category: string) {
  return category.charAt(0).toUpperCase() + category.slice(1).toLowerCase();
}

export function CrimeMap({ points }: { points: CrimeMapPoint[] }) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const mapId = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const overlayRef = useRef<GoogleMapsOverlay | null>(null);
  const [enabledSeverities, setEnabledSeverities] = useState(() => new Set(ALL_SEVERITIES));
  const [viewMode, setViewMode] = useState<ViewMode>("density");
  const [hoverInfo, setHoverInfo] = useState<HoverInfo>(null);
  const [selectedPoint, setSelectedPoint] = useState<CrimeMapPoint | null>(null);
  const [status, setStatus] = useState(apiKey ? "Loading Google Maps..." : "Google Maps API key is not configured.");

  const filteredPoints = useMemo(
    () => points.filter((point) => enabledSeverities.has(point.law_category?.toUpperCase())),
    [enabledSeverities, points],
  );

  useEffect(() => {
    if (!apiKey || !containerRef.current || mapRef.current) {
      return;
    }

    let cancelled = false;
    setOptions({
      key: apiKey,
      v: "weekly",
      mapIds: mapId ? [mapId] : undefined,
    });

    importLibrary("maps")
      .then(() => {
        if (cancelled || !containerRef.current) {
          return;
        }

        const map = new google.maps.Map(containerRef.current, {
          center: { lat: 40.72, lng: -73.95 },
          zoom: 10.4,
          mapId,
          tilt: 67.5,
          heading: 28,
          gestureHandling: "greedy",
          clickableIcons: true,
          fullscreenControl: true,
          mapTypeControl: false,
          streetViewControl: true,
        });
        const overlay = new GoogleMapsOverlay({ layers: [] });
        overlay.setMap(map);
        mapRef.current = map;
        overlayRef.current = overlay;
        setStatus("");
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        setStatus(`Could not load Google Maps: ${message}`);
      });

    return () => {
      cancelled = true;
      overlayRef.current?.finalize();
      overlayRef.current = null;
      mapRef.current = null;
    };
  }, [apiKey, mapId]);

  useEffect(() => {
    if (!overlayRef.current) {
      return;
    }

    const layers = [];
    if (viewMode === "density") {
      layers.push(
        new HexagonLayer<CrimeMapPoint>({
          id: "crime-hexagons",
          data: filteredPoints,
          getPosition: (point) => [point.longitude, point.latitude],
          radius: 260,
          extruded: true,
          elevationScale: 42,
          elevationRange: [0, 3500],
          pickable: true,
          coverage: 0.82,
          colorRange: [
            [21, 112, 239, 120],
            [124, 58, 237, 150],
            [247, 144, 9, 175],
            [196, 50, 10, 205],
            [180, 35, 24, 235],
          ],
          onHover: (info) => {
            if (info.object) {
              setHoverInfo(null);
            }
            return false;
          },
        }),
      );
    }

    if (viewMode === "heat") {
      layers.push(
        new HeatmapLayer<CrimeMapPoint>({
          id: "crime-heat-glow",
          data: filteredPoints,
          getPosition: (point) => [point.longitude, point.latitude],
          getWeight: (point) => (point.law_category === "FELONY" ? 3 : point.law_category === "MISDEMEANOR" ? 2 : 1),
          radiusPixels: 55,
          intensity: 1.2,
          threshold: 0.08,
        }),
      );
    }

    if (viewMode === "incidents" || viewMode === "density") {
      layers.push(
        new ScatterplotLayer<CrimeMapPoint>({
          id: "crime-incidents",
          data: filteredPoints,
          getPosition: (point) => [point.longitude, point.latitude],
          getFillColor: (point) => [...colorForSeverity(point.law_category), 215],
          getLineColor: [255, 255, 255, 220],
          getLineWidth: 1.2,
          getRadius: (point) => (point.law_category === "FELONY" ? 55 : point.law_category === "MISDEMEANOR" ? 42 : 32),
          radiusUnits: "meters",
          pickable: true,
          stroked: true,
          filled: true,
          onHover: (info) => {
            setHoverInfo(info.object ? { x: info.x, y: info.y, point: info.object } : null);
          },
          onClick: (info) => {
            if (info.object) {
              setSelectedPoint(info.object);
            }
          },
        }),
      );
    }

    overlayRef.current.setProps({ layers });
  }, [filteredPoints, viewMode]);

  const toggleSeverity = (severity: string) => {
    setEnabledSeverities((current) => {
      const next = new Set(current);
      if (next.has(severity)) {
        next.delete(severity);
      } else {
        next.add(severity);
      }
      return next.size === 0 ? current : next;
    });
  };

  const resetCamera = () => {
    mapRef.current?.moveCamera({
      center: { lat: 40.72, lng: -73.95 },
      zoom: 10.4,
      tilt: 67.5,
      heading: 28,
    });
  };

  const tiltCamera = () => {
    mapRef.current?.moveCamera({
      tilt: 67.5,
      heading: ((mapRef.current.getHeading() ?? 0) + 55) % 360,
      zoom: Math.max(mapRef.current.getZoom() ?? 10.4, 11),
    });
  };

  const tourBoroughs = () => {
    const boroughs = Object.values(BOROUGH_CAMERA);
    boroughs.forEach((center, index) => {
      window.setTimeout(() => {
        mapRef.current?.moveCamera({
          center,
          zoom: 12,
          tilt: 67.5,
          heading: index * 42,
        });
      }, index * 950);
    });
  };

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.75rem",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {ALL_SEVERITIES.map((severity) => (
            <button
              key={severity}
              onClick={() => toggleSeverity(severity)}
              style={{
                background: enabledSeverities.has(severity) ? `rgb(${colorForSeverity(severity).join(",")})` : "#f2f4f7",
                border: "1px solid #d0d5dd",
                borderRadius: 999,
                color: enabledSeverities.has(severity) ? "white" : "#344054",
                cursor: "pointer",
                fontWeight: 700,
                padding: "0.45rem 0.75rem",
              }}
              type="button"
            >
              {formatCategory(severity)}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {(["density", "incidents", "heat"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              style={{
                background: viewMode === mode ? "#111827" : "white",
                border: "1px solid #d0d5dd",
                borderRadius: 8,
                color: viewMode === mode ? "white" : "#344054",
                cursor: "pointer",
                padding: "0.45rem 0.7rem",
              }}
              type="button"
            >
              {mode === "density" ? "3D Density" : mode === "incidents" ? "Incidents" : "Heat"}
            </button>
          ))}
          <button onClick={resetCamera} type="button">Reset NYC</button>
          <button onClick={tiltCamera} type="button">Tilt 3D</button>
          <button onClick={tourBoroughs} type="button">Borough Tour</button>
        </div>
      </div>

      <div
        style={{
          border: "1px solid #d0d5dd",
          borderRadius: 18,
          boxShadow: "0 20px 60px rgba(16, 24, 40, 0.16)",
          height: 680,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
        {status ? (
          <div
            style={{
              background: "rgba(255, 255, 255, 0.92)",
              display: "grid",
              inset: 0,
              padding: "2rem",
              placeItems: "center",
              position: "absolute",
              textAlign: "center",
            }}
          >
            <div>
              <h3 style={{ margin: "0 0 0.5rem" }}>Google Maps setup needed</h3>
              <p style={{ color: "#475467", margin: 0, maxWidth: 560 }}>{status}</p>
            </div>
          </div>
        ) : null}
        {hoverInfo ? (
          <div
            style={{
              background: "rgba(17, 24, 39, 0.92)",
              border: "1px solid rgba(255,255,255,0.16)",
              borderRadius: 12,
              boxShadow: "0 16px 48px rgba(0,0,0,0.28)",
              color: "white",
              left: hoverInfo.x + 16,
              maxWidth: 320,
              padding: "0.75rem",
              pointerEvents: "none",
              position: "absolute",
              top: hoverInfo.y + 16,
              zIndex: 2,
            }}
          >
            <strong>{hoverInfo.point.offense_description}</strong>
            <p style={{ margin: "0.35rem 0 0" }}>
              {hoverInfo.point.complaint_date} · {hoverInfo.point.borough} · {hoverInfo.point.law_category}
            </p>
            {hoverInfo.point.premise_type ? <p style={{ margin: "0.25rem 0 0" }}>{hoverInfo.point.premise_type}</p> : null}
          </div>
        ) : null}
        {selectedPoint ? (
          <aside
            style={{
              background: "rgba(255,255,255,0.96)",
              border: "1px solid #eaecf0",
              borderRadius: 16,
              boxShadow: "0 18px 56px rgba(16,24,40,0.22)",
              maxWidth: 360,
              padding: "1rem",
              position: "absolute",
              right: 16,
              top: 16,
              zIndex: 3,
            }}
          >
            <button
              aria-label="Close incident details"
              onClick={() => setSelectedPoint(null)}
              style={{ background: "transparent", border: 0, cursor: "pointer", float: "right", fontSize: 18 }}
              type="button"
            >
              x
            </button>
            <h3 style={{ margin: "0 1.5rem 0.5rem 0" }}>{selectedPoint.offense_description}</h3>
            <p style={{ color: "#475467", margin: "0 0 0.75rem" }}>
              {selectedPoint.complaint_date} · {selectedPoint.borough} · {selectedPoint.law_category}
            </p>
            {selectedPoint.premise_type ? <p><strong>Premise:</strong> {selectedPoint.premise_type}</p> : null}
            <div style={{ display: "grid", gap: "0.45rem" }}>
              <a href={googleMapsUrl(selectedPoint)} rel="noreferrer" target="_blank">Open in Google Maps</a>
              <a href={streetViewUrl(selectedPoint)} rel="noreferrer" target="_blank">Open Street View</a>
              <a href={sourceRecordUrl(selectedPoint)} rel="noreferrer" target="_blank">NYC Open Data source record</a>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
