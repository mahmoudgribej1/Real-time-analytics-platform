import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { API } from "./App";

export default function DynamicSlaViolations({ city }) {
    const [minutes, setMinutes] = useState(180);
    const { data = [], isFetching } = useQuery({
        queryKey: ["dsla-violations", { minutes, city }],
        queryFn: async () => {
            const qs = new URLSearchParams({ minutes, limit: 50, threshold: 1.25, ...(city ? { city } : {}) });
            const r = await fetch(`${API}/api/dsla/violations?${qs}`);
            return r.json();
        },
        refetchInterval: 10_000,
        staleTime: 9_000,
    });

    return (
        <div className="card" style={{ padding: 20 }}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
                <h3 style={{margin:0}}>Dynamic SLA — Violations</h3>
                <div style={{display:"flex",gap:8}}>
                    {[60,180,720].map(m => (
                        <button key={m} className={`btn ${minutes===m?'':'ghost'}`} onClick={()=>setMinutes(m)}>
                            {m>=60? `${m/60}h` : `${m}m`}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{maxHeight: 380, overflowY:"auto", display:"grid", gap:8}}>
                {data.map(v => (
                    <div key={v.order_id} className="pill" style={{display:"grid",gridTemplateColumns:"1fr auto auto",gap:12,alignItems:"center"}}>
                        <div style={{minWidth:0}}>
                            <div style={{fontWeight:700, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis"}}>
                                #{v.order_id} · {v.restaurant_name}
                            </div>
                            <div style={{fontSize:12, color:"var(--muted)"}}>
                                {v.city_name} · {new Date(v.violation_timestamp).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}
                            </div>
                        </div>
                        <div style={{textAlign:"right"}}>
                            <div style={{fontWeight:800}}>{v.actual_minutes} min</div>
                            <div style={{fontSize:12, color:"var(--muted)"}}>actual</div>
                        </div>
                        <div style={{textAlign:"right"}}>
                            <div style={{fontWeight:800, color:"#ef4444"}}>
                                +{Math.round((v.overrun_pct-1)*100)}%
                            </div>
                            <div style={{fontSize:12, color:"var(--muted)"}}>vs {Math.round(v.predicted_minutes)}m</div>
                        </div>
                    </div>
                ))}
                {!data.length && <div style={{opacity:.7}}>No violations in window.</div>}
            </div>

            {isFetching && <div style={{marginTop:6, fontSize:12, color:"var(--muted)"}}>Refreshing…</div>}
        </div>
    );
}
