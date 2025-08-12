import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Legend } from "recharts";
const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;
import { useLocation } from "react-router-dom";


export default function Replay() {
    const [city, setCity] = useState("Tunis");
    const [minutes, setMinutes] = useState(120);
    const [data, setData] = useState({pressure:[], breaches:[], actions:[]});

    const load = async ()=> setData(await (await fetch(`${API}/api/replay?city=${encodeURIComponent(city)}&minutes=${minutes}`)).json());
    useEffect(()=>{ load(); },[city, minutes]);
    const location = useLocation();

    useEffect(() => {
        const q = new URLSearchParams(location.search);
        const c = q.get("city");
        if (c) setCity(c);
    }, [location.search]);


    return (
        <div className="card">
            <h3>Incident Replay</h3>
            <div style={{display:"flex", gap:12, alignItems:"center", marginBottom:12}}>
                <b>City</b>
                <select value={city} onChange={e=>setCity(e.target.value)}>
                    {["Tunis","Ariana","Ben Arous","Manouba","Sousse","Monastir","Nabeul","Sfax","Gabes","Medenine","Kairouan","Sidi Bouzid","Kasserine","Kef","Bizerte","Zaghouan","Siliana","Gafsa","Tozeur","Kebili","Tataouine","Jendouba","Beja","Mahdia"].map(c=><option key={c}>{c}</option>)}
                </select>
                <b>Window</b>
                <input type="number" min={30} max={360} value={minutes} onChange={e=>setMinutes(+e.target.value)} /> min
            </div>

            <div className="card">
                <h4>Pressure over time</h4>
                <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={data.pressure}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="ts" tickFormatter={v=>new Date(v).toLocaleTimeString()} />
                        <YAxis />
                        <Tooltip labelFormatter={v=>new Date(v).toLocaleTimeString()} />
                        <Legend />
                        <Line type="monotone" dataKey="pressure_score" name="Pressure" dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            </div>

            <div className="card">
                <h4>Breaches per minute</h4>
                <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={data.breaches}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="ts" tickFormatter={v=>new Date(v).toLocaleTimeString()} />
                        <YAxis />
                        <Tooltip labelFormatter={v=>new Date(v).toLocaleTimeString()} />
                        <Bar dataKey="breaches" />
                    </BarChart>
                </ResponsiveContainer>
            </div>

            <div className="card">
                <h4>Actions</h4>
                <table className="table">
                    <thead><tr><th>Time</th><th>Action</th><th>Params</th><th>Result</th></tr></thead>
                    <tbody>
                    {data.actions.map((a,i)=>(
                        <tr key={i}>
                            <td>{new Date(a.ts).toLocaleTimeString()}</td>
                            <td>{a.action}</td>
                            <td><code style={{fontSize:12}}>{JSON.stringify(a.params)}</code></td>
                            <td>{a.result}</td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
