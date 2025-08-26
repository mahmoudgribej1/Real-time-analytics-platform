import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useCity } from "./CityContext";

const API = import.meta.env.VITE_API || `http://${window.location.hostname}:8001`;

export default function RestaurantMap(){
    const { city } = useCity();
    const [pts, setPts] = useState([]);

    useEffect(()=>{
        let alive = true;
        const load = async ()=>{
            const url = `${API}/api/restaurants/load_map?${city ? `city=${encodeURIComponent(city)}&` : ""}limit=400`;
            const d = await (await fetch(url)).json();
            if (alive) setPts(Array.isArray(d)? d : []);
        };
        load(); const t = setInterval(load, 15000);
        return ()=>{ alive = false; clearInterval(t); };
    }, [city]);

    const center = pts.length ? [pts[0].lat, pts[0].lon] : [36.8, 10.1];

    return (
        <div className="card card-lg">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Restaurant Load (map)</h3>
                <span className="badge">{pts.length} pins</span>
            </div>
            <div style={{height:420, borderRadius:12, overflow:"hidden"}}>
                <MapContainer center={center} zoom={7} style={{height:"100%", width:"100%"}}>
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    {pts.map((p,i)=>{
                        const s = Number(p.load_score)||0;
                        const r = 6 + s/10;
                        const col = s >= 80 ? "#ef4444" : s >= 60 ? "#f59e0b" : "#22d3ee";
                        return (
                            <CircleMarker key={i} center={[p.lat, p.lon]} radius={r}
                                          pathOptions={{ color: col, fillColor: col, fillOpacity: 0.35 }}>
                                <Tooltip>
                                    <div><b>{p.restaurant_name}</b> · {p.city_name}</div>
                                    <div>Load {Math.round(s)}</div>
                                    <div>Orders15 {p.orders15} · Prep {Math.round(p.prep||0)}m</div>
                                </Tooltip>
                            </CircleMarker>
                        );
                    })}
                </MapContainer>
            </div>
        </div>
    );
}
