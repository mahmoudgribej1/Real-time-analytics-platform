import { useEffect, useMemo, useState } from "react";
import {
    ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
    PieChart, Pie, Cell,
} from "recharts";
import { useNavigate } from "react-router-dom";
import { readCache, writeCache } from "./cache";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

// simple, readable colors
const POS_COLOR = "#22c55e";
const NEG_COLOR = "#ef4444";

export default function SentimentPanel() {
    const [minutes, setMinutes] = useState(60);
    const cacheKey = `sentiment_${minutes}`;
    const [sortBy, setSortBy] = useState("positivity"); // 'positivity' | 'reviews'
    const [limit, setLimit] = useState(12);
    const [rows, setRows] = useState(readCache(cacheKey, []));
    const [summary, setSummary] = useState(readCache(`${cacheKey}_summary`, { total:0, posRate:0, avg:0 }));
    const [err, setErr] = useState("");

    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                setErr("");
                const r = await fetch(`${API}/api/sentiment?minutes=${minutes}`, { cache: "no-store" });
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                const data = await r.json();
                if (!alive) return;

                const safe = (Array.isArray(data) ? data : [])
                    .map(d => ({
                        city_name: d.city_name,
                        reviews: Number(d.reviews) || 0,
                        pos: Number(d.pos) || 0,
                        neg: Number(d.neg) || 0,
                        avg_rating: Number(d.avg_rating) || 0,
                    }))
                    .filter(d => d.reviews > 0);

                setRows(safe);
                writeCache(cacheKey, safe);

                // recompute summary
                const total = safe.reduce((a,b)=>a+b.reviews,0);
                const pos = safe.reduce((a,b)=>a+b.pos,0);
                const neg = safe.reduce((a,b)=>a+b.neg,0);
                const avg = total ? (safe.reduce((a,b)=>a+b.avg_rating*b.reviews,0)/total) : 0;
                const posRate = total ? Math.round((pos/(pos+neg))*100) : 0;
                const sum = { total, posRate, avg };
                setSummary(sum);
                writeCache(`${cacheKey}_summary`, sum);
            } catch (e) {
                if (!alive) return;
                setRows([]);
                setErr(String(e));
            }
        };
        load();
        const t = setInterval(load, 10000);
        return () => { alive = false; clearInterval(t); };
    }, [minutes]);

    const enriched = useMemo(() => {
        return rows.map(r => ({
            ...r,
            posPct: r.reviews ? (r.pos * 100) / r.reviews : 0,
        }));
    }, [rows]);

    const totals = useMemo(() => {
        return enriched.reduce((acc, r) => {
            acc.reviews += r.reviews;
            acc.pos += r.pos;
            acc.neg += r.neg;
            acc.ratingSum += r.avg_rating * r.reviews;
            return acc;
        }, { reviews: 0, pos: 0, neg: 0, ratingSum: 0 });
    }, [enriched]);

    const overallAvg = totals.reviews ? (totals.ratingSum / totals.reviews) : 0;
    const overallPosPct = totals.reviews ? Math.round((totals.pos * 100) / totals.reviews) : 0;

    const sorted = useMemo(() => {
        const copy = [...enriched];
        if (sortBy === "reviews") {
            copy.sort((a,b) => b.reviews - a.reviews);
        } else {
            copy.sort((a,b) => b.posPct - a.posPct);
        }
        return copy.slice(0, limit || copy.length);
    }, [enriched, sortBy, limit]);

    // Recharts data for pie & bars
    const pieData = [
        { name: "Positive", value: totals.pos, fill: POS_COLOR },
        { name: "Negative", value: totals.neg, fill: NEG_COLOR },
    ];
    const barData = sorted.map(r => ({ name: r.city_name, Positive: r.pos, Negative: r.neg }));
    // --- tight domain + dynamic Y-axis width ---
    const maxStack = Math.max(1, ...barData.map(d => (d.Positive || 0) + (d.Negative || 0)));
    const xDomain  = [0, Math.ceil(maxStack * 1.05)];     // 5% headroom

// rough width per label character so long names fit without giant padding
    const maxLabelLen = Math.max(0, ...barData.map(d => (d.name?.length || 0)));
    const yAxisWidth  = Math.min(130, Math.max(80, 7 * maxLabelLen));  // 80–130px


    const navigate = useNavigate();
    const openSupersetCity = (city) => {
        navigate(`/dashboards?city=${encodeURIComponent(city)}`);
    };

    return (
        <div className="card">
            <div className="sentiment-header">
                <h3>Customer Sentiment</h3>
                <div className="sentiment-controls">
                    <label>
                        Window:
                        <select value={minutes} onChange={e => setMinutes(+e.target.value)}>
                            {[30, 60, 120, 240].map(m => <option key={m} value={m}>{m}m</option>)}
                        </select>
                    </label>
                    <label>
                        Sort by:
                        <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
                            <option value="positivity">% Positive</option>
                            <option value="reviews">Reviews</option>
                        </select>
                    </label>
                    <label>
                        Top:
                        <select value={limit} onChange={e => setLimit(+e.target.value)}>
                            {[6, 8, 12, 20].map(n => <option key={n} value={n}>{n}</option>)}
                            <option value={0}>All</option>
                        </select>
                    </label>
                </div>
            </div>

            {err && <div className="note error">Error: {err}</div>}

            {/* KPI tiles */}
            <div className="grid sentiment-kpis">
                <div className="card mini">
                    <div>Total reviews</div>
                    <b>{totals.reviews}</b>
                </div>
                <div className="card mini">
                    <div>Overall positivity</div>
                    <b>{overallPosPct}%</b>
                    <div className="bar">
                        <div className="bar-in" style={{ width: `${overallPosPct}%`, background: POS_COLOR }} />
                    </div>
                </div>
                <div className="card mini">
                    <div>Avg rating</div>
                    <b>{overallAvg.toFixed(2)} ★</b>
                </div>
            </div>

            {!enriched.length ? (
                <div>No recent reviews.</div>
            ) : (
                <>
                    <div className="grid2 sentiment-charts">
                        {/* Donut */}
                        <div className="card">
                            <h4>Overall (last {minutes}m)</h4>
                            <ResponsiveContainer width="100%" height={220}>
                                <PieChart>
                                    <Pie
                                        data={pieData}
                                        dataKey="value"
                                        nameKey="name"
                                        innerRadius={60}
                                        outerRadius={90}
                                        isAnimationActive={false}
                                    >
                                        {pieData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                                    </Pie>
                                    <Legend />
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Horizontal stacked bars per city */}
                        <div className="card">
                            <h4>Cities (stacked Pos/Neg)</h4>
                            <ResponsiveContainer width="100%" height={360}>
                                <BarChart
                                    data={barData}
                                    layout="vertical"
                                    margin={{ left: 16, right: 8, top: 6 }}   // was 110,8,6
                                    barCategoryGap="20%"
                                >
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        type="number"
                                        domain={xDomain}
                                        tick={{ fill: 'var(--muted)', fontSize: 12 }}
                                        tickLine={false}
                                        allowDecimals={false}
                                    />
                                    <YAxis
                                        type="category"
                                        dataKey="name"
                                        width={yAxisWidth}                        // was fixed 120
                                        tick={{ fill: 'var(--muted)', fontSize: 12 }}
                                        tickLine={false}
                                    />
                                    <Tooltip />
                                    <Bar dataKey="Positive" stackId="a" fill="#22c55e" />
                                    <Bar dataKey="Negative" stackId="a" fill="#ef4444" />
                                </BarChart>
                            </ResponsiveContainer>

                        </div>
                    </div>

                    {/* Compact table */}
                    <div className="card">
                        <h4>Details</h4>
                        <table className="table">
                            <thead>
                            <tr>
                                <th>City</th><th>Reviews</th><th>Avg ★</th><th>% Pos</th><th></th>
                            </tr>
                            </thead>
                            <tbody>
                            {sorted.map((r, i) => {
                                const pct = r.reviews ? Math.round((r.pos * 100) / r.reviews) : 0;
                                return (
                                    <tr key={i} className={pct >= 65 ? "ok" : pct < 45 ? "crit" : ""}>
                                        <td>{r.city_name}</td>
                                        <td>{r.reviews}</td>
                                        <td>{r.avg_rating.toFixed(2)}</td>
                                        <td style={{ minWidth: 160 }}>
                                            <div className="bar">
                                                <div className="bar-in" style={{ width: `${pct}%`, background: POS_COLOR }} />
                                            </div>
                                            <div style={{ fontSize: 12, opacity: .75 }}>{pct}%</div>
                                        </td>
                                        <td style={{ textAlign: "right" }}>
                                            <button className="btn" onClick={() => openSupersetCity(r.city_name)}>Open in dashboard</button>
                                        </td>
                                    </tr>
                                );
                            })}
                            </tbody>
                        </table>
                    </div>
                </>
            )}
        </div>
    );
}
