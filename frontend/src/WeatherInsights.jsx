// src/WeatherInsights.jsx
import { useMemo, useRef, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { API } from "./App";
import Chart from "chart.js/auto";

const fmtWhen = (ms) =>
    ms ? new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

const cities = [
    "Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine",
    "Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur",
    "Kebili","Tataouine","Jendouba","Beja","Mahdia"
];

const fetchJSON = async (url) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
};
// Map many weather types to emojis (fallback included)
const weatherEmoji = (w) => {
    const k = (w || "").toLowerCase();
    const map = {
        sunny: "☀️",
        clear: "☀️",
        hot: "🌡️",
        cloudy: "☁️",
        overcast: "☁️",
        rainy: "🌧️",
        rain: "🌧️",
        drizzle: "🌦️",
        thunderstorm: "⛈️",
        storm: "⛈️",
        snow: "❄️",
        snowy: "❄️",
        hail: "🌨️",
        sleet: "🌨️",
        windy: "💨",
        wind: "💨",
        fog: "🌫️",
        mist: "🌫️",
        haze: "🌫️",
        sandstorm: "🌪️",
        sandstorms: "🌪️",
        dust: "🌪️",
    };
    return map[k] || "🌤️";
};

const weatherLabel = (w, isRain) => {
    // If upstream sometimes only flags rain without a nice name
    const label = w || (isRain ? "Rain" : "—");
    return `${weatherEmoji(label)} ${label}`;
};

export default function WeatherInsights() {
    const [city, setCity] = useState("");
    const [minutes, setMinutes] = useState(180);
    const [rain, setRain] = useState(""); // "", "true", "false"

    // Orders table
    const ordersKey = ["weatherOrders", { minutes, city, rain }];
    const { data: orders = [], isLoading: ordersLoading, isError: ordersErr } = useQuery({
        queryKey: ordersKey,
        queryFn: () => {
            const qs = new URLSearchParams({
                minutes: String(minutes),
                ...(city ? { city } : {}),
                ...(rain ? { rain } : {}),
                limit: "200",
            }).toString();
            return fetchJSON(`${API}/api/weather/orders?${qs}`);
        },
        refetchInterval: 10_000, // live-ish
    });

    // Impact summary (rain vs dry averages)
    const impactKey = ["weatherImpact", { hours: 24, city }];
    const { data: impact = [], isLoading: impactLoading, isError: impactErr } = useQuery({
        queryKey: impactKey,
        queryFn: () => fetchJSON(`${API}/api/weather/impact?hours=24${city ? `&city=${encodeURIComponent(city)}` : ""}`),
        refetchInterval: 60_000,
    });

    const rainVsDry = useMemo(() => {
        const rainRows = impact.filter((x) => x.is_rain === true);
        const dryRows = impact.filter((x) => x.is_rain === false);
        const avg = (xs) =>
            xs.length ? xs.reduce((a, b) => a + Number(b.avg_minutes || 0), 0) / xs.length : 0;
        return { rain: avg(rainRows), dry: avg(dryRows) };
    }, [impact]);

    // Tiny bar chart (Chart.js)
    const canvasRef = useRef(null);
    const chartRef = useRef(null);

    useEffect(() => {
        if (!canvasRef.current) return;
        if (!chartRef.current) {
            chartRef.current = new Chart(canvasRef.current, {
                type: "bar",
                data: {
                    labels: ["Dry", "Rain"],
                    datasets: [{ label: "Avg delivery time (min)", data: [0, 0] }],
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { suggestedMin: 0 } },
                },
            });
        }
        chartRef.current.data.datasets[0].data = [rainVsDry.dry, rainVsDry.rain];
        chartRef.current.update();
    }, [rainVsDry]);

    return (
        <div className="card card-lg">
            <div className="hero" style={{ marginBottom: 14 }}>
                <div>
                    <div className="badge">☔ Weather-aware ops</div>
                    <h1>Weather Insights</h1>
                    <p>See how rain and rush hours affect delivery time and route decisions.</p>
                </div>
                <div className="cta" style={{ gap: 12 }}>
                    <select value={city} onChange={(e) => setCity(e.target.value)} style={{ minWidth: 160 }}>
                        <option value="">All cities</option>
                        {cities.map((c) => (
                            <option key={c}>{c}</option>
                        ))}
                    </select>
                    <select value={rain} onChange={(e) => setRain(e.target.value)} style={{ minWidth: 140 }}>
                        <option value="">Any weather</option>
                        <option value="true">Rain only</option>
                        <option value="false">No rain</option>
                    </select>
                    <select
                        value={minutes}
                        onChange={(e) => setMinutes(+e.target.value)}
                        style={{ minWidth: 160 }}
                    >
                        {[60, 120, 180, 360, 720].map((m) => (
                            <option key={m} value={m}>
                                Last {m} min
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                <div className="card">
                    <h3>Rain vs Dry — average delivery time</h3>
                    <canvas ref={canvasRef} height="120" />
                    <div className="note">
                        Dry: {rainVsDry.dry.toFixed(1)} min • Rain: {rainVsDry.rain.toFixed(1)} min
                    </div>
                </div>

                <div className="card">
                    <h3>Recent enriched orders</h3>

                    <div
                        className="scroll-list"
                        style={{
                            maxHeight: 400,                 // Reduced height to give map more space
                            overflowY: "auto",
                            overflowX: "auto",              // Allow horizontal scroll if needed
                            marginTop: 10,
                            paddingRight: 6,
                            scrollbarGutter: "stable",
                            borderRadius: 12,
                            boxShadow: "inset 0 0 0 1px var(--border)",
                        }}
                    >
                        {/* Sticky header */}
                        <div
                            style={{
                                position: "sticky",
                                top: 0,
                                zIndex: 1,
                                background: "var(--surface-1)",
                                backdropFilter: "blur(4px)",
                                boxShadow: "0 1px 0 var(--border)",
                                padding: "8px 10px",        // Reduced padding
                                display: "grid",
                                // Use fixed widths to ensure restaurant names show fully
                                gridTemplateColumns: "50px 200px 70px 80px 40px 50px",
                                columnGap: 10,              // Reduced gap
                                alignItems: "center",
                                fontWeight: 700,
                                fontSize: "0.85rem",        // Smaller font
                                color: "var(--muted)",
                                letterSpacing: ".1px",
                            }}
                        >
                            <div>When</div>
                            <div>Restaurant</div>
                            <div>City</div>
                            <div>Weather</div>
                            <div>Rush</div>
                            <div style={{ textAlign: "right" }}>Min</div>
                        </div>

                        {orders.map((r, idx) => (
                            <div
                                key={r.order_id}
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "50px 200px 70px 80px 40px 50px",
                                    columnGap: 10,
                                    alignItems: "center",
                                    padding: "10px",           // More compact padding
                                    fontSize: "0.9rem",        // Slightly smaller text
                                    lineHeight: 1.3,
                                    borderBottom: "1px dashed var(--border)",
                                    background:
                                        idx % 2 === 0
                                            ? "color-mix(in oklab, var(--surface-2) 8%, transparent)"
                                            : "transparent",
                                    transition: "background .15s ease",
                                }}
                                onMouseEnter={(e) => (e.currentTarget.style.background =
                                    "color-mix(in oklab, var(--surface-2) 15%, transparent)")}
                                onMouseLeave={(e) => (e.currentTarget.style.background =
                                    idx % 2 === 0
                                        ? "color-mix(in oklab, var(--surface-2) 8%, transparent)"
                                        : "transparent")}
                            >
                                {/* Compact time format */}
                                <div style={{
                                    fontVariantNumeric: "tabular-nums",
                                    fontSize: "0.85rem",
                                    color: "var(--muted)"
                                }}>
                                    {fmtWhen(r.event_ms)}
                                </div>

                                {/* Restaurant name with better space allocation */}
                                <div
                                    title={r.restaurant_name}
                                    style={{
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        minWidth: 0,
                                        fontWeight: 500,        // Less bold
                                        fontSize: "0.9rem",
                                        paddingRight: "12px",   // More padding to prevent cramping
                                    }}
                                >
                                    {r.restaurant_name}
                                </div>

                                {/* Compact city */}
                                <div style={{
                                    fontSize: "0.85rem",
                                    color: "var(--muted)",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                }}>
                                    {r.city_name}
                                </div>

                                {/* Compact weather with icons only */}
                                <div style={{
                                    fontSize: "0.85rem",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                }}>
                                    {weatherLabel(r.weather, r.is_rain)}
                                </div>

                                {/* Smaller rush indicator */}
                                <div style={{ textAlign: "center" }}>
                                    {r.is_rush_hour ? (
                                        <span
                                            className="pill"
                                            style={{
                                                padding: "2px 6px",
                                                fontSize: "0.75rem",
                                                borderRadius: "4px"
                                            }}
                                        >
                                            R
                                        </span>
                                    ) : (
                                        <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>—</span>
                                    )}
                                </div>

                                {/* Compact time */}
                                <div style={{
                                    textAlign: "right",
                                    fontVariantNumeric: "tabular-nums",
                                    fontSize: "0.85rem",
                                    fontWeight: 600
                                }}>
                                    {r.time_taken_minutes ?? "—"}
                                </div>
                            </div>
                        ))}

                        {!ordersLoading && !orders.length && (
                            <div style={{
                                padding: 20,
                                opacity: 0.7,
                                textAlign: "center",
                                fontSize: "0.9rem"
                            }}>
                                No data in window.
                            </div>
                        )}
                        {(ordersLoading || impactLoading) && (
                            <div style={{
                                padding: 20,
                                opacity: 0.7,
                                textAlign: "center",
                                fontSize: "0.9rem"
                            }}>
                                Loading…
                            </div>
                        )}
                        {(ordersErr || impactErr) && (
                            <div style={{
                                padding: 20,
                                color: "var(--danger)",
                                textAlign: "center",
                                fontSize: "0.9rem"
                            }}>
                                Failed to load weather data.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
