import { useEffect, useState, useRef } from "react";
import { NavLink, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import axios from "axios";
import PressureTop from "./PressureTop";
// import Recommendations from "./Recommendations";
import Replay from "./Replay";
import Scenarios from "./Scenarios";
import SlaList from "./SlaList";
import SentimentPanel from "./SentimentPanel";
import RevenuePanel from "./RevenuePanel";
import ThemeToggle from "./ThemeToggle";
import { WSProvider } from "./wsBus";
import { CityProvider, useCity } from "./CityContext";
import LiveOrders from "./LiveOrders";
import SmartAlerts from "./SmartAlerts";
import Heatmap from "./Heatmap";
import RevenueAnalytics from "./RevenueAnalytics";
import TopEntities from "./TopEntities";
import RestaurantsLive from "./RestaurantsLive";
import CouriersLive from "./CouriersLive";
import RestaurantMap from "./RestaurantMap";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WeatherInsights from "./WeatherInsights";
import WeatherMap from "./WeatherMap";
import DynamicSlaViolations from "./DynamicSlaViolations";   // ADD
import DynamicModelHealth from "./DynamicModelHealth";       // ADD
import DeliveryRouteMap from "./DeliveryRouteMap";


/* --------------------------- CONFIG --------------------------- */
const defaultBase = `${location.protocol}//${location.hostname}:8001`;
const envBase = (import.meta.env.VITE_API || "").trim();
export const API = envBase && !/^https?:\/\/webapi(:\d+)?/i.test(envBase) ? envBase : defaultBase;
export const WS  = API.replace(/^http/i, "ws") + "/ws";


/* ------------------------ SHARED HELPERS ---------------------- */
const cache = {
    get(key, fallback) {
        try {
            const s = sessionStorage.getItem(key);
            return s ? JSON.parse(s) : fallback;
        } catch { return fallback; }
    },
    set(key, val) {
        try { sessionStorage.setItem(key, JSON.stringify(val)); } catch {}
    },
    del(key) {
        try { sessionStorage.removeItem(key); } catch {}
    }
};

const isEmptyKpi = (k) =>
    !k ||
    ((k.orders_per_min || 0) === 0 &&
        (k.sla_today || 0)     === 0 &&
        ((k.eta_mae_1h || 0)   === 0));

/* Keep last good snapshot in module scope so it survives route changes */
const LAST_GOOD = {
    kpi: null,  // { ...k, _ts }
    sla: []
};

const queryClient = new QueryClient({
       defaultOptions: {
         queries: {
               staleTime: 15_000,             // data considered fresh for 15s
                   refetchOnWindowFocus: false,   // avoid surprise refetches when tab focused
                   retry: 1
             }
       }
 });

/* --------------------- REUSABLE HOOKS ------------------------- */
function useWebSocket(url) {
    const [events, setEvents] = useState([]);
    useEffect(() => {
        const ws = new WebSocket(url);
        ws.onmessage = e => {
            try {
                const msg = JSON.parse(e.data);
                setEvents(prev => [msg, ...prev].slice(0, 12));
            } catch {}
        };
        const ping = setInterval(() => { try { ws.send("ping"); } catch {} }, 25000);
        return () => { clearInterval(ping); ws.close(); };
    }, [url]);
    return events;
}

function useLocalToasts() {
    const [toasts, setToasts] = useState([]);
    const push = (text, kind="info") => {
        const id = Date.now() + Math.random();
        setToasts(t => [...t, { id, text, kind }]);
        setTimeout(()=> setToasts(t => t.filter(x=>x.id!==id)), 3500);
    };
    return { toasts, push };
}

/* -------------------------- UI BITS --------------------------- */
function Tiles({ kpi, loading }) {
    const showSkel = loading || !kpi || !kpi._ts;
    if (showSkel) {
        return <div className="kpi-grid">
            <div className="card kpi skeleton kpi-skel"></div>
            <div className="card kpi skeleton kpi-skel"></div>
            <div className="card kpi skeleton kpi-skel"></div>
        </div>;
    }
    return (
        <div className="kpi-grid">
            <div className="card kpi"><div>Orders/min</div><b>{kpi.orders_per_min}</b></div>
            <div className="card kpi"><div>SLA today</div><b>{kpi.sla_today}</b></div>
            <div className="card kpi"><div>ETA MAE 1h</div><b>{kpi.eta_mae_1h}</b><span style={{marginLeft:6}}>min</span></div>
        </div>
    );
}

// function ActionBar({ onToast }) {
//     const [city, setCity] = useState("Tunis");
//     const [minutes, setMinutes] = useState(15);
//     const [mult, setMult] = useState(2.0);
//     const [loading, setLoading] = useState(null);
//     const [mutes, setMutes] = useState([]);
//     const cities = ["Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine","Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur","Kebili","Tataouine","Jendouba","Beja","Mahdia"];
//
//     const post = async (path, body, key) => {
//         try {
//             setLoading(key);
//             const r = await fetch(`${API}${path}`, {
//                 method: "POST",
//                 headers: {"Content-Type":"application/json"},
//                 body: JSON.stringify(body)
//             });
//             const data = await r.json();
//             onToast?.(data.message || "Done", "success");
//             await refreshMutes();
//         } catch (e) {
//             onToast?.("Error: "+e, "error");
//         } finally {
//             setLoading(null);
//         }
//     };
//
//     const refreshMutes = async () => {
//         const r = await fetch(`${API}/api/actions/mutes`);
//         setMutes(await r.json());
//     };
//
//     useEffect(()=>{ refreshMutes(); const t=setInterval(refreshMutes, 10000); return ()=>clearInterval(t); },[]);
//
//     const muted = mutes.find(m=>m.city_name===city);
//
//     return (
//         <div className="card actionbar">
//             <b>City</b>
//             <select value={city} onChange={e=>setCity(e.target.value)}>
//                 {cities.map(c=><option key={c}>{c}</option>)}
//             </select>
//
//             <b>Mute</b>
//             <input type="number" value={minutes} min={5} max={120} onChange={e=>setMinutes(+e.target.value)} />
//             <button className="btn" disabled={loading==='mute'} onClick={()=>post("/api/actions/mute_city",{city, minutes},'mute')}>Mute alerts</button>
//             <button className="btn ghost" disabled={loading==='unmute'} onClick={()=>post("/api/actions/unmute_city",{city},'unmute')}>Unmute</button>
//             {muted ? <span className="badge">🔕 Muted until {new Date(muted.until).toLocaleTimeString()}</span>
//                 : null}
//
//             <b>Surge x</b>
//             <input type="number" step="0.5" value={mult} min={1} max={5} onChange={e=>setMult(+e.target.value)} />
//             <button className="btn" disabled={loading==='surge'} onClick={()=>post("/api/actions/trigger_surge",{city, multiplier: mult, minutes},'surge')}>Trigger surge</button>
//
//             <button className="btn" disabled={loading==='retrain'} onClick={()=>post("/api/retrain",{},'retrain')}>Retrain ETA model</button>
//         </div>
//     );
// }

/* ------------------------ PAGES ------------------------------- */
function OverviewPage() {
    // sanitize old bad cache (zeros)
    const cached = cache.get("kpi", null);
    const goodCached = cached && !isEmptyKpi(cached) ? cached : null;
    if (cached && !goodCached) cache.del("kpi");

    const [kpi, setKpi] = useState(LAST_GOOD.kpi || goodCached || null);
    const [sla, setSla] = useState(LAST_GOOD.sla?.length ? LAST_GOOD.sla : cache.get("sla", []));
    const [loading, setLoading] = useState(!(LAST_GOOD.kpi || goodCached));
    const emptyHits = useRef(0);

    const events = useWebSocket(WS);
    const { toasts, push } = useLocalToasts();

    useEffect(() => {
        let alive = true;

        const load = async () => {
            try {
                const [kRes, sRes] = await Promise.allSettled([
                    fetch(API + "/api/kpi"),
                    fetch(API + "/api/sla?limit=50"),
                ]);

                if (!alive) return;

                // SLA can update independently
                if (sRes.status === "fulfilled") {
                    const s = await sRes.value.json();
                    setSla(s);
                    LAST_GOOD.sla = s;
                    cache.set("sla", s);
                }

                if (kRes.status === "fulfilled") {
                    const k = await kRes.value.json();
                    const looksEmpty = isEmptyKpi(k);

                    if (looksEmpty) {
                        emptyHits.current += 1;

                        // If we've never shown KPI yet, keep skeleton
                        if (!kpi) return;

                        // If we already have KPI, ignore empties; keep last good
                        if (emptyHits.current < 3) return;

                        // If consistently empty (3+ ticks), keep last good
                        return;
                    }

                    emptyHits.current = 0;
                    const kWithTs = { ...k, _ts: Date.now() };

                    setKpi(kWithTs);
                    LAST_GOOD.kpi = kWithTs;
                    cache.set("kpi", kWithTs);
                    setLoading(false);
                }
            } catch {
                // keep whatever we have
            }
        };

        // initial + poll
        load();
        const t = setInterval(load, 5000);

        // refresh immediately when tab becomes visible (helps after navigation)
        const onVis = () => { if (document.visibilityState === "visible") load(); };
        document.addEventListener("visibilitychange", onVis);

        return () => {
            alive = false;
            clearInterval(t);
            document.removeEventListener("visibilitychange", onVis);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // run once per mount

    return (
        <>
            <div className="hero">
                <div>
                    <div className="badge">⚡ Real-Time Ops</div>
                    <h1>Real-Time Operations <span style={{color:"var(--primary)"}}>Command Center</span></h1>
                    <p>Monitor, analyze, and optimize delivery performance with live insights.</p>
                </div>
                <div className="cta">
                    <button className="btn" onClick={()=>window.scrollTo({top:999,behavior:'smooth'})}>View Analytics</button>
                    <button className="btn ghost" onClick={()=>navigate('/dashboards')}>Dashboards</button>
                </div>
            </div>
            <div className="stats">
                <div className="stat">
                    <div className="sub">Orders/min</div>
                    <div className="val">{kpi?.orders_per_min ?? 0}</div>
                </div>
                <div className="stat">
                    <div className="sub">SLA today</div>
                    <div className="val">{kpi?.sla_today ?? 0}</div>
                </div>
                <div className="stat">
                    <div className="sub">ETA MAE 1h</div>
                    <div className="val">{kpi?.eta_mae_1h ?? 0}<span style={{fontSize:14,opacity:.7}}> min</span></div>
                </div>
                <div className="stat">
                    <div className="sub">System</div>
                    <div className="val" style={{fontSize:18}}>
                        <span className="badge" style={{background:'rgba(34,197,94,.14)', color:'#34d399', borderColor:'rgba(34,197,94,.3)'}}>● Healthy</span>
                    </div>
                </div>
            </div>
            <div className="grid2">
                <LiveOrders />
                <SmartAlerts />
            </div>
            <div className="row2 full">
                <RestaurantsLive />
                <CouriersLive />
            </div>


            {/*<ActionBar onToast={push} />*/}

            <h3>Live Alerts</h3>
            <div className="toasts">
                {events.map((e, i) => (
                    <div key={i} className={`toast ${e.severity || "info"}`}>
                        <b>{e.title}</b>
                        {e.details ? (
                            <div style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>
                                {e.details.city_name ? `${e.details.city_name} — ` : ""}
                                {e.details.courier_name ? `Courier ${e.details.courier_name} — ` : ""}
                                {typeof e.details.delay_minutes === "number" ? `${e.details.delay_minutes}m late` : ""}
                            </div>
                        ) : null}
                    </div>
                ))}
            </div>

            <div className="grid2">
                <PressureTop />
                {/*<Recommendations />*/}
            </div>
            <div className="row2 full">
                <RestaurantMap />
            </div>

            <div className="row2 full">
                <div className="card"><SentimentPanel /></div>
                {/*<div className="card"><RevenuePanel /></div>*/}
                <div className="card"><RevenueAnalytics /></div>

            </div>

            <div className="full">
                <SlaList rows={sla} />
            </div>

            <div className="overlay-toasts">
                {toasts.map((t) => (
                    <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>
                ))}
            </div>



            {/*<div className="row2 full">*/}
            {/*    <RevenueAnalytics />*/}
            {/*</div>*/}

            <div
                className="row2 full"
                style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(420px, 0.9fr) 1.6fr", // map | Top Today
                    gap: 16,
                    alignItems: "start"
                }}
            >
                <Heatmap />
                <div style={{ minWidth: 0 }}>
                    <TopEntities />
                </div>
            </div>


        </>
    );
}

function DashboardsPage() {
    const { search } = useLocation();
    const q = new URLSearchParams(search);
    const city = q.get("city") || "All Cities";

    const SLA = "http://localhost:8088/superset/dashboard/p/6eA72DQZKX8/?standalone=1";
    const ORD = "http://localhost:8088/superset/dashboard/p/yYzwLYeZxKA/?standalone=1";

    return (
        <>
            <div className="card">
                <h3>SLA Dashboard <span style={{fontWeight:400, opacity:.7}}>({city})</span></h3>
                <iframe src={SLA} title="SLA" style={{width:"100%", height:"85vh", border:0, borderRadius:12}} />
            </div>
            <div className="card">
                <h3>Orders per City <span style={{fontWeight:400, opacity:.7}}>({city})</span></h3>
                <iframe src={ORD} title="Orders" style={{width:"100%", height:"85vh", border:0, borderRadius:12}} />
            </div>
        </>
    );
}

function DynamicSlaPage() {                                   // ADD
    const { city } = useCity();
    return (
        <>
            <div className="card" style={{ marginBottom: 16 }}>
                <h3 style={{ margin: 0 }}>Dynamic SLA</h3>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    Live overruns & ETA model health (separate from classic SLA)
                </div>
            </div>
            <div className="row2 full">
                <DynamicSlaViolations city={city} />
                <DynamicModelHealth />
            </div>
        </>
    );
}


function ActivityPage() {
    const [rows, setRows] = useState([]);
    useEffect(()=>{
        const load = async () => {
            const r = await fetch(`${API}/api/actions/log?limit=50`);
            setRows(await r.json());
        };
        load();
        const t=setInterval(load,5000);
        return ()=>clearInterval(t);
    },[]);
    return (
        <div className="card">
            <h3>Activity Log</h3>
            <table className="table">
                <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Params</th><th>Result</th></tr></thead>
                <tbody>
                {rows.map((r,i)=>(<tr key={i}>
                    <td>{new Date(r.ts).toLocaleTimeString()}</td>
                    <td>{r.user_name}</td><td>{r.action}</td>
                    <td><code style={{fontSize:12}}>{JSON.stringify(r.params)}</code></td>
                    <td>{r.result}</td>
                </tr>))}
                </tbody>
            </table>
        </div>
    );
}
function CityChip(){
    const { city, setCity } = useCity();
    const cities = ["Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine","Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur","Kebili","Tataouine","Jendouba","Beja","Mahdia"];
    return (
        <div className="city-chip">
            <span className="pill">City</span>
            <select value={city} onChange={e=>setCity(e.target.value)}>{cities.map(c=><option key={c}>{c}</option>)}</select>
        </div>
    );
}
// Replace the RouteViewerPage function in App.jsx with this:

function RouteViewerPage() {
    const [orderId, setOrderId] = useState("")
    const [recentRoutes, setRecentRoutes] = useState([])
    const [loading, setLoading] = useState(true)
    const [err, setErr] = useState(null)

    useEffect(() => {
        let alive = true
        setLoading(true)
        setErr(null)

        fetch(`${API}/api/routes/recent?limit=20`)
            .then(r => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`)
                return r.json()
            })
            .then(data => {
                if (!alive) return
                const rows = Array.isArray(data) ? data : Array.isArray(data?.rows) ? data.rows : []
                // Filter out entries without valid order_id
                const validRows = rows.filter(r => r.order_id && Number.isFinite(Number(r.order_id)) && Number(r.order_id) > 0)
                setRecentRoutes(validRows)
            })
            .catch(e => { if (alive) setErr(e.message) })
            .finally(() => { if (alive) setLoading(false) })

        return () => { alive = false }
    }, [])

    const parsedId = Number(orderId)
    const hasValidId = Number.isFinite(parsedId) && parsedId > 0

    const handleRecentClick = (id) => {
        const validId = Number(id)
        if (Number.isFinite(validId) && validId > 0) {
            setOrderId(String(validId))
        }
    }

    return (
        <>
            <div className="card">
                <h3>View Delivery Route</h3>

                <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
                    <input
                        type="number"
                        placeholder="Enter Order ID"
                        value={orderId}
                        onChange={e => setOrderId(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter" && hasValidId) {
                                // Trigger re-render by updating state
                                setOrderId(String(parsedId))
                            }
                        }}
                        style={{ flex: 1 }}
                    />
                    <button className="btn" onClick={() => setOrderId(orderId)} disabled={!hasValidId}>
                        Load Route
                    </button>
                </div>

                {loading ? <div style={{ color: "var(--muted)" }}>Loading recent deliveries...</div> : null}
                {err ? <div style={{ color: "var(--danger)" }}>Error: {err}</div> : null}

                <h4>Recent Deliveries</h4>

                {!loading && !err && recentRoutes.length === 0 ? (
                    <div style={{
                        textAlign: "center",
                        padding: 32,
                        background: "var(--bg-muted)",
                        borderRadius: 8,
                        color: "var(--muted)"
                    }}>
                        No recent routes available
                    </div>
                ) : (
                    <div style={{
                        display: "grid",
                        gap: 8,
                        maxHeight: 400,
                        overflowY: "auto",
                        paddingRight: 4
                    }}>
                        {recentRoutes.map((r, idx) => {
                            const isValidOrder = r.order_id && Number.isFinite(Number(r.order_id)) && Number(r.order_id) > 0

                            return (
                                <div
                                    key={r.order_id ?? `fallback-${idx}`}
                                    onClick={() => isValidOrder && handleRecentClick(r.order_id)}
                                    style={{
                                        padding: 12,
                                        background: "var(--bg-muted)",
                                        borderRadius: 8,
                                        cursor: isValidOrder ? "pointer" : "not-allowed",
                                        opacity: isValidOrder ? 1 : 0.5,
                                        border: orderId === String(r.order_id) ? "2px solid var(--primary)" : "2px solid transparent",
                                        transition: "all 0.2s"
                                    }}
                                    onMouseEnter={e => {
                                        if (isValidOrder) e.currentTarget.style.background = "var(--border)"
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.background = "var(--bg-muted)"
                                    }}
                                >
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                        <div>
                                            <div>
                                                Order #{r.order_id ?? "N/A"} • {r.courier_name ?? "Unknown Courier"}
                                                {!isValidOrder && <span style={{ color: "var(--danger)", marginLeft: 8 }}>(Invalid ID)</span>}
                                            </div>
                                            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                                                {r.restaurant_name ?? "Restaurant"} • {r.total_distance_km ?? "?"}km • {r.actual_duration_min ?? "?"}min
                                            </div>
                                        </div>
                                        {isValidOrder && (
                                            <span className="badge" style={{ background: "var(--primary)", color: "white" }}>
                                                View
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                )}
            </div>

            {hasValidId ? <DeliveryRouteMap key={parsedId} orderId={parsedId} /> : null}
        </>
    )
}



/* ------------------------ APP SHELL --------------------------- */
function Shell(){
    const navigate = useNavigate();
    useEffect(()=>{ if (location.pathname==="/") navigate("/overview"); },[]);
    return (
        <div className="wrap">
            <nav className="nav" aria-label="Primary">
                <ThemeToggle />
                <div className="brand">Ops Command Center</div>
                <CityChip/>
                <div className="links" role="navigation">
                    <NavLink to="/overview" className={({isActive})=>isActive?"active":""}>Overview</NavLink>
                    <NavLink to="/dashboards" className={({isActive})=>isActive?"active":""}>Dashboards</NavLink>
                    <NavLink to="/dynamic-sla" className={({isActive})=>isActive?"active":""}>Dynamic SLA</NavLink>
                    <NavLink to="/activity" className={({isActive})=>isActive?"active":""}>Activity</NavLink>
                    <NavLink to="/weather" className={({isActive})=>isActive?"active":""}>Weather</NavLink>
                    <NavLink to="/replay" className={({isActive})=>isActive?"active":""}>Replay</NavLink>
                    <NavLink to="/scenarios" className={({isActive})=>isActive?"active":""}>Scenarios</NavLink>
                    <NavLink to="/routes">Routes</NavLink>
                </div>
            </nav>
            <Routes>
                <Route path="/overview" element={<OverviewPage/>} />
                <Route path="/dashboards" element={<DashboardsPage />} />
                <Route path="/dynamic-sla" element={<DynamicSlaPage/>} />
                <Route path="/activity" element={<ActivityPage />} />
                <Route
                    path="/weather"
                    element={
                        <div className="grid" style={{ gridTemplateColumns: "1.2fr 1fr", alignItems: "start" }}>
                            <WeatherInsights />
                            <WeatherMap />
                        </div>
                    }
                />
                <Route path="/replay" element={<Replay/>} />
                <Route path="/scenarios" element={<Scenarios/>} />
                <Route path="/routes" element={<RouteViewerPage/>} />

            </Routes>
        </div>
    );
}

export default function App(){
    return (
        <QueryClientProvider client={queryClient}>
                   <WSProvider url={WS}>
                     <CityProvider>
                       <Shell/>
                     </CityProvider>
                   </WSProvider>
        </QueryClientProvider>
    );
}