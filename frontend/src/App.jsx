
import { useEffect, useState } from "react";
import { NavLink, Routes, Route, useNavigate } from "react-router-dom";
import axios from "axios";
import PressureTop from "./PressureTop";
import Recommendations from "./Recommendations";
import Replay from "./Replay";
import Scenarios from "./Scenarios";
import SlaList from "./SlaList";
import SentimentPanel from "./SentimentPanel";
import { useLocation } from "react-router-dom";
import RevenuePanel from "./RevenuePanel";
import { readCache, writeCache } from "./cache";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;
const WS  = API.replace("http","ws") + "/ws";

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

function Tiles({ kpi }) {
    return (
        <div className="grid">
            <div className="card">Orders/min <b>{kpi.orders_per_min}</b></div>
            <div className="card">SLA today <b>{kpi.sla_today}</b></div>
            <div className="card">ETA MAE 1h <b>{kpi.eta_mae_1h}</b> min</div>
        </div>
    );
}

function SlaTable({ rows }) {
    return (
        <table className="table">
            <thead><tr><th>Order</th><th>City</th><th>Courier</th><th>Delay min</th><th>When</th></tr></thead>
            <tbody>
            {rows.map((r, i) => (
                <tr key={i}>
                    <td>{r.order_id}</td>
                    <td>{r.city_name}</td>
                    <td>{r.courier_name}</td>
                    <td>{r.delay_minutes}</td>
                    <td>{new Date(r.created_at).toLocaleTimeString()}</td>
                </tr>
            ))}
            </tbody>
        </table>
    );
}

function ActionBar({ onToast }) {
    const [city, setCity] = useState("Tunis");
    const [minutes, setMinutes] = useState(15);
    const [mult, setMult] = useState(2.0);
    const [loading, setLoading] = useState(null);
    const [mutes, setMutes] = useState([]);
    const cities = ["Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine","Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur","Kebili","Tataouine","Jendouba","Beja","Mahdia"];

    const post = async (path, body, key) => {
        try {
            setLoading(key);
            const r = await fetch(`${API}${path}`, {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify(body)
            });
            const data = await r.json();
            onToast?.(data.message || "Done", "success");
            await refreshMutes();
        } catch (e) {
            onToast?.("Error: "+e, "error");
        } finally {
            setLoading(null);
        }
    };

    const refreshMutes = async () => {
        const r = await fetch(`${API}/api/actions/mutes`);
        setMutes(await r.json());
    };

    useEffect(()=>{ refreshMutes(); const t=setInterval(refreshMutes, 10000); return ()=>clearInterval(t); },[]);

    const muted = mutes.find(m=>m.city_name===city);

    return (
        <div className="card actionbar">
            <b>City</b>
            <select value={city} onChange={e=>setCity(e.target.value)}>
                {cities.map(c=><option key={c}>{c}</option>)}
            </select>

            <b>Mute</b>
            <input type="number" value={minutes} min={5} max={120} onChange={e=>setMinutes(+e.target.value)} />
            <button className="btn" disabled={loading==='mute'} onClick={()=>post("/api/actions/mute_city",{city, minutes},'mute')}>Mute alerts</button>
            <button className="btn" disabled={loading==='unmute'} onClick={()=>post("/api/actions/unmute_city",{city},'unmute')}>Unmute</button>
            {muted ? <span className="pill">Muted until {new Date(muted.until).toLocaleTimeString()}</span> : null}

            <b>Surge x</b>
            <input type="number" step="0.5" value={mult} min={1} max={5} onChange={e=>setMult(+e.target.value)} />
            <button className="btn" disabled={loading==='surge'} onClick={()=>post("/api/actions/trigger_surge",{city, multiplier: mult, minutes},'surge')}>Trigger surge</button>

            <button className="btn" disabled={loading==='retrain'} onClick={()=>post("/api/retrain",{},'retrain')}>Retrain ETA model</button>
        </div>
    );
}

function OverviewPage() {
    const [kpi, setKpi] = useState(
        readCache("kpi", { orders_per_min: 0, sla_today: 0, eta_mae_1h: 0 })
    );
    const [sla, setSla] = useState(readCache("sla_list", []));
    const events = useWebSocket(WS);
    const { toasts, push } = useLocalToasts();

    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const [k, s] = await Promise.all([
                    fetch(`${API}/api/kpi`).then(r => r.json()),
                    fetch(`${API}/api/sla?limit=50`).then(r => r.json()),
                ]);
                if (!alive) return;
                setKpi(k); writeCache("kpi", k);
                setSla(s); writeCache("sla_list", s);
            } catch {}
        };
        load(); // immediate (no zeros)
        const t = setInterval(load, 5000);
        return () => { alive = false; clearInterval(t); };
    }, []);

    return (
        <>
            <Tiles kpi={kpi} />
            <ActionBar onToast={push} />

            <h3>Live Alerts</h3>
            <div className="toasts">
                {events.map((e, i) => (
                    <div
                        key={i}
                        className={`toast ${e.severity || "info"}`}
                        onClick={() => {
                            const city = e?.details?.city_name || e.city_name;
                            if (city) window.location.href = `/replay?city=${encodeURIComponent(city)}`;
                        }}
                        style={{ cursor: (e?.details?.city_name || e.city_name) ? "pointer" : "default" }}
                    >
                        <b>{e.title}</b>
                        <div style={{ fontSize: 12, opacity: 0.85 }}>
                            {e?.details?.order_id ? <>#{e.details.order_id} • </> : null}
                            {e?.details?.city_name ? <>{e.details.city_name} • </> : null}
                            {e?.details?.courier_name ? <>{e.details.courier_name} • </> : null}
                            {typeof e?.details?.delay_minutes === "number" ? <>+{e.details.delay_minutes}m late</> : null}
                        </div>
                    </div>
                ))}
            </div>
            <div className="grid2">
                <PressureTop />
                <Recommendations />
            </div>
            <div className="grid2">
                <SentimentPanel />
                <RevenuePanel />
            </div>

            <h3 style={{display:"none"}}>SLA Violations</h3>
            <SlaList rows={sla} />

            {/* local toasts overlay */}
            <div className="overlay-toasts">
                {toasts.map(t=><div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
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

function ActivityPage() {
    const [rows, setRows] = useState([]);
    useEffect(()=>{ const load=async()=> setRows(await (await fetch(`${API}/api/actions/log?limit=50`)).json()); load(); const t=setInterval(load,5000); return ()=>clearInterval(t); },[]);
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

export default function App() {
    const navigate = useNavigate();
    useEffect(()=>{ /* default route */ if (location.pathname==="/") navigate("/overview"); },[]);
    return (
        <div className="wrap">
            <nav className="nav">
                <div className="brand">Ops Command Center</div>
                <div className="links">
                    <NavLink to="/overview" className={({isActive})=>isActive?"active":""}>Overview</NavLink>
                    <NavLink to="/dashboards" className={({isActive})=>isActive?"active":""}>Dashboards</NavLink>
                    <NavLink to="/activity" className={({isActive})=>isActive?"active":""}>Activity</NavLink>
                    <NavLink to="/replay" className={({isActive})=>isActive?"active":""}>Replay</NavLink>
                    <NavLink to="/scenarios" className={({isActive})=>isActive?"active":""}>Scenarios</NavLink>
                </div>
            </nav>

            <Routes>
                <Route path="/overview" element={<OverviewPage/>} />
                <Route path="/dashboards" element={<DashboardsPage/>} />
                <Route path="/activity" element={<ActivityPage/>} />
                <Route path="/replay" element={<Replay/>} />
                <Route path="/scenarios" element={<Scenarios/>} />
            </Routes>
        </div>
    );
}
