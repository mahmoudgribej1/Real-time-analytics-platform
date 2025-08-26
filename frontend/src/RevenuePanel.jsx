import { useEffect, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { readCache, writeCache } from "./cache";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function RevenuePanel() {
    const [minutes, setMinutes] = useState(60);
    const [kpis, setKpis] = useState(readCache(`rev_kpis_${minutes}`, {
        gmv_window:0, orders_window:0, aov_window:0, gmv_today:0, orders_today:0
    }));
    const [byCity, setByCity] = useState(readCache(`rev_city_${minutes}`, []));
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const [k, cWrap] = await Promise.all([
                    fetch(`${API}/api/revenue/kpis?minutes=${minutes}`).then(r=>r.json()),
                    fetch(`${API}/api/revenue/by_city?minutes=${minutes}`).then(r=>r.json()),
                ]);
                const c = Array.isArray(cWrap.rows) ? cWrap.rows : cWrap; // backward compat
                if (!alive) return;
                setKpis(k);   writeCache(`rev_kpis_${minutes}`, k);
                setByCity(c); writeCache(`rev_city_${minutes}`, c);
                setLoading(false);
            } catch {
                if (!alive) return;
                setLoading(false);
            }
        };
        load();
        const t = setInterval(load, 10000);
        return () => { alive = false; clearInterval(t); };
    }, [minutes]);

    const fmt = (v)=> new Intl.NumberFormat(undefined, { style:"currency", currency:"TND", maximumFractionDigits:0 }).format(v||0);

    return (
        <div className="card">
            <div style={{display:"flex", justifyContent:"space-between", alignItems:"center"}}>
                <h3>Revenue / GMV</h3>
                <div style={{display:"flex", gap:8, alignItems:"center"}}>
                    <span>Window</span>
                    <select value={minutes} onChange={e=>setMinutes(+e.target.value)}>
                        {[30,60,120,240].map(m=><option key={m} value={m}>{m}m</option>)}
                    </select>
                </div>
            </div>

            <div className="grid" style={{marginBottom:12}}>
                <div className="card mini"><div>GMV (window)</div><b>{fmt(kpis.gmv_window)}</b></div>
                <div className="card mini"><div>Orders (window)</div><b>{kpis.orders_window}</b></div>
                <div className="card mini"><div>AOV (window)</div><b>{fmt(kpis.aov_window)}</b></div>
                <div className="card mini"><div>GMV (today)</div><b>{fmt(kpis.gmv_today)}</b></div>
            </div>

            <div className="card">
                <h4>GMV by City (window)</h4>
                <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={byCity} margin={{ left: 24, right: 8, top: 6 }}>
                        <defs>
                            <linearGradient id="gmvGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#38bdf8"/>
                                <stop offset="100%" stopColor="#0ea5e9"/>
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="city_name" tick={{ fontSize: 12 }} tickLine={false}/>
                        <YAxis tick={{ fontSize: 12 }} tickLine={false}/>
                        <Tooltip formatter={(v)=>fmt(v)} />
                        <Bar dataKey="gmv" fill="url(#gmvGrad)" radius={[6,6,0,0]} />
                    </BarChart>
                </ResponsiveContainer>


            </div>
        </div>
    );
}
