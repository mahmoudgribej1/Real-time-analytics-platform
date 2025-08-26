import { useEffect, useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function RevenueAnalytics(){
    const [kpis, setKpis] = useState({ gmv_today:0 });
    const [weekly, setWeekly] = useState([]);
    const [mprog, setMprog] = useState({ gmv_mtd:0, target:0, pct:0 });

    useEffect(()=>{
        let alive=true;
        const load=async ()=>{
            const k = await (await fetch(`${API}/api/revenue/kpis?minutes=60`)).json();
            const w = await (await fetch(`${API}/api/revenue/weekly`)).json();
            const m = await (await fetch(`${API}/api/revenue/monthly_progress`)).json();
            if (!alive) return;
            setKpis(k); setWeekly(w); setMprog(m);
        };
        load(); const t=setInterval(load, 10000);
        return ()=>{ alive=false; clearInterval(t); };
    },[]);

    return (
        <div className="card card-lg">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Revenue Analytics</h3>
                <button className="btn ghost">View Report</button>
            </div>
            <div className="stats" style={{gridTemplateColumns:"repeat(4, minmax(0,1fr))"}}>
                <div className="stat"><div className="sub">GMV (today)</div><div className="val">TND {Math.round(kpis.gmv_today||0).toLocaleString()}</div></div>
                <div className="stat"><div className="sub">Orders (window)</div><div className="val">{kpis.orders_window||0}</div></div>
                <div className="stat"><div className="sub">AOV (window)</div><div className="val">TND {Math.round(kpis.aov_window||0)}</div></div>
                <div className="stat"><div className="sub">MTD progress</div><div className="val">{mprog.pct.toFixed(0)}%</div></div>
            </div>

            <div className="card" style={{marginTop:12}}>
                <h4>Weekly Overview</h4>
                <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={weekly} margin={{ left: 20, right: 8, top: 6 }}>
                        <defs>
                            <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#f97316"/>
                                <stop offset="100%" stopColor="#fb923c"/>
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="day" tick={{ fontSize: 12 }} tickLine={false}/>
                        <YAxis tick={{ fontSize: 12 }} tickLine={false}/>
                        <Tooltip />
                        <Bar dataKey="gmv" fill="url(#revGrad)" radius={[6,6,0,0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>

            <div className="card" style={{marginTop:12}}>
                <h4>Monthly Progress</h4>
                <div className="bar" style={{height:10, background:"var(--surface-2)", borderRadius:999, overflow:"hidden"}}>
                    <div className="bar-in" style={{width:`${Math.min(100, mprog.pct)}%`, height:"100%", background:"linear-gradient(90deg,var(--primary),var(--primary-2))"}}/>
                </div>
                <div style={{marginTop:6, fontSize:12, color:"var(--muted)"}}>
                    TND {Math.round(mprog.gmv_mtd).toLocaleString()} / TND {Math.round(mprog.target).toLocaleString()}
                </div>
            </div>
        </div>
    );
}
