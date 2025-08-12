import { useEffect, useState } from "react";
const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function Recommendations() {
    const [rows, setRows] = useState([]);
    const [busyId, setBusyId] = useState(null);
    const [msg, setMsg] = useState("");

    const load = async ()=> {
        try {
            const r = await fetch(`${API}/api/recommendations/list?minutes=10`);
            setRows(await r.json());
        } catch {
            /* ignore */
        }
    };
    useEffect(()=>{ load(); const t=setInterval(load, 5000); return ()=>clearInterval(t); },[]);

    const act = async (path, r, label)=>{
        setBusyId(r.id ?? `${r.city_name}-${r.kind}`);
        setMsg("");
        try {
            const res = await fetch(`${API}/api/recommendations/${path}`, {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body: JSON.stringify({...r, user:"demo"})
            });
            if (!res.ok) throw new Error(await res.text());
            setMsg(`✓ ${label}`);
            await load();
        } catch(e) {
            setMsg(`✗ ${label}: ${e.message?.slice(0,120) || e}`);
        } finally {
            setBusyId(null);
            setTimeout(()=>setMsg(""), 2500);
        }
    };

    if (!rows.length) return <div className="card"><h3>Recommendations</h3><div>No recommendations right now.</div></div>;

    return (
        <div className="card">
            <h3>Recommendations <small style={{opacity:.7, marginLeft:8}}>{msg}</small></h3>
            <table className="table">
                <thead><tr><th>City</th><th>Kind</th><th>Score</th><th>Why</th><th>Suggested</th><th></th></tr></thead>
                <tbody>
                {rows.map((r,i)=>{
                    const id = r.id ?? `${r.city_name}-${r.kind}`;
                    return (
                        <tr key={i} className={r.score>=85?'crit':r.score>=75?'warn':''}>
                            <td>{r.city_name}</td>
                            <td>{r.kind}</td>
                            <td>{Math.round(r.score)}</td>
                            <td>{r.rationale}</td>
                            <td>{r.kind==='SURGE_CITY'
                                ? <>x{r.suggested_params?.multiplier} for {r.suggested_params?.minutes}m</>
                                : JSON.stringify(r.suggested_params)}</td>
                            <td style={{display:"flex", gap:8}}>
                                <button className="btn" disabled={busyId===id} onClick={()=>act("approve", r, "Approved")}>
                                    {busyId===id ? "…" : "Approve"}
                                </button>
                                <button className="btn" disabled={busyId===id} onClick={()=>act("dismiss", r, "Dismissed")}>
                                    {busyId===id ? "…" : "Dismiss"}
                                </button>
                            </td>
                        </tr>
                    );
                })}
                </tbody>
            </table>
        </div>
    );
}
