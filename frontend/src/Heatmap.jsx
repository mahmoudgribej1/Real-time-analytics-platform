// Heatmap.jsx
import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import { latLngBounds } from "leaflet";
import "leaflet/dist/leaflet.css";
import { useQuery } from "@tanstack/react-query";
import { API } from "./App";

const WINDOW_OPTS = [60, 180, 720]; // minutes

// tiny helper: quantile with linear interpolation
const quantile = (arr, q) => {
    if (!arr?.length) return 0;
    const a = [...arr].sort((x, y) => x - y);
    const pos = (a.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    return a[base + 1] !== undefined ? a[base] + rest * (a[base + 1] - a[base]) : a[base];
};

export default function Heatmap() {
    const [minutes, setMinutes] = useState(60);
    const [map, setMap] = useState(null);
    const [focusCity, setFocusCity] = useState(null);

    const { data: pts = [], isFetching } = useQuery({
        queryKey: ["heatmap-cities", minutes],
        queryFn: async () => {
            const r = await fetch(`${API}/api/heatmap/cities?minutes=${minutes}`);
            return r.json();
        },
        refetchInterval: 10_000,
        staleTime: 9_000,
    });

    // --- dynamic bins from current data ---
    const bins = useMemo(() => {
        const pressures = (pts || [])
            .map(p => Number(p.pressure) || 0)
            .filter(v => v > 0);
        const q50 = quantile(pressures, 0.50) || 20;
        const q80 = quantile(pressures, 0.80) || 60;
        return { q50, q80 };
    }, [pts]);

    // default center if no data yet
    const center = useMemo(() => {
        if (pts?.length) {
            const p = pts[0];
            return [Number(p.lat) || 36.8, Number(p.lon) || 10.1];
        }
        return [36.8, 10.1];
    }, [pts]);

    // Fit to all points whenever data refreshes (unless a city is focused)
    useEffect(() => {
        if (!map || !pts?.length || focusCity) return;
        const coords = pts
            .filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon))
            .map(p => [p.lat, p.lon]);
        if (!coords.length) return;
        const b = latLngBounds(coords);
        if (b.isValid()) map.fitBounds(b.pad(0.15));
    }, [map, pts, focusCity]);

    // If user clicks a chip, pan/zoom to that city
    useEffect(() => {
        if (!map || !focusCity) return;
        const p = pts.find(x => x.city_name === focusCity);
        if (p && Number.isFinite(p.lat) && Number.isFinite(p.lon)) {
            map.setView([p.lat, p.lon], Math.max(map.getZoom(), 9));
        }
    }, [focusCity, pts, map]);

    const activeCount = (pts || []).filter(p => (Number(p.opm) || 0) > 0).length;

    // NEW: color never gray if opm>0; use dynamic quantiles for buckets
    const colorFor = (pressure, opm) => {
        const v = Number(pressure) || 0;
        const hasFlow = (Number(opm) || 0) > 0;
        if (!hasFlow) return "#94a3b8";           // slate for idle
        if (v >= bins.q80) return "#ef4444";      // high = red
        if (v >= bins.q50) return "#f59e0b";      // mid = amber
        return "#22d3ee";                          // low but active = cyan
    };

    // nicer radius: base + sqrt(opm) + small pressure term
    const radiusFor = (pressure, opm) => {
        const r = 6 + Math.sqrt(Math.max(0, Number(opm))) * 6 + (Number(pressure) || 0) / 25;
        return Math.max(6, Math.min(28, r));
    };

    return (
        <div className="card card-lg">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <h3 style={{ margin: 0 }}>Delivery Heatmap</h3>

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span className="badge" title="Cities with orders/min &gt; 0">{activeCount} Active</span>

                    <div style={{ display: "flex", gap: 6, background: "var(--surface-3)", padding: 4, borderRadius: 8, border: "1px solid var(--border)" }}>
                        {WINDOW_OPTS.map((m) => (
                            <button
                                key={m}
                                onClick={() => { setMinutes(m); setFocusCity(null); }}
                                className={`btn ${minutes === m ? "" : "ghost"}`}
                                style={{ padding: "6px 10px", fontSize: 12 }}
                            >
                                {m >= 60 ? `${m / 60}h` : `${m}m`}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div style={{ height: 420, borderRadius: 12, overflow: "hidden", marginTop: 8 }}>
                <MapContainer whenCreated={setMap} center={center} zoom={6} minZoom={5} maxZoom={14} style={{ height: "100%", width: "100%" }}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    {(pts || []).map((p) => {
                        if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) return null;
                        const pressure = Number(p.pressure) || 0;
                        const opm = Number(p.opm) || 0;
                        const radius = radiusFor(pressure, opm);
                        const col = colorFor(pressure, opm);

                        return (
                            <CircleMarker
                                key={`${p.city_name}-${p.lat}-${p.lon}`}
                                center={[p.lat, p.lon]}
                                radius={radius}
                                pathOptions={{ color: col, fillColor: col, fillOpacity: 0.35, weight: 1.5 }}
                            >
                                <Tooltip>
                                    <div style={{ lineHeight: 1.2 }}>
                                        <b>{p.city_name}</b>
                                        <div>Orders/min: <b>{opm}</b></div>
                                        <div>Pressure: <b>{Math.round(pressure)}</b></div>
                                    </div>
                                </Tooltip>
                            </CircleMarker>
                        );
                    })}
                </MapContainer>
            </div>

            {/* legend + hottest cities */}
            <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <span className="badge" style={{ background: "var(--surface-2)", borderColor: "var(--border)", color: "var(--muted)" }}>
          Legend:
          <span style={{ display: "inline-block", width: 10, height: 10, background: "#22d3ee", borderRadius: 3, marginLeft: 8 }} /> Low
          <span style={{ display: "inline-block", width: 10, height: 10, background: "#f59e0b", borderRadius: 3, margin: "0 6px 0 10px" }} /> Med
          <span style={{ display: "inline-block", width: 10, height: 10, background: "#ef4444", borderRadius: 3, marginLeft: 10 }} /> High
          <span style={{ marginLeft: 10, opacity: .7 }}>
            (q50≈{Math.round(bins.q50)}, q80≈{Math.round(bins.q80)})
          </span>
        </span>

                {(pts || [])
                    .slice()
                    .sort((a, b) => (Number(b.pressure) || 0) - (Number(a.pressure) || 0))
                    .slice(0, 8)
                    .map((p) => (
                        <button
                            key={`chip-${p.city_name}`}
                            className="badge"
                            onClick={() => setFocusCity(focusCity === p.city_name ? null : p.city_name)}
                            title="Center map to city"
                            style={{
                                cursor: "pointer",
                                background: focusCity === p.city_name ? "rgba(59,130,246,.18)" : "rgba(249,115,22,.14)",
                                borderColor: focusCity === p.city_name ? "rgba(59,130,246,.35)" : "rgba(249,115,22,.30)",
                                color: focusCity === p.city_name ? "#93c5fd" : "#fdba74",
                            }}
                        >
                            ⚡ {p.city_name} · {Math.round(Number(p.pressure) || 0)}
                        </button>
                    ))}
            </div>

            {isFetching && <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted)" }}>Refreshing…</div>}
        </div>
    );
}
