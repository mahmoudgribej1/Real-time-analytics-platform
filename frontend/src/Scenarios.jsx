import { useEffect, useMemo, useState } from "react";
const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

const CITIES = [
    "Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine",
    "Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur",
    "Kebili","Tataouine","Jendouba","Beja","Mahdia"
];

function prettyTimeLeft(untilIso) {
    const ms = new Date(untilIso).getTime() - Date.now();
    if (ms <= 0) return "expired";
    const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
    return `${m}m ${String(s).padStart(2,"0")}s`;
}

export default function Scenarios() {
    const [city, setCity] = useState("Tunis");

    // inputs
    const [rainMinutes, setRainMinutes] = useState(20);
    const [promoMinutes, setPromoMinutes] = useState(20);
    const [promoFactor, setPromoFactor] = useState(1.5);
    const [outageMinutes, setOutageMinutes] = useState(10);
    const [outagePct, setOutagePct] = useState(0.3);

    // status
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState("");
    const [active, setActive] = useState([]); // from /api/sim/list

    const loadActive = async () => {
        try {
            const res = await fetch(`${API}/api/sim/list`);
            if (!res.ok) throw new Error(await res.text());
            setActive(await res.json());
        } catch (e) {
            // ignore noise
        }
    };

    useEffect(() => {
        loadActive();
        const t = setInterval(loadActive, 3000);
        return () => clearInterval(t);
    }, []);

    const post = async (url, body) => {
        setBusy(true); setMsg("");
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error(await res.text());
            setMsg("✓ Done");
            loadActive();
        } catch (e) {
            setMsg(`✗ ${e.message?.slice(0,140) || e}`);
        } finally {
            setBusy(false);
            setTimeout(() => setMsg(""), 3000);
        }
    };

    const startRain = () => post(`${API}/api/sim/rain`, { city, on: true, minutes: rainMinutes });
    const stopRain  = () => post(`${API}/api/sim/rain`, { city, on: false, minutes: 1 });
    const startPromo = () => post(`${API}/api/sim/promo`, { city, factor: Number(promoFactor), minutes: promoMinutes });
    const startOutage = () => post(`${API}/api/sim/outage`, { city, pct_offline: Number(outagePct), minutes: outageMinutes });

    const rows = useMemo(() => active
        .sort((a,b)=> new Date(b.until) - new Date(a.until))
        .map((r,i)=>({
            id: i,
            key: r.key,
            city: r.city_name,
            details: r.params,
            endsIn: prettyTimeLeft(r.until),
        })), [active]);

    return (
        <div className="card">
            <h3>Scenarios</h3>

            <div style={{display:"flex", gap:12, alignItems:"center", marginBottom:12, flexWrap:"wrap"}}>
                <label><b>City</b></label>
                <select value={city} onChange={e=>setCity(e.target.value)}>
                    {CITIES.map(c => <option key={c}>{c}</option>)}
                </select>
                <span style={{opacity:0.7}}>Active flags poll every ~3s</span>
                <span style={{marginLeft:"auto"}}>{busy ? "…working" : msg}</span>
            </div>

            <div className="grid2">
                {/* Rain */}
                <div className="card">
                    <h4>Rain</h4>
                    <div className="row">
                        <label>Minutes</label>
                        <input type="number" min={1} max={120} value={rainMinutes}
                               onChange={e=>setRainMinutes(+e.target.value)} />
                    </div>
                    <div style={{display:"flex", gap:8}}>
                        <button className="btn" disabled={busy} onClick={startRain}>Start rain</button>
                        <button className="btn" disabled={busy} onClick={stopRain}>Stop rain</button>
                    </div>
                    <small>Forces weather="Rainy" in generator for this city.</small>
                </div>

                {/* Promo */}
                <div className="card">
                    <h4>Promo (demand boost)</h4>
                    <div className="row">
                        <label>Factor</label>
                        <input type="number" step="0.1" min={1} max={3} value={promoFactor}
                               onChange={e=>setPromoFactor(e.target.value)} />
                    </div>
                    <div className="row">
                        <label>Minutes</label>
                        <input type="number" min={1} max={120} value={promoMinutes}
                               onChange={e=>setPromoMinutes(+e.target.value)} />
                    </div>
                    <button className="btn" disabled={busy} onClick={startPromo}>Trigger promo</button>
                    <small>Increases order rate if generator uses promo flag (see note below).</small>
                </div>

                {/* Outage */}
                <div className="card">
                    <h4>Courier outage</h4>
                    <div className="row">
                        <label>Offline %</label>
                        <input type="number" step="0.05" min={0} max={0.9} value={outagePct}
                               onChange={e=>setOutagePct(+e.target.value)} />
                    </div>
                    <div className="row">
                        <label>Minutes</label>
                        <input type="number" min={1} max={120} value={outageMinutes}
                               onChange={e=>setOutageMinutes(+e.target.value)} />
                    </div>
                    <button className="btn" disabled={busy} onClick={startOutage}>Trigger outage</button>
                    <small>Temporarily removes a % of available couriers.</small>
                </div>
            </div>

            <div className="card" style={{marginTop:12}}>
                <h4>Active scenarios</h4>
                <table className="table">
                    <thead><tr><th>Key</th><th>City</th><th>Details</th><th>Ends in</th></tr></thead>
                    <tbody>
                    {rows.length ? rows.map(r=>(
                        <tr key={r.id}>
                            <td>{r.key}</td>
                            <td>{r.city}</td>
                            <td><code style={{fontSize:12}}>{JSON.stringify(r.details)}</code></td>
                            <td>{r.endsIn}</td>
                        </tr>
                    )) : <tr><td colSpan={4}>No active flags.</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
