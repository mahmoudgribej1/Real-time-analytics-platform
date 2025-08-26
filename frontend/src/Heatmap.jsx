import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function Heatmap(){
    const [pts, setPts] = useState([]);
    useEffect(()=>{
        let alive=true;
        const load=async ()=>{
            const r = await fetch(`${API}/api/heatmap/cities?minutes=60`);
            const d = await r.json(); if (!alive) return; setPts(d);
        };
        load(); const t=setInterval(load, 10000);
        return ()=>{ alive=false; clearInterval(t); };
    },[]);
    const center = pts.length ? [pts[0].lat || 36.8, pts[0].lon || 10.1] : [36.8, 10.1];

    return (
        <div className="card card-lg">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Delivery Heatmap</h3>
                <span className="badge">{pts.filter(p=>p.opm>0).length} Active</span>
            </div>
            <div style={{height:360, borderRadius:12, overflow:"hidden"}}>
                <MapContainer center={center} zoom={6} style={{height:"100%", width:"100%"}}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    {pts.map((p,i)=>{
                        const val = p.pressure || 0;
                        const r = Math.max(6, Math.min(24, val/5 + 6));
                        const col = val >= 85 ? "#ef4444" : val >= 70 ? "#f59e0b" : "#22d3ee";
                        return (
                            <CircleMarker key={i} center={[p.lat, p.lon]} radius={r} pathOptions={{color:col, fillColor:col, fillOpacity:0.35}}>
                                <Tooltip>{p.city_name}: pressure {Math.round(val)}</Tooltip>
                            </CircleMarker>
                        );
                    })}
                </MapContainer>
            </div>
            <div style={{marginTop:10, display:"flex", gap:8, flexWrap:"wrap"}}>
                {pts.sort((a,b)=> (b.pressure||0)-(a.pressure||0)).slice(0,6).map((p,i)=>(
                    <span key={i} className="badge" style={{background:"rgba(249,115,22,.14)",borderColor:"rgba(249,115,22,.3)", color:"#fdba74"}}>
            ⚡ {p.city_name} · {Math.round(p.pressure||0)}
          </span>
                ))}
            </div>
        </div>
    );
}
