import { useEffect, useState } from "react";
import { API } from "./App";
import { useWSEvents } from "./wsBus"; // if not exported, comment it out

const fmtClockUTC = (ms) =>
    ms ? new Date(ms).toLocaleTimeString('en-GB',
        { hour: '2-digit', minute: '2-digit', hour12:false, timeZone:'UTC' }) : '—';

const isStale = (ms) => typeof ms === 'number' && ms > 2*60*1000; // >2 min old
const fmtAge = (ms) => {
    if (!ms) return "—";
    const age = Date.now() - ms;
    const m = Math.floor(age/60000);
    if (m <= 0) return "now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m/60);
    return `${h}h ${m%60}m ago`;
};


export default function CouriersLive({ city }) {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const nudgeCourier = async (id) => {
        try {
            await fetch(`${API}/api/couriers/nudge`, {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ courier_id:id, reason:'overloaded' })
            });
        } catch {}
    };


    let wsEvents = [];
    try { wsEvents = useWSEvents?.() || []; } catch {}

    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const qs = new URLSearchParams({ limit: "50", ...(city ? { city } : {}) }).toString();
                const r = await fetch(`${API}/api/couriers/live?${qs}`);
                const d = await r.json();
                if (!alive) return;
                setRows(Array.isArray(d) ? d : []);
                setLoading(false);
            } catch { /* keep last */ }
        };
        load();
        const t = setInterval(load, 7000);
        return () => { alive = false; clearInterval(t); };
    }, [city]);

    useEffect(() => {
        if (!wsEvents.length) return;
        const e = wsEvents[0];
        if (e?.type !== "courier_update") return;
        const p = e.payload || {};
        const id = p.delivery_person_id;
        if (!id) return;

        setRows(prev => {
            const idx = prev.findIndex(r => (r.courier_id ?? r.delivery_person_id) === id);
            const merged = {
                ...(idx >= 0 ? prev[idx] : { courier_id: id, city_name: e.city || prev[idx]?.city_name }),
                active_deliveries: Number(p.active_deliveries_count ?? prev[idx]?.active_deliveries ?? 0),
                avg_speed_kmh: Number(p.avg_delivery_speed_today ?? prev[idx]?.avg_speed_kmh ?? 0),
                updated_ms: Number(p.report_timestamp || Date.now())
            };
            const next = [...prev];           // ⬅️ fix
            if (idx >= 0) next[idx] = merged; else next.unshift(merged);
            return next.slice(0, 50);
        });
    }, [wsEvents]);

    const now = Date.now();

    return (
        <div className="card card-lg">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Courier Activity</h3>
                <span className="badge">{rows.length} couriers</span>
            </div>

            <table className="table">
                <thead>
                <tr>
                    <th>ID</th><th>City</th><th>Active deliveries</th><th>Avg speed</th><th>Updated</th>
                </tr>
                </thead>
                <tbody>
                {rows.map(c => {
                    const updatedMs = c.updated_ms ?? (c.last_update ? Date.parse(c.last_update) : 0);
                    const staleMs   = updatedMs ? (Date.now() - updatedMs) : Number.POSITIVE_INFINITY;

                    return (
                        <tr key={c.courier_id ?? c.delivery_person_id ?? i}
                            className={`${c.overloaded ? 'warn' : ''} ${c.slow ? 'warn' : ''} ${isStale(staleMs) ? 'stale' : ''}`}>
                            <td>#{c.courier_id ?? c.delivery_person_id}</td>
                            <td>{c.city_name || '—'}</td>
                            <td className="num">{c.active_deliveries}</td>
                            <td className="num">{c.avg_speed_kmh ? Math.round(c.avg_speed_kmh) + ' km/h' : '—'}</td>
                            <td className="num">{fmtAge(c.updated_ms)}</td>
                            <td><button className="btn ghost" onClick={()=>nudgeCourier(c.courier_id)}>Nudge</button></td>

                        </tr>
                    );
                })}
                </tbody>
            </table>
        </div>
    );
}
