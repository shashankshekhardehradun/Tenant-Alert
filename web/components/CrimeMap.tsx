"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { importLibrary, setOptions } from "@googlemaps/js-api-loader";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { HexagonLayer } from "@deck.gl/aggregation-layers";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";

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

type ViewMode = "density" | "incidents";
type HoverInfo = { x: number; y: number; point: CrimeMapPoint } | null;
type OffenseGroup = "ROBBERY" | "THEFT" | "FORGERY" | "ASSAULT" | "DRUGS" | "OTHER";

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

const OFFENSE_MARKERS: Record<OffenseGroup, { color: [number, number, number]; label: string; symbol: string }> = {
  ROBBERY: { color: [255, 32, 110], label: "Robbery", symbol: "R" },
  THEFT: { color: [255, 230, 0], label: "Theft", symbol: "T" },
  FORGERY: { color: [0, 245, 255], label: "Forgery", symbol: "F" },
  ASSAULT: { color: [255, 74, 28], label: "Assault", symbol: "A" },
  DRUGS: { color: [57, 255, 20], label: "Drugs", symbol: "D" },
  OTHER: { color: [190, 119, 255], label: "Other", symbol: "O" },
};

const BOROUGH_OUTLINES: Array<{ name: string; path: google.maps.LatLngLiteral[] }> = [
  {
    name: "MANHATTAN",
    path: [
      { lat: 40.701, lng: -74.019 },
      { lat: 40.882, lng: -73.933 },
      { lat: 40.873, lng: -73.907 },
      { lat: 40.704, lng: -73.969 },
    ],
  },
  {
    name: "BRONX",
    path: [
      { lat: 40.786, lng: -73.933 },
      { lat: 40.918, lng: -73.933 },
      { lat: 40.914, lng: -73.765 },
      { lat: 40.800, lng: -73.765 },
      { lat: 40.785, lng: -73.865 },
    ],
  },
  {
    name: "QUEENS",
    path: [
      { lat: 40.787, lng: -73.962 },
      { lat: 40.808, lng: -73.700 },
      { lat: 40.578, lng: -73.713 },
      { lat: 40.545, lng: -73.950 },
      { lat: 40.642, lng: -73.962 },
    ],
  },
  {
    name: "BROOKLYN",
    path: [
      { lat: 40.739, lng: -74.043 },
      { lat: 40.735, lng: -73.846 },
      { lat: 40.570, lng: -73.835 },
      { lat: 40.565, lng: -74.040 },
      { lat: 40.646, lng: -74.052 },
    ],
  },
  {
    name: "STATEN ISLAND",
    path: [
      { lat: 40.651, lng: -74.260 },
      { lat: 40.643, lng: -74.052 },
      { lat: 40.477, lng: -74.050 },
      { lat: 40.477, lng: -74.260 },
    ],
  },
];

const BOROUGH_LABELS = [
  { name: "MANHATTAN", position: [-73.975, 40.768] as [number, number] },
  { name: "THE BRONX", position: [-73.875, 40.848] as [number, number] },
  { name: "QUEENS", position: [-73.815, 40.708] as [number, number] },
  { name: "BROOKLYN", position: [-73.945, 40.64] as [number, number] },
  { name: "STATEN ISLAND", position: [-74.155, 40.585] as [number, number] },
];

const nycTabloidMapStyle: google.maps.MapTypeStyle[] = [
  { featureType: "all", elementType: "geometry", stylers: [{ color: "#1b1511" }] },
  { featureType: "all", elementType: "labels.text.fill", stylers: [{ color: "#e8d8b5" }] },
  { featureType: "all", elementType: "labels.text.stroke", stylers: [{ color: "#120d0a" }, { weight: 3 }] },
  { featureType: "administrative", elementType: "geometry.stroke", stylers: [{ color: "#8f2d24" }, { weight: 1.4 }] },
  { featureType: "administrative.neighborhood", elementType: "labels.text.fill", stylers: [{ color: "#f4e6bf" }] },
  { featureType: "poi", elementType: "all", stylers: [{ visibility: "off" }] },
  { featureType: "transit", elementType: "geometry", stylers: [{ color: "#5c4a33" }] },
  { featureType: "transit.station", elementType: "labels.icon", stylers: [{ visibility: "off" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#33261c" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#0e0a07" }] },
  { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#bca77b" }] },
  { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#5a241d" }] },
  { featureType: "road.highway", elementType: "geometry.stroke", stylers: [{ color: "#d39a38" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#101820" }] },
  { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#6f8790" }] },
  { featureType: "landscape.man_made", elementType: "geometry", stylers: [{ color: "#211812" }] },
  { featureType: "landscape.natural", elementType: "geometry", stylers: [{ color: "#1a1a12" }] },
  { featureType: "poi.park", elementType: "geometry", stylers: [{ color: "#26301d" }] },
];

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

function offenseGroup(point: CrimeMapPoint): OffenseGroup {
  const offense = point.offense_description.toUpperCase();
  if (offense.includes("ROBBERY")) return "ROBBERY";
  if (offense.includes("FORGERY") || offense.includes("FRAUD")) return "FORGERY";
  if (offense.includes("LARCENY") || offense.includes("THEFT") || offense.includes("BURGLARY") || offense.includes("STOLEN")) {
    return "THEFT";
  }
  if (offense.includes("ASSAULT")) return "ASSAULT";
  if (offense.includes("DRUG") || offense.includes("CONTROLLED SUBSTANCE")) return "DRUGS";
  return "OTHER";
}

function colorForOffense(point: CrimeMapPoint): [number, number, number] {
  return OFFENSE_MARKERS[offenseGroup(point)].color;
}

export function CrimeMap({ points }: { points: CrimeMapPoint[] }) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const mapId = process.env.NEXT_PUBLIC_GOOGLE_MAP_ID;
  const useCloudMapStyle = process.env.NEXT_PUBLIC_USE_GOOGLE_MAP_ID === "true";
  const activeMapId = useCloudMapStyle ? mapId : undefined;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const overlayRef = useRef<GoogleMapsOverlay | null>(null);
  const boroughPolygonsRef = useRef<google.maps.Polygon[]>([]);
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
      mapIds: activeMapId ? [activeMapId] : undefined,
    });

    importLibrary("maps")
      .then(() => {
        if (cancelled || !containerRef.current) {
          return;
        }

        const map = new google.maps.Map(containerRef.current, {
          center: { lat: 40.705, lng: -73.94 },
          zoom: 10.7,
          mapId: activeMapId,
          styles: activeMapId ? undefined : nycTabloidMapStyle,
          backgroundColor: "#120d0a",
          mapTypeId: google.maps.MapTypeId.SATELLITE,
          tilt: 67.5,
          heading: 28,
          gestureHandling: "greedy",
          clickableIcons: false,
          fullscreenControl: false,
          mapTypeControl: false,
          streetViewControl: false,
          zoomControl: false,
          rotateControl: false,
          scaleControl: false,
          keyboardShortcuts: false,
        });
        const overlay = new GoogleMapsOverlay({ layers: [] });
        overlay.setMap(map);
        boroughPolygonsRef.current = BOROUGH_OUTLINES.map(
          ({ path }) =>
            new google.maps.Polygon({
              clickable: false,
              fillColor: "#ffee58",
              fillOpacity: 0.035,
              map,
              paths: path,
              strokeColor: "#ffee58",
              strokeOpacity: 0.95,
              strokeWeight: 3.5,
              zIndex: 2,
            }),
        );
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
      boroughPolygonsRef.current.forEach((polygon) => polygon.setMap(null));
      boroughPolygonsRef.current = [];
      overlayRef.current?.finalize();
      overlayRef.current = null;
      mapRef.current = null;
    };
  }, [activeMapId, apiKey]);

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
          radius: 220,
          extruded: true,
          elevationScale: 58,
          elevationRange: [0, 4600],
          pickable: true,
          coverage: 0.72,
          colorRange: [
            [44, 255, 194, 105],
            [255, 230, 0, 145],
            [255, 137, 6, 185],
            [255, 32, 110, 225],
            [255, 255, 255, 245],
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

    if (viewMode === "incidents" || viewMode === "density") {
      layers.push(
        new ScatterplotLayer<CrimeMapPoint>({
          id: "crime-neon-halos",
          data: filteredPoints,
          getPosition: (point) => [point.longitude, point.latitude],
          getFillColor: (point) => [...colorForOffense(point), 70],
          getLineColor: (point) => [...colorForOffense(point), 210],
          getLineWidth: 8,
          getRadius: (point) => {
            const group = offenseGroup(point);
            if (group === "ROBBERY" || group === "ASSAULT") return 120;
            if (group === "THEFT" || group === "FORGERY") return 96;
            return 78;
          },
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
        new ScatterplotLayer<CrimeMapPoint>({
          id: "crime-neon-cores",
          data: filteredPoints,
          getPosition: (point) => [point.longitude, point.latitude],
          getFillColor: (point) => [...colorForOffense(point), 245],
          getLineColor: [255, 255, 255, 255],
          getLineWidth: 2.5,
          getRadius: (point) => {
            const group = offenseGroup(point);
            if (group === "ROBBERY" || group === "ASSAULT") return 46;
            if (group === "THEFT" || group === "FORGERY") return 38;
            return 32;
          },
          radiusUnits: "meters",
          pickable: false,
          stroked: true,
          filled: true,
        }),
        new TextLayer<CrimeMapPoint>({
          id: "crime-offense-glyphs",
          data: filteredPoints,
          getPosition: (point) => [point.longitude, point.latitude],
          getText: (point) => OFFENSE_MARKERS[offenseGroup(point)].symbol,
          getColor: [5, 5, 5, 255],
          getSize: 13,
          getTextAnchor: "middle",
          getAlignmentBaseline: "center",
          fontFamily: "Impact, Arial Narrow, sans-serif",
          fontWeight: "bold",
          pickable: false,
          sizeUnits: "pixels",
        }),
      );
    }

    layers.push(
      new TextLayer<(typeof BOROUGH_LABELS)[number]>({
        id: "borough-map-labels",
        data: BOROUGH_LABELS,
        getPosition: (label) => label.position,
        getText: (label) => label.name,
        getColor: [248, 237, 207, 235],
        getSize: 18,
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
        fontFamily: "Impact, Arial Narrow, sans-serif",
        fontWeight: "bold",
        outlineColor: [0, 0, 0, 255],
        outlineWidth: 4,
        pickable: false,
        sizeUnits: "pixels",
      }),
    );

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

  const offenseCounts = filteredPoints.reduce<Record<OffenseGroup, number>>(
    (counts, point) => {
      const group = offenseGroup(point);
      counts[group] += 1;
      return counts;
    },
    { ROBBERY: 0, THEFT: 0, FORGERY: 0, ASSAULT: 0, DRUGS: 0, OTHER: 0 },
  );
  const topOffenseGroup = Object.entries(offenseCounts).sort((a, b) => b[1] - a[1])[0] as [OffenseGroup, number];
  const felonyCount = filteredPoints.filter((point) => point.law_category === "FELONY").length;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div
        className="map-frame"
        style={{
          height: 740,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div ref={containerRef} style={{ height: "100%", width: "100%" }} />
        <aside className="map-control-panel">
          <p className="map-panel-kicker">Layer Control</p>
          {ALL_SEVERITIES.map((severity) => (
            <label key={severity} className="map-check-row">
              <input
                checked={enabledSeverities.has(severity)}
                onChange={() => toggleSeverity(severity)}
                type="checkbox"
              />
              <span>{formatCategory(severity)}</span>
            </label>
          ))}
          <p className="map-panel-kicker">Time View</p>
          {(["density", "incidents"] as const).map((mode) => (
            <button
              className={viewMode === mode ? "map-pill active" : "map-pill"}
              key={mode}
              onClick={() => setViewMode(mode)}
              type="button"
            >
              {mode === "density" ? "3D Hot Columns" : "Neon Incidents"}
            </button>
          ))}
          <p className="map-panel-kicker">Camera</p>
          <button className="map-pill" onClick={resetCamera} type="button">Reset NYC</button>
          <button className="map-pill" onClick={tiltCamera} type="button">Tilt 3D</button>
          <button className="map-pill" onClick={tourBoroughs} type="button">Borough Tour</button>
        </aside>
        <aside className="map-stat-stack">
          <div>
            <span>Incidents Live</span>
            <strong>{filteredPoints.length.toLocaleString()}</strong>
          </div>
          <div>
            <span>Hot Layer</span>
            <strong>{viewMode === "density" ? "3D" : "PINS"}</strong>
          </div>
          <div>
            <span>Top Type</span>
            <strong>{OFFENSE_MARKERS[topOffenseGroup[0]].label}</strong>
          </div>
          <div>
            <span>Felony Sample</span>
            <strong>{felonyCount.toLocaleString()}</strong>
          </div>
        </aside>
        <div className="map-risk-legend">
          <span><i style={{ background: "#2cffc2" }} /> Low Risk</span>
          <span><i style={{ background: "#ffe600" }} /> Medium Risk</span>
          <span><i style={{ background: "#ff5f1f" }} /> High Risk</span>
          <span><i style={{ background: "#ff206e" }} /> Very High Risk</span>
        </div>
        <div className="map-offense-legend">
          {Object.entries(OFFENSE_MARKERS).map(([key, marker]) => (
            <span key={key}>
              <i style={{ background: `rgb(${marker.color.join(",")})` }}>{marker.symbol}</i>
              {marker.label}
            </span>
          ))}
        </div>
        <div className="map-headline-strip">
          <strong>Latest Headline</strong>
          <span>
            {OFFENSE_MARKERS[topOffenseGroup[0]].label} markers dominate the visible sample with {topOffenseGroup[1].toLocaleString()} mapped reports.
          </span>
          <button onClick={() => setSelectedPoint(filteredPoints[0] ?? null)} type="button">View Blotter</button>
        </div>
        {status ? (
          <div
            style={{
              background: "rgba(248, 237, 207, 0.94)",
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
              <p style={{ color: "#6a5947", margin: 0, maxWidth: 560 }}>{status}</p>
            </div>
          </div>
        ) : null}
        {hoverInfo ? (
          <div
            style={{
              background: "rgba(248, 237, 207, 0.95)",
              border: "3px solid #17110d",
              borderRadius: 0,
              boxShadow: "6px 6px 0 rgba(179,49,36,0.28)",
              color: "#17110d",
              left: hoverInfo.x + 16,
              maxWidth: 320,
              padding: "0.75rem",
              pointerEvents: "none",
              position: "absolute",
              top: hoverInfo.y + 16,
              zIndex: 2,
            }}
          >
            <strong style={{ fontFamily: "Impact, Arial Narrow, sans-serif", textTransform: "uppercase" }}>{hoverInfo.point.offense_description}</strong>
            <p style={{ margin: "0.35rem 0 0" }}>
              {hoverInfo.point.complaint_date} · {hoverInfo.point.borough} · {hoverInfo.point.law_category}
            </p>
            {hoverInfo.point.premise_type ? <p style={{ margin: "0.25rem 0 0" }}>{hoverInfo.point.premise_type}</p> : null}
          </div>
        ) : null}
        {selectedPoint ? (
          <aside
            style={{
              background: "rgba(248,237,207,0.98)",
              border: "4px solid #17110d",
              borderRadius: 0,
              boxShadow: "8px 8px 0 rgba(179,49,36,0.3)",
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
            <span className="stamp">Filed Incident</span>
            <h3 style={{ margin: "0.75rem 1.5rem 0.5rem 0" }}>{selectedPoint.offense_description}</h3>
            <p style={{ color: "#6a5947", margin: "0 0 0.75rem" }}>
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
