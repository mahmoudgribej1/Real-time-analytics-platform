import { useEffect, useState } from "react";
const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function PressureTop() {
    const [rows, setRows] = useState([]);
    const load = async ()=> setRows(await (await fetch(`${API}/api/pressure/top?minutes=10&limit=8`)).json());
    useEffect(()=>{ load(); const t=setInterval(load, 7000); return ()=>clearInterval(t); },[]);
    return (
        <div className="card">
            <h3>Top City Pressure (last 10m)</h3>
            <table className="table">
                <thead><tr><th>City</th><th>Pressure</th><th>Orders</th><th>Avail Couriers</th><th>Orders/Avail</th><th>Avg Delay</th></tr></thead>
                <tbody>
                {rows.map((r,i)=>(
                    <tr key={i} className={r.pressure_score>=85?'crit':r.pressure_score>=75?'warn':''}>
                        <td>{r.city_name}</td>
                        <td>{r.pressure_score}</td>
                        <td>{r.order_count}</td>
                        <td>{r.available_couriers ?? 0}</td>
                        <td>{(r.demand_per_available ?? 0).toFixed?.(2)}</td>
                        <td>{r.avg_delivery_time?.toFixed?.(1)}m</td>
                    </tr>
                ))}
                </tbody>
            </table>
        </div>
    );
}
