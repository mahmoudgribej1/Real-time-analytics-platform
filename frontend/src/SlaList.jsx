import { useEffect, useMemo, useState } from "react";

export default function SlaList({ rows }) {
    const [expanded, setExpanded] = useState(false);
    const [city, setCity] = useState("All");

    const cities = useMemo(() => ["All", ...Array.from(new Set(rows.map(r => r.city_name)))], [rows]);
    const filtered = useMemo(() => rows.filter(r => city==="All" ? true : r.city_name===city), [rows, city]);
    const shown = expanded ? filtered : filtered.slice(0, 12);

    return (
        <div className="card">
            <div style={{display:"flex", alignItems:"center", gap:12}}>
                <h3 style={{margin:0}}>SLA Violations</h3>
                <span style={{opacity:.7}}>{filtered.length} items</span>
                <div style={{marginLeft:"auto", display:"flex", gap:8, alignItems:"center"}}>
                    <b>City</b>
                    <select value={city} onChange={e=>setCity(e.target.value)}>
                        {cities.map(c=><option key={c}>{c}</option>)}
                    </select>
                    <button className="btn" onClick={()=>setExpanded(x=>!x)}>{expanded ? "Show less" : "Show all"}</button>
                </div>
            </div>

            <details open>
                <summary style={{cursor:"pointer", margin:"8px 0"}}>Latest {shown.length} items</summary>
                <ul style={{listStyle:"none", padding:0, margin:0, display:"grid", gap:6}}>
                    {shown.map((r,i)=>(
                        <li key={i} className="card" style={{padding:"8px 10px", display:"grid", gridTemplateColumns:"88px 1fr 100px 110px 120px", gap:8}}>
                            <code>#{r.order_id}</code>
                            <div><b>{r.city_name}</b> — {r.courier_name}</div>
                            <div><b>{r.delay_minutes}m</b> late</div>
                            <div>{new Date(r.created_at).toLocaleTimeString()}</div>
                            <div style={{opacity:.7}}>id:{r.delivery_person_id}</div>
                        </li>
                    ))}
                </ul>
            </details>
        </div>
    );
}
