// src/RestaurantDrawer.jsx
import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import "chart.js/auto";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

const makeOpts = (label) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: {
            enabled: true,
            callbacks: {
                // label shows metric value, title shows time
                title: (items) => items?.[0]?.label || "",
                label: (item) => `${label}: ${item.formattedValue}`,
            },
        },
    },
    scales: { x: { display: false }, y: { display: false } },
    elements: { point: { radius: 2, hitRadius: 8 }, line: { borderWidth: 2, tension: 0.35 } },
});

export default function RestaurantDrawer({ restaurant, onClose }) {
    const [trend, setTrend] = useState([]);

    useEffect(() => {
        if (!restaurant) return;
        let alive = true;
        fetch(`${API}/api/restaurants/trend?restaurant_id=${restaurant.restaurant_id}&hours=6`)
            .then((r) => r.json())
            .then((d) => { if (alive) setTrend(d || []); });
        return () => { alive = false; };
    }, [restaurant]);

    if (!restaurant) return null;

    const labels = trend.map((t) =>
        new Date(t.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
    );
    const orders = trend.map((t) => Number(t.orders_last_15m) || 0);
    const prep   = trend.map((t) => Number(t.avg_prep_time) || 0);

    return (
        <div className="drawer" onClick={onClose}>
            <div className="drawer-card" onClick={(e) => e.stopPropagation()}>
                <div className="drawer-head">
                    <div><b>{restaurant.restaurant_name}</b> · {restaurant.city_name}</div>
                    <button className="btn ghost" onClick={onClose}>Close</button>
                </div>

                <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div className="card" style={{ height: 180 }}>
                        <div className="sub">Orders (15m)</div>
                        <Line
                            data={{ labels, datasets: [{ label: "Orders", data: orders, borderColor: "#3b82f6" }] }}
                            options={makeOpts("Orders")}
                        />
                    </div>
                    <div className="card" style={{ height: 180 }}>
                        <div className="sub">Avg prep (min)</div>
                        <Line
                            data={{ labels, datasets: [{ label: "Avg prep", data: prep, borderColor: "#10b981" }] }}
                            options={makeOpts("Avg prep")}
                        />
                    </div>
                </div>

                {!trend.length && <div style={{ opacity:.7, marginTop:8 }}>No trend data yet.</div>}
            </div>
        </div>
    );
}
