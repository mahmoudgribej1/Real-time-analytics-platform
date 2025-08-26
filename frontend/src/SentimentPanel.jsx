import { useEffect, useMemo, useState } from "react";
import {
    ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
    PieChart, Pie, Cell,
} from "recharts";
import { useNavigate } from "react-router-dom";
import { readCache, writeCache } from "./cache";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;
const POS_COLOR = "#22c55e";
const NEG_COLOR = "#ef4444";

/** Normalize any server shape (array or {rows:[]}, different key names) into a common row */
function normalizePayload(raw) {
    let arr = [];
    if (Array.isArray(raw)) arr = raw;
    else if (raw && Array.isArray(raw.rows)) arr = raw.rows;

    return arr.map((d) => {
        // Accept both sink-style and fallback-style keys
        const entityId =
            d.entity_id ??
            d.restaurant_id ??
            d.delivery_person_id ??
            null;

        const entityName =
            d.entity_name ??
            d.name ??
            d.restaurant_name ??
            d.courier_name ??
            (entityId ? `#${entityId}` : "Unknown");

        const cityName = d.city_name ?? d.city ?? "";

        const reviews =
            Number(d.reviews ?? d.review_count ?? 0);

        const avgRating =
            Number(d.avg_rating ?? d.avg ?? 0);

        const pos =
            Number(d.pos ?? d.pos_reviews ?? d.positive ?? 0);

        const neg =
            Number(d.neg ?? d.neg_reviews ?? d.negative ?? 0);

        return {
            entity_id: entityId,
            entity_name: entityName,
            city_name: cityName,
            reviews,
            avg_rating: avgRating,
            pos,
            neg,
        };
    }).filter(r => r.reviews > 0);
}

export default function SentimentPanel() {
    const [minutes, setMinutes] = useState(60);
    const [entity, setEntity]   = useState("restaurant"); // "restaurant" | "courier"
    const [sortBy, setSortBy]   = useState("positivity"); // "positivity" | "reviews"
    const [limit, setLimit]     = useState(12);

    const cacheKey = `sentiment_${entity}_${minutes}`;
    const [rows, setRows] = useState(readCache(cacheKey, []));
    const [err, setErr]   = useState("");

    // fetch + normalize
    useEffect(() => {
        let alive = true;

        const load = async () => {
            try {
                setErr("");
                const res  = await fetch(`${API}/api/sentiment?minutes=${minutes}&kind=${entity}`, { cache: "no-store" });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const raw  = await res.json();
                const data = normalizePayload(raw);
                if (!alive) return;
                setRows(data);
                writeCache(cacheKey, data);
            } catch (e) {
                if (!alive) return;
                setErr(String(e));
                setRows([]);
            }
        };

        load();
        const t = setInterval(load, 10_000);
        return () => { alive = false; clearInterval(t); };
    }, [minutes, entity]); // cacheKey derives from these

    // enrich & totals
    const enriched = useMemo(() =>
        rows.map(r => ({
            ...r,
            label: `${r.entity_name} (${r.city_name})`,
            posPct: r.reviews ? (r.pos * 100) / r.reviews : 0,
        })), [rows]);

    const totals = useMemo(() => enriched.reduce((a, r) => {
        a.reviews   += r.reviews || 0;
        a.pos       += r.pos || 0;
        a.neg       += r.neg || 0;
        a.ratingSum += (r.avg_rating || 0) * (r.reviews || 0);
        return a;
    }, { reviews:0, pos:0, neg:0, ratingSum:0 }), [enriched]);

    const overallAvg    = totals.reviews ? (totals.ratingSum / totals.reviews) : 0;
    const overallPosPct = totals.reviews ? Math.round((totals.pos * 100) / totals.reviews) : 0;

    const sorted = useMemo(() => {
        const copy = [...enriched];
        if (sortBy === "reviews") copy.sort((a,b)=> (b.reviews||0)-(a.reviews||0));
        else copy.sort((a,b)=> (b.posPct||0)-(a.posPct||0));
        return copy.slice(0, limit || copy.length);
    }, [enriched, sortBy, limit]);

    // charts
    const pieData = [
        { name: "Positive", value: totals.pos, fill: POS_COLOR },
        { name: "Negative", value: totals.neg, fill: NEG_COLOR },
    ];
    const barData = sorted.map(r => ({ name: r.label, Positive: r.pos, Negative: r.neg }));

    const navigate = useNavigate();
    const openDash = (city) => navigate(`/dashboards?city=${encodeURIComponent(city)}`);

    return (
        <div className="card">
            <div className="sentiment-header" style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Customer Sentiment — {entity === "courier" ? "Couriers" : "Restaurants"}</h3>
                <div className="sentiment-controls" style={{display:"flex",gap:10,alignItems:"center"}}>
                    <label>Entity:
                        <select value={entity} onChange={e=>setEntity(e.target.value)}>
                            <option value="restaurant">Restaurants</option>
                            <option value="courier">Couriers</option>
                        </select>
                    </label>
                    <label>Window:
                        <select value={minutes} onChange={e=>setMinutes(+e.target.value)}>
                            {[30,60,120,240].map(m=><option key={m} value={m}>{m}m</option>)}
                        </select>
                    </label>
                    <label>Sort by:
                        <select value={sortBy} onChange={e=>setSortBy(e.target.value)}>
                            <option value="positivity">% Positive</option>
                            <option value="reviews">Reviews</option>
                        </select>
                    </label>
                    <label>Top:
                        <select value={limit} onChange={e=>setLimit(+e.target.value)}>
                            {[6,8,12,20].map(n=><option key={n} value={n}>{n}</option>)}
                            <option value={0}>All</option>
                        </select>
                    </label>
                </div>
            </div>

            {err && <div className="note error">Error: {err}</div>}

            {/* KPIs */}
            <div className="grid sentiment-kpis" style={{margin:"10px 0"}}>
                <div className="card mini"><div>Total reviews</div><b>{totals.reviews}</b></div>
                <div className="card mini">
                    <div>Overall positivity</div>
                    <b>{overallPosPct}%</b>
                    <div className="bar"><div className="bar-in" style={{width:`${overallPosPct}%`,background:POS_COLOR}}/></div>
                </div>
                <div className="card mini"><div>Avg rating</div><b>{overallAvg.toFixed(2)} ★</b></div>
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
                                    <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90} isAnimationActive={false}>
                                        {pieData.map((d,i)=><Cell key={i} fill={d.fill}/>)}
                                    </Pie>
                                    <Legend/><Tooltip/>
                                </PieChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Horizontal stacked bars */}
                        <div className="card">
                            <h4>{entity === "courier" ? "Couriers" : "Restaurants"} (stacked Pos/Neg)</h4>
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={barData} layout="vertical" margin={{ left: 140 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis type="number" />
                                    <YAxis type="category" dataKey="name" width={260} />
                                    <Tooltip />
                                    <Legend />
                                    <Bar dataKey="Positive" stackId="a" fill={POS_COLOR} />
                                    <Bar dataKey="Negative" stackId="a" fill={NEG_COLOR} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* Details */}
                    <div className="card">
                        <h4>Details</h4>
                        <table className="table">
                            <thead>
                            <tr>
                                <th>{entity === "courier" ? "Courier" : "Restaurant"} (City)</th>
                                <th>Reviews</th>
                                <th>Avg ★</th>
                                <th>% Pos</th>
                                <th></th>
                            </tr>
                            </thead>
                            <tbody>
                            {sorted.map((r,i)=>{
                                const pct = r.reviews ? Math.round((r.pos*100)/r.reviews) : 0;
                                return (
                                    <tr key={i} className={pct>=65 ? "ok" : pct<45 ? "crit" : ""}>
                                        <td>{r.entity_name} <span style={{opacity:.7}}>({r.city_name})</span></td>
                                        <td>{r.reviews}</td>
                                        <td>{Number(r.avg_rating || 0).toFixed(2)}</td>
                                        <td style={{ minWidth: 160 }}>
                                            <div className="bar"><div className="bar-in" style={{ width:`${pct}%`, background: POS_COLOR }} /></div>
                                            <div style={{ fontSize: 12, opacity: .75 }}>{pct}%</div>
                                        </td>
                                        <td style={{ textAlign: "right" }}>
                                            <button className="btn" onClick={()=>openDash(r.city_name)}>Open dashboard</button>
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
