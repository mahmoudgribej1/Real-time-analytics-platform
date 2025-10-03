import { useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { API } from "./App";

// Fix Leaflet default marker icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
    iconUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
    shadowUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

export default function DeliveryRouteMap({ orderId }) {
    const [routeData, setRouteData] = useState(null);
    const [loading, setLoading] = useState(true);

    // animation state
    const [animating, setAnimating] = useState(false);
    const [progress, setProgress] = useState(0);
    const [courierPos, setCourierPos] = useState(null);
    const stepRef = useRef(null);

    useEffect(() => {
        if (!orderId) return;

        setLoading(true);
        fetch(`${API}/api/routes/${orderId}`)
            .then((res) => res.json())
            .then((data) => {
                setRouteData(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Failed to load route:", err);
                setLoading(false);
            });

        // stop any previous animation when order changes
        return () => {
            if (stepRef.current) {
                clearInterval(stepRef.current);
                stepRef.current = null;
            }
            setAnimating(false);
            setProgress(0);
            setCourierPos(null);
        };
    }, [orderId]);

    if (loading) return <div className="card">Loading route...</div>;
    if (!routeData) return <div className="card">No route data available.</div>;
    if (!routeData.route_geometry || !routeData.route_geometry.coordinates?.length) {
        return <div className="card">Route shape is missing.</div>;
    }

    const routeCoords = routeData.route_geometry.coordinates.map((c) => [
        c[1],
        c[0],
    ]); // [lng,lat] -> [lat,lng]

    const center = [
        routeData.restaurant_lat ?? routeCoords[0][0],
        routeData.restaurant_lon ?? routeCoords[0][1],
    ];

    // fit-to-bounds once per render
    const whenMapReady = (map) => {
        const bounds = L.latLngBounds(routeCoords);
        map.fitBounds(bounds, { padding: [50, 50] });
    };

    const animateDelivery = () => {
        if (animating) return;

        const points =
            Array.isArray(routeData.waypoints) && routeData.waypoints.length > 1
                ? routeData.waypoints.map((w) => [w.lat, w.lon])
                : routeCoords;

        let idx = 0;
        setAnimating(true);
        setCourierPos(points[0]);
        setProgress(0);

        if (stepRef.current) clearInterval(stepRef.current);
        stepRef.current = setInterval(() => {
            idx += 1;
            if (idx >= points.length) {
                clearInterval(stepRef.current);
                stepRef.current = null;
                setAnimating(false);
                setProgress(100);
                return;
            }
            setCourierPos(points[idx]);
            setProgress(Math.round((idx / (points.length - 1)) * 100));
        }, 300); // 300 ms per step, tune as needed
    };

    return (
        <div className="card" style={{ position: "relative" }}>
            <div style={{ marginBottom: 16 }}>
                <h3 style={{ margin: 0 }}>Delivery Route, Order #{orderId}</h3>
                <div style={{ fontSize: 14, color: "var(--muted)", marginTop: 4 }}>
                    {routeData.courier_name} • {routeData.city_name} •{" "}
                    {routeData.total_distance_km} km • {routeData.actual_duration_min} min
                </div>
            </div>

            <MapContainer
                center={center}
                zoom={13}
                style={{ height: "500px", borderRadius: 8 }}
                whenCreated={whenMapReady}
            >
                <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution='&copy; OpenStreetMap'
                />

                <Marker position={[routeData.restaurant_lat, routeData.restaurant_lon]}>
                    <Popup>
                        <b>{routeData.restaurant_name}</b>
                        <br />
                        Restaurant
                    </Popup>
                </Marker>

                <Marker position={[routeData.delivery_latitude, routeData.delivery_longitude]}>
                    <Popup>Delivery destination</Popup>
                </Marker>

                <Polyline positions={routeCoords} pathOptions={{ color: "#3b82f6", weight: 4 }} />

                {courierPos ? (
                    <Marker position={courierPos}>
                        <Popup>Courier</Popup>
                    </Marker>
                ) : null}
            </MapContainer>

            <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
                <button className="btn" onClick={animateDelivery} disabled={animating}>
                    {animating ? "Animating..." : "Replay delivery"}
                </button>
                {animating ? (
                    <div style={{ flex: 1 }}>
                        <div
                            style={{
                                height: 8,
                                background: "var(--bg-muted)",
                                borderRadius: 4,
                                overflow: "hidden",
                            }}
                        >
                            <div
                                style={{
                                    width: `${progress}%`,
                                    height: "100%",
                                    background: "var(--primary)",
                                    transition: "width 0.3s",
                                }}
                            />
                        </div>
                        <div style={{ fontSize: 12, marginTop: 4, color: "var(--muted)" }}>
                            {progress}% complete
                        </div>
                    </div>
                ) : null}
            </div>
        </div>
    );
}
