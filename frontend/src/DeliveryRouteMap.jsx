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
    const [error, setError] = useState(null);

    // animation state
    const [animating, setAnimating] = useState(false);
    const [progress, setProgress] = useState(0);
    const [courierPos, setCourierPos] = useState(null);
    const stepRef = useRef(null);

    useEffect(() => {
        if (!orderId || !Number.isFinite(Number(orderId)) || Number(orderId) <= 0) {
            setError("Invalid order ID");
            setLoading(false);
            return;
        }

        setLoading(true);
        setError(null);
        setRouteData(null);

        fetch(`${API}/api/routes/${orderId}`)
            .then((res) => {
                if (!res.ok) {
                    if (res.status === 404) {
                        throw new Error("Route not found for this order");
                    } else if (res.status === 422) {
                        throw new Error("Invalid order ID format");
                    } else {
                        throw new Error(`HTTP ${res.status}`);
                    }
                }
                return res.json();
            })
            .then((data) => {
                if (!data || !data.route_geometry || !data.route_geometry.coordinates?.length) {
                    throw new Error("Route data is incomplete or missing");
                }
                setRouteData(data);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Failed to load route:", err);
                setError(err.message || "Failed to load route");
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

    if (loading) {
        return (
            <div className="card">
                <div style={{
                    textAlign: "center",
                    padding: 48,
                    color: "var(--muted)"
                }}>
                    <div style={{ fontSize: 16, marginBottom: 8 }}>Loading route...</div>
                    <div style={{ fontSize: 12 }}>Order #{orderId}</div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="card">
                <div style={{
                    textAlign: "center",
                    padding: 48,
                    background: "var(--bg-muted)",
                    borderRadius: 8
                }}>
                    <div style={{ fontSize: 16, color: "var(--danger)", marginBottom: 8 }}>
                        Error: {error}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted)" }}>
                        Order #{orderId}
                    </div>
                </div>
            </div>
        );
    }

    if (!routeData) {
        return (
            <div className="card">
                <div style={{
                    textAlign: "center",
                    padding: 48,
                    color: "var(--muted)",
                    background: "var(--bg-muted)",
                    borderRadius: 8
                }}>
                    No route data available for Order #{orderId}
                </div>
            </div>
        );
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
        try {
            const bounds = L.latLngBounds(routeCoords);
            map.fitBounds(bounds, { padding: [50, 50] });
        } catch (e) {
            console.error("Failed to fit bounds:", e);
        }
    };

    const animateDelivery = () => {
        if (animating) return;

        const points =
            Array.isArray(routeData.waypoints) && routeData.waypoints.length > 1
                ? routeData.waypoints.map((w) => [w.lat, w.lon])
                : routeCoords;

        if (points.length === 0) {
            console.warn("No points to animate");
            return;
        }

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
        }, 300); // 300 ms per step
    };

    return (
        <div className="card" style={{ position: "relative" }}>
            <div style={{ marginBottom: 16 }}>
                <h3 style={{ margin: 0, marginBottom: 4 }}>Delivery Route, Order #{orderId}</h3>
                <div style={{ fontSize: 14, color: "var(--muted)" }}>
                    {routeData.courier_name ?? "Unknown Courier"} • {routeData.city_name ?? "Unknown City"} • {routeData.total_distance_km ?? "?"} km • {routeData.actual_duration_min ?? "?"} min
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

                {routeData.restaurant_lat && routeData.restaurant_lon ? (
                    <Marker position={[routeData.restaurant_lat, routeData.restaurant_lon]}>
                        <Popup>
                            <b>{routeData.restaurant_name ?? "Restaurant"}</b>
                            <br />
                            Pickup location
                        </Popup>
                    </Marker>
                ) : null}

                {routeData.delivery_latitude && routeData.delivery_longitude ? (
                    <Marker position={[routeData.delivery_latitude, routeData.delivery_longitude]}>
                        <Popup>Delivery destination</Popup>
                    </Marker>
                ) : null}

                <Polyline positions={routeCoords} pathOptions={{ color: "#3b82f6", weight: 4 }} />

                {courierPos ? (
                    <Marker position={courierPos}>
                        <Popup>Courier (animated)</Popup>
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