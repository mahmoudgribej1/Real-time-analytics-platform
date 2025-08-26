// src/WeatherMap.jsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { API } from "./App";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const fetchJSON = async (url) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
};

export default function WeatherMap() {
    const [minutes, setMinutes] = useState(180);

    const { data: rows = [], isLoading, isError } = useQuery({
        queryKey: ["weatherCityHeat", { minutes }],
        queryFn: () => fetchJSON(`${API}/api/weather/city_heat?minutes=${minutes}`),
        refetchInterval: 30_000,
    });

    const center = [34.0, 9.0]; // Tunisia-ish center

    return (
        <div className="card card-lg">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>Weather heat by city</h3>
                <select value={minutes} onChange={(e) => setMinutes(+e.target.value)}>
                    {[60, 120, 180, 360, 720].map((m) => (
                        <option key={m} value={m}>
                            Last {m} min
                        </option>
                    ))}
                </select>
            </div>

            <div style={{ height: "70vh", borderRadius: 12, overflow: "hidden" }}>
                <MapContainer center={center} zoom={6} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
                    <TileLayer
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        attribution="&copy; OpenStreetMap"
                    />
                    {rows.map((r, i) => {
                        const radius = Math.max(6, Math.min(28, Math.sqrt(r.orders) * 2));
                        const rain = Math.max(0, Math.min(1, Number(r.rain_ratio || 0)));
                        const color = rain < 0.5 ? "#1e90ff" : "#f97316";
                        return (
                            <CircleMarker
                                key={i}
                                center={[r.lat, r.lon]}
                                radius={radius}
                                pathOptions={{ color, fillColor: color, fillOpacity: 0.25 }}
                            >
                                <Tooltip>
                                    <div style={{ minWidth: 180 }}>
                                        <b>{r.city_name}</b>
                                        <br />
                                        Orders: {r.orders}
                                        <br />
                                        Avg time: {r.avg_minutes} min
                                        <br />
                                        Rain share: {(rain * 100).toFixed(0)}%
                                    </div>
                                </Tooltip>
                            </CircleMarker>
                        );
                    })}
                </MapContainer>
                {isLoading && <div className="note" style={{ padding: 8 }}>Loading…</div>}
                {isError && <div className="note" style={{ padding: 8, color: "var(--danger)" }}>Failed to load map data.</div>}
            </div>
        </div>
    );
}
