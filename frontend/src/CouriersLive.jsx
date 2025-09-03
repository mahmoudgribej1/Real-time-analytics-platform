// src/CouriersLive.jsx
import { useEffect, useState } from "react";
import { API } from "./App";

const fmtClock = (ms) =>
    (typeof ms === "number" && !Number.isNaN(ms))
        ? new Date(ms - 3600000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
        : "—";

const isStale = (ms) => typeof ms === "number" && (Date.now() - ms) > 2 * 60 * 1000; // >2 min

// Courier Status Component
const CourierStatusChip = ({ activeDeliveries }) => {
    const overloaded = activeDeliveries >= 5;
    const busy = activeDeliveries >= 3;
    const active = activeDeliveries > 0;

    if (overloaded) {
        return (
            <div style={{
                padding: "6px 12px",
                borderRadius: "20px",
                fontSize: "11px",
                fontWeight: "600",
                background: "linear-gradient(135deg, #FEE2E2, #FECACA)",
                color: "#991B1B",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                textTransform: "uppercase",
                letterSpacing: "0.5px"
            }}>
                <span style={{ fontSize: "9px" }}>🔥</span>
                {activeDeliveries} Overloaded
            </div>
        );
    }

    if (busy) {
        return (
            <div style={{
                padding: "6px 12px",
                borderRadius: "20px",
                fontSize: "11px",
                fontWeight: "600",
                background: "linear-gradient(135deg, #FEF3C7, #FDE68A)",
                color: "#92400E",
                border: "1px solid rgba(251, 191, 36, 0.3)",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                textTransform: "uppercase",
                letterSpacing: "0.5px"
            }}>
                <span style={{ fontSize: "9px" }}>⚡</span>
                {activeDeliveries} Busy
            </div>
        );
    }

    if (active) {
        return (
            <div style={{
                padding: "6px 12px",
                borderRadius: "20px",
                fontSize: "11px",
                fontWeight: "600",
                background: "linear-gradient(135deg, #D1FAE5, #A7F3D0)",
                color: "#065F46",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                textTransform: "uppercase",
                letterSpacing: "0.5px"
            }}>
                <span style={{ fontSize: "9px" }}>🚀</span>
                {activeDeliveries} Active
            </div>
        );
    }

    return (
        <div style={{
            padding: "6px 12px",
            borderRadius: "20px",
            fontSize: "11px",
            fontWeight: "600",
            background: "var(--surface-3, rgba(75, 85, 99, 0.3))",
            color: "var(--text-2, #9CA3AF)",
            border: "1px solid var(--border, rgba(75, 85, 99, 0.3))",
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            textTransform: "uppercase",
            letterSpacing: "0.5px"
        }}>
            <span style={{ fontSize: "9px" }}>💤</span>
            Idle
        </div>
    );
};

// Speed Chip Component
const SpeedChip = ({ speed }) => {
    if (!speed) {
        return (
            <div style={{
                padding: "6px 12px",
                borderRadius: "20px",
                fontSize: "11px",
                fontWeight: "600",
                background: "var(--surface-3, rgba(75, 85, 99, 0.3))",
                color: "var(--text-2, #9CA3AF)",
                border: "1px solid var(--border, rgba(75, 85, 99, 0.3))",
                textTransform: "uppercase",
                letterSpacing: "0.5px"
            }}>
                —
            </div>
        );
    }

    const fast = speed >= 35;
    const normal = speed >= 25;

    return (
        <div style={{
            padding: "6px 12px",
            borderRadius: "20px",
            fontSize: "11px",
            fontWeight: "600",
            background: fast ? "linear-gradient(135deg, #8B5CF6, #7C3AED)" :
                normal ? "linear-gradient(135deg, #3B82F6, #1E40AF)" :
                    "var(--surface-3, rgba(75, 85, 99, 0.3))",
            color: fast || normal ? "white" : "var(--text-2, #9CA3AF)",
            border: `1px solid ${fast || normal ? "transparent" : "var(--border, rgba(75, 85, 99, 0.3))"}`,
            textTransform: "uppercase",
            letterSpacing: "0.5px"
        }}>
            {Math.round(speed)} km/h
        </div>
    );
};

export default function CouriersLive({ city }) {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [viewMode, setViewMode] = useState("deliveries"); // "deliveries", "speed", "status"

    // hydrate + poll
    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const qs = new URLSearchParams({ limit: "50", ...(city ? { city } : {}) }).toString();
                const r = await fetch(`${API}/api/couriers/live?${qs}`);
                const d = await r.json();
                if (!alive) return;
                // sort: most active first, then most recent
                d.sort(
                    (a, b) =>
                        (b.active_deliveries || 0) - (a.active_deliveries || 0) ||
                        (b.updated_ms || 0) - (a.updated_ms || 0)
                );
                setRows(d);
                setLoading(false);
            } catch {
                /* keep last snapshot */
            }
        };
        load();
        const t = setInterval(load, 7000);
        return () => {
            alive = false;
            clearInterval(t);
        };
    }, [city]);

    const active = rows.filter((r) => (r.active_deliveries || 0) > 0).length;
    const overloaded = rows.filter((r) => (r.active_deliveries || 0) >= 5).length;
    const idle = rows.filter((r) => (r.active_deliveries || 0) === 0).length;

    return (
        <>
            {/* Scoped CSS for courier component only */}
            <style>{`
                @keyframes courier-spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                @keyframes courier-gradientShift {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
                .couriers-container {
                    background: var(--surface-1, #1F2937);
                    border: 1px solid var(--border, rgba(75, 85, 99, 0.3));
                    border-radius: 16px;
                    padding: 24px;
                    box-shadow: var(--shadow-lg, 0 10px 25px rgba(0,0,0,0.2));
                }
                .couriers-container .courier-gradient-border {
                    background: linear-gradient(145deg, #10B981, #059669, #047857, #065F46, #10B981, #34D399, #6EE7B7);
                    background-size: 400% 400%;
                    animation: courier-gradientShift 4s ease infinite;
                    height: 3px;
                    border-radius: 2px;
                    margin-bottom: 20px;
                }
                .couriers-container .courier-tab-button {
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 600;
                    border: none;
                    cursor: pointer;
                    transition: all 0.2s ease-in-out;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .couriers-container .courier-tab-active {
                    background: linear-gradient(135deg, #10B981, #059669);
                    color: white;
                    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
                }
                .couriers-container .courier-tab-inactive {
                    background: var(--surface-3, rgba(75, 85, 99, 0.3));
                    color: var(--text-2, #9CA3AF);
                }
                .couriers-container .courier-tab-inactive:hover {
                    background: var(--surface-hover, rgba(75, 85, 99, 0.5));
                    color: var(--text-1, #F9FAFB);
                }
                .couriers-container .courier-row {
                    display: flex;
                    align-items: center;
                    padding: 16px;
                    margin-bottom: 8px;
                    background: var(--surface-2, rgba(31, 41, 55, 0.5));
                    border: 1px solid var(--border, rgba(75, 85, 99, 0.3));
                    border-radius: 12px;
                    cursor: default;
                    transition: all 0.2s ease-in-out;
                    backdrop-filter: blur(10px);
                }
                .couriers-container .courier-row:hover {
                    background: var(--surface-hover, rgba(55, 65, 81, 0.7));
                    border-color: var(--border-hover, rgba(107, 114, 128, 0.5));
                    transform: translateY(-2px);
                    box-shadow: var(--shadow-lg, 0 8px 25px rgba(0,0,0,0.3));
                }
                .couriers-container .courier-row.overloaded {
                    border-left: 4px solid #EF4444;
                    background: var(--error-bg, rgba(239, 68, 68, 0.1));
                }
                .couriers-container .courier-row.busy {
                    border-left: 4px solid #F59E0B;
                    background: var(--warning-bg, rgba(245, 158, 11, 0.1));
                }
                .couriers-container .courier-row.stale {
                    opacity: 0.6;
                }
                /* Light theme overrides - scoped to courier container only */
                :root[data-theme="light"] .couriers-container,
                body.light .couriers-container,
                html.light .couriers-container {
                    --text-1: #111827;
                    --text-2: #4b5563;
                    --surface-1: #ffffff;
                    --surface-2: #f8fafc;
                    --surface-3: #eef2f7;
                    --surface-hover: #f3f4f6;
                    --border: rgba(0,0,0,0.08);
                    --border-hover: rgba(0,0,0,0.12);
                    --gradient-text: linear-gradient(135deg, #111827, #334155);
                }
                :root[data-theme="light"] .couriers-container .courier-row {
                    background: var(--surface-2);
                    border-color: var(--border);
                }
                :root[data-theme="light"] .couriers-container .courier-row:hover {
                    background: var(--surface-hover);
                    border-color: var(--border-hover);
                }
            `}</style>

            <div className="couriers-container">
                <div className="courier-gradient-border"></div>

                <div style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "24px"
                }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                        <div style={{
                            width: "40px",
                            height: "40px",
                            borderRadius: "12px",
                            background: "linear-gradient(135deg, #10B981, #059669)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "18px"
                        }}>
                            🚴
                        </div>
                        <div>
                            <h3 style={{
                                margin: 0,
                                color: "var(--text-1, #F9FAFB)",
                                fontSize: "24px",
                                fontWeight: "700",
                                background: "var(--gradient-text, linear-gradient(135deg, #F9FAFB, #E5E7EB))",
                                WebkitBackgroundClip: "text",
                                WebkitTextFillColor: "transparent"
                            }}>
                                Courier Activity
                            </h3>
                            <div style={{
                                color: "var(--text-2, #9CA3AF)",
                                fontSize: "14px",
                                marginTop: "2px"
                            }}>
                                Live tracking
                            </div>
                        </div>
                    </div>

                    <div style={{ display: "flex", gap: "8px" }}>
                        <button
                            className={`courier-tab-button ${viewMode === "deliveries" ? "courier-tab-active" : "courier-tab-inactive"}`}
                            onClick={() => setViewMode("deliveries")}
                        >
                            Deliveries
                        </button>
                        <button
                            className={`courier-tab-button ${viewMode === "speed" ? "courier-tab-active" : "courier-tab-inactive"}`}
                            onClick={() => setViewMode("speed")}
                        >
                            Speed
                        </button>
                        <button
                            className={`courier-tab-button ${viewMode === "status" ? "courier-tab-active" : "courier-tab-inactive"}`}
                            onClick={() => setViewMode("status")}
                        >
                            Status
                        </button>
                    </div>
                </div>

                <div style={{
                    display: "flex",
                    gap: "12px",
                    marginBottom: "20px"
                }}>
                    <div style={{
                        background: "linear-gradient(135deg, #10B981, #059669)",
                        color: "white",
                        padding: "8px 16px",
                        borderRadius: "20px",
                        fontSize: "12px",
                        fontWeight: "600",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px"
                    }}>
                        {active} Active
                    </div>
                    {overloaded > 0 && (
                        <div style={{
                            background: "linear-gradient(135deg, #EF4444, #DC2626)",
                            color: "white",
                            padding: "8px 16px",
                            borderRadius: "20px",
                            fontSize: "12px",
                            fontWeight: "600",
                            textTransform: "uppercase",
                            letterSpacing: "0.5px"
                        }}>
                            {overloaded} Overloaded
                        </div>
                    )}
                    <div style={{
                        background: "linear-gradient(135deg, #6B7280, #4B5563)",
                        color: "white",
                        padding: "8px 16px",
                        borderRadius: "20px",
                        fontSize: "12px",
                        fontWeight: "600",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px"
                    }}>
                        {idle} Idle
                    </div>
                </div>

                <div style={{
                    maxHeight: "500px",
                    overflowY: "auto",
                    paddingRight: "8px"
                }}>
                    {loading ? (
                        <div style={{
                            textAlign: "center",
                            padding: "60px 20px",
                            color: "var(--text-2, #6B7280)"
                        }}>
                            <div style={{
                                width: "40px",
                                height: "40px",
                                border: "3px solid var(--border, #374151)",
                                borderTop: "3px solid #10B981",
                                borderRadius: "50%",
                                animation: "courier-spin 1s linear infinite",
                                margin: "0 auto 16px"
                            }}></div>
                            Loading couriers...
                        </div>
                    ) : rows.length > 0 ? (
                        rows.map((c, index) => {
                            const stale = isStale(Number(c.updated_ms));
                            const overloaded = (c.active_deliveries || 0) >= 5;
                            const busy = (c.active_deliveries || 0) >= 3;

                            return (
                                <div
                                    key={c.courier_id}
                                    className={`courier-row ${overloaded ? "overloaded" : busy ? "busy" : ""} ${stale ? "stale" : ""}`}
                                >
                                    <div style={{
                                        display: "flex",
                                        alignItems: "center",
                                        flex: "1",
                                        minWidth: 0
                                    }}>
                                        <div style={{
                                            color: "var(--text-2, #9CA3AF)",
                                            fontSize: "14px",
                                            fontWeight: "600",
                                            minWidth: "20px",
                                            marginRight: "16px"
                                        }}>
                                            {index + 1}
                                        </div>

                                        <div style={{
                                            width: "32px",
                                            height: "32px",
                                            borderRadius: "8px",
                                            background: "linear-gradient(135deg, #3B82F6, #1E40AF)",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            fontWeight: "700",
                                            color: "#fff",
                                            fontSize: "12px",
                                            marginRight: "12px"
                                        }}>
                                            #{c.courier_id}
                                        </div>

                                        <div style={{ flex: "1", minWidth: 0 }}>
                                            <div style={{
                                                color: "var(--text-1, #F9FAFB)",
                                                fontSize: "16px",
                                                fontWeight: "600",
                                                marginBottom: "2px",
                                                whiteSpace: "nowrap",
                                                overflow: "hidden",
                                                textOverflow: "ellipsis"
                                            }}>
                                                {c.courier_name || `Courier #${c.courier_id}`}
                                            </div>
                                            <div style={{
                                                color: "var(--text-2, #9CA3AF)",
                                                fontSize: "13px",
                                                display: "flex",
                                                alignItems: "center",
                                                gap: "8px"
                                            }}>
                                                <span>{c.city_name || "—"}</span>
                                                <span>•</span>
                                                <span>Updated {fmtClock(Number(c.updated_ms))}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "24px"
                                    }}>
                                        <div style={{ textAlign: "right" }}>
                                            <div style={{
                                                color: "var(--text-1, #F9FAFB)",
                                                fontSize: "18px",
                                                fontWeight: "700"
                                            }}>
                                                {viewMode === "deliveries" ? (c.active_deliveries || 0) :
                                                    viewMode === "speed" ? (c.avg_speed_kmh ? `${Math.round(c.avg_speed_kmh)}` : "—") :
                                                        (c.active_deliveries || 0) > 0 ? "Active" : "Idle"}
                                            </div>
                                            <div style={{
                                                color: "var(--text-2, #6B7280)",
                                                fontSize: "11px",
                                                textTransform: "uppercase",
                                                letterSpacing: "0.5px"
                                            }}>
                                                {viewMode === "deliveries" ? "Deliveries" :
                                                    viewMode === "speed" ? "km/h" :
                                                        "Status"}
                                            </div>
                                        </div>

                                        <div style={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: "12px"
                                        }}>
                                            <CourierStatusChip activeDeliveries={c.active_deliveries || 0} />
                                            <SpeedChip speed={c.avg_speed_kmh} />
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    ) : (
                        <div style={{
                            textAlign: "center",
                            padding: "60px 20px",
                            color: "var(--text-2, #6B7280)"
                        }}>
                            <div style={{ fontSize: "48px", marginBottom: "16px" }}>🚴</div>
                            <div style={{
                                fontSize: "16px",
                                fontWeight: "600",
                                marginBottom: "8px",
                                color: "var(--text-1, #F9FAFB)"
                            }}>
                                No couriers found
                            </div>
                            <div style={{ fontSize: "14px" }}>
                                Couriers will appear here when they become active
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}