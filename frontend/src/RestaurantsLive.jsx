// src/RestaurantsLive.jsx
import { useEffect, useState } from "react";
import { API } from "./App";
// If your wsBus DOES export useWSEvents, uncomment the next line:
import { useWSEvents } from "./wsBus";
import RestaurantDrawer from "./RestaurantDrawer";

/* ---------- helpers (top-level, single definitions) ---------- */
const fmtAge = (ms) => {
    if (!ms) return "—";
    const age = Date.now() - ms;
    const m = Math.floor(age / 60000);
    if (m <= 0) return "now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m ago`;
};
const isRowStale = (ms) => typeof ms === "number" && Date.now() - ms > 2 * 60 * 1000;

/* ============================================================ */
export default function RestaurantsLive({ city }) {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [sel, setSel] = useState(null); // for the drawer

    const pauseRestaurant = async (id) => {
        try {
            await fetch(`${API}/api/restaurants/pause`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ restaurant_id: id, minutes: 15 }),
            });
        } catch {}
    };

    // ---- Initial + periodic fetch
    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const qs = new URLSearchParams({
                    limit: "50",
                    ...(city ? { city } : {}),
                }).toString();
                const r = await fetch(`${API}/api/restaurants/live?${qs}`);
                const d = await r.json();
                if (!alive) return;
                setRows(Array.isArray(d) ? d : []);
                setLoading(false);
            } catch {
                /* keep last snapshot */
            }
        };
        load();
        const t = setInterval(load, 7000);
        return () => {
            alive = false;
            clearInterval(t);
        };
    }, [city]);


    let wsEvents = [];
    try { wsEvents = useWSEvents?.() || []; } catch {}
    useEffect(() => {
      if (!wsEvents.length) return;
      const e = wsEvents[0];
      if (e?.type !== "restaurant_update") return;
      const p = e.payload || {};
      const rid = p.restaurant_id;
      if (!rid) return;
      setRows((prev) => {
        const idx = prev.findIndex((r) => r.restaurant_id === rid);
        const base = idx >= 0 ? prev[idx] : { restaurant_id: rid };
        const merged = {
          ...base,
          city_name: base.city_name || e.city || base.city_name,
          restaurant_name: base.restaurant_name,
          orders_last_15m: Number(p.orders_last_15m ?? base.orders_last_15m ?? 0),
          avg_prep_time_min: Number(p.avg_prep_time_last_hour ?? base.avg_prep_time_min ?? 0),
          is_promo_active: !!p.is_promo_active,
          updated_ms: Number(p.report_timestamp || Date.now()),
        };
        const next = [...prev];
        if (idx >= 0) next[idx] = merged;
        else next.unshift(merged);
        return next.slice(0, 50);
      });
    }, [wsEvents]);

    return (
        <div className="card card-lg">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>Restaurant Load</h3>
                <span className="badge">{rows.length} tracked</span>
            </div>

            <table className="table">
                <thead>
                <tr>
                    <th>Restaurant</th>
                    <th>City</th>
                    <th>Orders (15m)</th>
                    <th>Avg prep</th>
                    <th>Promo</th>
                    <th>Updated</th>
                    <th></th>
                </tr>
                </thead>
                <tbody>
                {rows.map((r) => {
                    const updatedMs = Number(
                        r.updated_ms ?? (r.last_update ? Date.parse(r.last_update) : NaN)
                    );
                    const stale = isRowStale(updatedMs);

                    return (
                        <tr
                            key={r.restaurant_id}
                            className={`${r.critical ? "crit" : r.overloaded ? "warn" : ""} ${stale ? "stale" : ""}`}
                            onClick={() => setSel(r)}
                            style={{ cursor: "pointer" }}
                        >
                            <td>{r.restaurant_name}</td>
                            <td>{r.city_name}</td>
                            <td className="num">{r.orders_last_15m}</td>
                            <td className="num">
                                {r.avg_prep_time_min ? Math.round(r.avg_prep_time_min) + " min" : "—"}
                            </td>
                            <td>{r.is_promo_active ? <span className="badge">Promo</span> : "—"}</td>
                            <td className="num">{fmtAge(updatedMs)}</td>
                            <td>
                                <button
                                    className="btn ghost"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        pauseRestaurant(r.restaurant_id);
                                    }}
                                >
                                    Pause
                                </button>
                            </td>
                        </tr>
                    );
                })}

                {!rows.length && !loading && (
                    <tr>
                        <td colSpan={7} style={{ opacity: 0.7 }}>
                            No live rows yet.
                        </td>
                    </tr>
                )}
                </tbody>
            </table>

            {/* Drawer lives outside <tbody> */}
            <RestaurantDrawer restaurant={sel} onClose={() => setSel(null)} />
        </div>
    );
}
