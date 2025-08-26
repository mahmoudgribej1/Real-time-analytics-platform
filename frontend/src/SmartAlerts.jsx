import { useEffect, useState } from "react";
const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function SmartAlerts(){
    const [rows, setRows] = useState([]);
    useEffect(()=>{
        let alive=true;
        const load = async ()=>{
            const r = await fetch(`${API}/api/alerts/active`);
            const d = await r.json(); if (!alive) return; setRows(d);
        };
        load(); const t=setInterval(load, 8000);
        return ()=>{ alive=false; clearInterval(t); };
    },[]);
    return (
        <div className="card card-lg">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Smart Alerts</h3>
                <span className="badge">{rows.length} Active</span>
            </div>
            <div className="alerts">
                {rows.map((a, i)=>(
                    <div key={i} className={`alert ${a.severity}`}>
                        <div className="title">{a.title}</div>
                        {a.details && <div className="sub">{JSON.stringify(a.details)}</div>}
                        <button className="btn ghost" style={{marginLeft:"auto"}}>Resolve</button>
                    </div>
                ))}
                {!rows.length && <div style={{opacity:.7}}>No active alerts.</div>}
            </div>
        </div>
    );
}
