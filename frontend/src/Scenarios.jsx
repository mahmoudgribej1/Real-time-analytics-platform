import { useEffect, useMemo, useRef, useState } from "react";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;
const WS  = API.replace(/^http/, "ws") + "/ws";

function useWebSocketEvents(url) {
    const [events, setEvents] = useState([]);
    useEffect(() => {
        const ws = new WebSocket(url);
        ws.onmessage = (e) => { try { const m = JSON.parse(e.data); setEvents(p => [m,...p].slice(0,100)); } catch {} };
        const ping = setInterval(() => { try { ws.send("ping"); } catch {} }, 25000);
        return () => { clearInterval(ping); ws.close(); };
    }, [url]);
    return events;
}
function usePolling(fn, ms, deps=[]) {
    const [data, setData] = useState(null);
    useEffect(() => {
        let alive = true;
        const load = async () => { try { const v = await fn(); if (alive) setData(v); } catch {} };
        load(); const t = setInterval(load, ms);
        return () => { alive = false; clearInterval(t); };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);
    return data;
}

export default function Scenarios(){
    const [city, setCity] = useState("Tunis");
    const [rainMinutes, setRainMinutes] = useState(20);
    const [assumeRain, setAssumeRain] = useState(false);

    const [promoFactor, setPromoFactor] = useState(1.5);
    const [promoMinutes, setPromoMinutes] = useState(20);

    const [outPct, setOutPct] = useState(0.3);
    const [outMinutes, setOutMinutes] = useState(10);

    const [busy, setBusy] = useState("");
    const [est, setEst] = useState(null);
    const [estimating, setEstimating] = useState(false);

    const events = useWebSocketEvents(WS);
    const scenarioEvents = events.filter(e => e?.type === "SCENARIO" || e?.type === "PLAYBOOK").slice(0, 6);

    const flags = usePolling(
        async () => await (await fetch(`${API}/api/sim/list`)).json(),
        3000,
        [city]
    ) || [];
    const replay = usePolling(
        async () => await (await fetch(`${API}/api/replay?city=${encodeURIComponent(city)}&minutes=120`)).json(),
        15000,
        [city]
    ) || { pressure: [], breaches: [] };
    const actions = usePolling(
        async () => {
            const rows = await (await fetch(`${API}/api/actions/log?limit=40`)).json();
            return rows.filter(r => ["sim_rain","sim_promo","sim_outage"].includes(r.action)
                && (r?.params?.city === city || r?.params?.city_name === city));
        },
        5000,
        [city]
    ) || [];

    const doPost = async (path, body, key) => {
        try {
            setBusy(key);
            const r = await fetch(`${API}${path}`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body) });
            const data = await r.json().catch(()=>({}));
            toast(`✔ ${data.message || "Command sent"}`);
        } catch (e) {
            toast(`✖ ${String(e)}`, "error");
        } finally { setBusy(""); }
    };

    const toastQ = useRef([]);
    const [toasts, setToasts] = useState([]);
    function toast(text, kind="info"){
        const id = Date.now()+Math.random();
        setToasts(t => [...t, {id, text, kind}]);
        setTimeout(()=> setToasts(t => t.filter(x=>x.id!==id)), 3200);
    }

    // active flags (countdown)
    const now = Date.now();
    const activeForCity = flags.filter(f => f.city_name === city);
    useEffect(()=>{ setAssumeRain(activeForCity.some(f => f.key === "rain")); }, [city, flags]);
    const withCountdown = activeForCity.map(f => {
        const until = Date.parse(f.until); const ms = Math.max(0, until - now);
        const m = Math.floor(ms/60000), s = Math.floor((ms%60000)/1000);
        return { ...f, countdown: `${m}m ${String(s).padStart(2,"0")}s` };
    });

    // Sparklines data
    const pressurePoints = (replay.pressure || []).map(p => ({ t: p.ts, y: p.pressure_score })).slice(-60);
    const breachPoints   = (replay.breaches || []).map(b => ({ t: b.ts, y: b.breaches })).slice(-60);

    const cities = ["Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine","Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur","Kebili","Tataouine","Jendouba","Beja","Mahdia"];

    const estimate = async () => {
        try {
            setEstimating(true);
            const r = await fetch(`${API}/api/sim/estimate`, {
                method:"POST", headers:{"Content-Type":"application/json"},
                body: JSON.stringify({
                    city,
                    promo_factor: promoFactor,
                    outage_pct: outPct,
                    rain_on: !!assumeRain,
                    minutes_window: 120
                })
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            setEst(await r.json());
        } catch (e) {
            toast(`✖ Estimate failed: ${String(e)}`, "error");
            setEst(null);
        } finally { setEstimating(false); }
    };

    return (
        <div className="wrap-scenarios">
            <div className="card">
                <div style={{display:"flex", alignItems:"center", gap:12}}>
                    <h2 style={{margin:0}}>Scenarios</h2>
                    <div style={{marginLeft:12}}>
                        <b>City</b>{" "}
                        <select value={city} onChange={e=>setCity(e.target.value)}>
                            {cities.map(c => <option key={c}>{c}</option>)}
                        </select>
                        <span style={{marginLeft:10, color:"var(--muted)"}}>Active flags poll every ~3s</span>
                    </div>
                </div>
            </div>

            <div className="grid-scenarios">
                {/* Rain */}
                <div className="card">
                    <h3>Rain</h3>
                    <div className="row form">
                        <label>Minutes</label>
                        <input type="number" min={5} max={120} value={rainMinutes} onChange={e=>setRainMinutes(+e.target.value)} />
                    </div>
                    <div className="row form">
                        <label>Assume rain</label>
                        <input type="checkbox" checked={assumeRain} onChange={e=>setAssumeRain(e.target.checked)} />
                    </div>
                    <div className="row">
                        <button className="btn" disabled={busy==="rain_on"} onClick={()=>doPost("/api/sim/rain", { city, on:true, minutes: rainMinutes }, "rain_on")}>Start rain</button>
                        <button className="btn secondary" disabled={busy==="rain_off"} onClick={()=>doPost("/api/sim/rain", { city, on:false, minutes: 1 }, "rain_off")}>Stop rain</button>
                    </div>
                    <div className="note">Forces <code>weather="Rainy"</code> in generator for this city.</div>
                </div>

                {/* Promo */}
                <div className="card">
                    <h3>Promo (demand boost)</h3>
                    <div className="row form">
                        <label>Factor</label>
                        <input type="number" step="0.1" min={1.1} max={3} value={promoFactor} onChange={e=>setPromoFactor(+e.target.value)} />
                    </div>
                    <div className="row form">
                        <label>Minutes</label>
                        <input type="number" min={5} max={120} value={promoMinutes} onChange={e=>setPromoMinutes(+e.target.value)} />
                    </div>
                    <button className="btn" disabled={busy==="promo"} onClick={()=>doPost("/api/sim/promo", { city, factor: promoFactor, minutes: promoMinutes }, "promo")}>Trigger promo</button>
                    <div className="note">Increases order rate in the generator if promo flag is active.</div>
                </div>

                {/* Courier outage */}
                <div className="card">
                    <h3>Courier outage</h3>
                    <div className="row form">
                        <label>Offline %</label>
                        <input type="number" step="0.05" min={0.05} max={0.9} value={outPct} onChange={e=>setOutPct(+e.target.value)} />
                    </div>
                    <div className="row form">
                        <label>Minutes</label>
                        <input type="number" min={5} max={60} value={outMinutes} onChange={e=>setOutMinutes(+e.target.value)} />
                    </div>
                    <button className="btn" disabled={busy==="outage"} onClick={()=>doPost("/api/sim/outage", { city, pct_offline: outPct, minutes: outMinutes }, "outage")}>Trigger outage</button>
                    <div className="note">Temporarily removes a % of available couriers.</div>
                </div>

                {/* Impact Estimate */}
                <div className="card">
                    <h3>Scenario Impact Estimate</h3>
                    <div className="row form">
                        <label>Promo ×</label>
                        <input type="number" step="0.1" min={1} max={3} value={promoFactor} onChange={e=>setPromoFactor(+e.target.value)} />
                    </div>
                    <div className="row form">
                        <label>Outage %</label>
                        <input type="number" step="0.05" min={0} max={0.9} value={outPct} onChange={e=>setOutPct(+e.target.value)} />
                    </div>
                    <div className="row form">
                        <label>Rain</label>
                        <input type="checkbox" checked={assumeRain} onChange={e=>setAssumeRain(e.target.checked)} />
                    </div>
                    <button className="btn" disabled={estimating} onClick={estimate}>{estimating ? "Estimating..." : "Estimate impact"}</button>

                    {est && (
                        <>
                            <div className="impact-grid">
                                <ImpactTile label="Pressure" base={est.baseline.pressure_score} next={est.predicted.pressure_score} fmt={(v)=>`${v}`} />
                                <ImpactTile label="DPA"       base={est.baseline.demand_per_available} next={est.predicted.demand_per_available} fmt={(v)=>v.toFixed(2)} />
                                <ImpactTile label="Avg time (m)" base={est.baseline.avg_delivery_time} next={est.predicted.avg_delivery_time} fmt={(v)=>v.toFixed(1)} />
                                <ImpactTile label="Breaches/min" base={est.baseline.breaches_per_min} next={est.predicted.breaches_per_min} fmt={(v)=>v.toFixed(2)} />
                                <ImpactTile label="ETA typical (m)" base={est.baseline.eta_typical} next={est.predicted.eta_typical} fmt={(v)=>v.toFixed(1)} />
                            </div>
                            <div className="note">Estimates use current city snapshot + simple uplifts (log-scaled pressure on demand/supply, +rain penalty). Treat as directional.</div>
                        </>
                    )}
                </div>

                {/* Live evidence */}
                <div className="card">
                    <h3>Live evidence</h3>
                    <div className="evidence">
                        <div className="mini">
                            <div className="label">Active flags ({city})</div>
                            {!withCountdown.length ? <div className="pill">No active flags</div> :
                                <ul className="flags">
                                    {withCountdown.map((f,i)=>(
                                        <li key={i}><span className="pill">{f.key}</span><span className="muted">ends in</span> <b>{f.countdown}</b></li>
                                    ))}
                                </ul>
                            }
                        </div>
                        <div className="mini">
                            <div className="label">Recent scenario events</div>
                            {!scenarioEvents.length ? <div className="muted">No events yet.</div> :
                                <ul className="events">
                                    {scenarioEvents.map((e,i)=>(
                                        <li key={i}><span className={`dot ${e.severity||"info"}`} /><b>{e.title}</b></li>
                                    ))}
                                </ul>
                            }
                        </div>
                    </div>
                </div>

                {/* Proof: metrics */}
                <div className="card span2">
                    <h3>Proof: {city} last 2h</h3>
                    <div className="proof-grid">
                        <SparkLine title="Pressure score" data={pressurePoints} />
                        <SparkLine title="SLA breaches / min" data={breachPoints} />
                    </div>
                    <div className="note">After starting a scenario, expect pressure or breaches to move within a few minutes.</div>
                </div>

                {/* Actions log */}
                <div className="card span2">
                    <h3>Recent scenario actions ({city})</h3>
                    <table className="table">
                        <thead><tr><th>Time</th><th>Action</th><th>Params</th><th>Result</th></tr></thead>
                        <tbody>
                        {!actions.length ? <tr><td colSpan={4} style={{opacity:.7}}>No recent actions.</td></tr> :
                            actions.map((r,i)=>(
                                <tr key={i}>
                                    <td>{new Date(r.ts).toLocaleTimeString()}</td>
                                    <td>{r.action}</td>
                                    <td><code style={{fontSize:12}}>{JSON.stringify(r.params)}</code></td>
                                    <td>{r.result}</td>
                                </tr>
                            ))
                        }
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="overlay-toasts">
                {toasts.map(t => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
            </div>
        </div>
    );
}

function ImpactTile({ label, base, next, fmt=(v)=>String(v) }){
    const delta = (next ?? 0) - (base ?? 0);
    const up = delta >= 0;
    return (
        <div className="impact-tile">
            <div className="label">{label}</div>
            <div className="vals">
                <span className="base">{fmt(base ?? 0)}</span>
                <span className="arrow">→</span>
                <span className="next">{fmt(next ?? 0)}</span>
                <span className={`delta ${up ? "up" : "down"}`}>{up? "+" : ""}{fmt(delta)}</span>
            </div>
            <div className="bar">
                <div className="bar-in" style={{ width: `${Math.max(6, Math.min(100, (Number(next)||0) / (Number(base)||1) * 50 + 50))}%` }} />
            </div>
        </div>
    );
}

/* Tiny sparkline component reused */
function SparkLine({ title, data }) {
    const pts = (data || []).slice(-60);
    const min = Math.min(...pts.map(p=>p.y), 0);
    const max = Math.max(...pts.map(p=>p.y), 1);
    const range = Math.max(1, max - min);
    const path = pts.map((p,i)=>{
        const x = (i/(pts.length-1||1))*100;
        const y = 100 - ((p.y - min)/range)*100;
        return `${i===0?"M":"L"} ${x},${y}`;
    }).join(" ");
    return (
        <div className="spark">
            <div className="spark-head">
                <div className="label">{title}</div>
                <div className="value">{pts.length? pts[pts.length-1].y : "-"}</div>
            </div>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="spark-svg">
                <path d={path} className="spark-line" />
            </svg>
        </div>
    );
}
