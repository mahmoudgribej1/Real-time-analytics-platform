import { useEffect, useState } from "react";
import { API } from "./App";
// If your wsBus DOES export useWSEvents, leave this:
import { useWSEvents } from "./wsBus";
import RestaurantDrawer from "./RestaurantDrawer";

/* ---------- helpers ---------- */
const fmtClock = (ms) =>
    (typeof ms === "number" && !Number.isNaN(ms))
        ? new Date(ms - 3600000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })
        : "—";

const fmtAge = (ms) => {
    if (!ms) return "—";
    const age = Date.now() - ms;
    const m = Math.floor(age / 60000);
    if (m <= 0) return "now";
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m ago`;
};
const isRowStale = (ms) => typeof ms === "number" && Date.now() - ms > 2 * 60 * 1000;

// Enhanced Pause Button Component
const PauseButton = ({ restaurant, pauseState, onPause }) => {
    const p = pauseState[restaurant.restaurant_id];
    const remainingMin = p?.until ? Math.max(0, Math.ceil((p.until - Date.now()) / 60000)) : 0;
    const isPaused = p?.until && Date.now() < p.until;

    if (isPaused) {
        return (
            <div
                style={{
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
                    minWidth: "80px",
                    justifyContent: "center",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px"
                }}
                title={`Paused until ${fmtClock(p.until)}`}
            >
                {p.pending ? (
                    <>
                        <div style={{
                            width: "8px",
                            height: "8px",
                            border: "2px solid currentColor",
                            borderTop: "2px solid transparent",
                            borderRadius: "50%",
                            animation: "spin 1s linear infinite"
                        }}></div>
                        Pausing
                    </>
                ) : (
                    <>
                        <span style={{ fontSize: "9px" }}>⏸</span>
                        {remainingMin}m left
                    </>
                )}
            </div>
        );
    }

    if (p?.error) {
        return (
            <div
                style={{
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
                }}
            >
                <span style={{ fontSize: "9px" }}>⚠</span>
                Failed
            </div>
        );
    }

    return (
        <button
            style={{
                padding: "6px 12px",
                borderRadius: "20px",
                fontSize: "11px",
                fontWeight: "600",
                background: "linear-gradient(135deg, #1F2937, #374151)",
                color: "#F9FAFB",
                border: "1px solid rgba(75, 85, 99, 0.5)",
                cursor: "pointer",
                transition: "all 0.2s ease-in-out",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                minWidth: "80px",
                justifyContent: "center",
                textTransform: "uppercase",
                letterSpacing: "0.5px"
            }}
            onClick={(e) => {
                e.stopPropagation();
                onPause(restaurant.restaurant_id);
            }}
            title="Pause new orders for 15 minutes"
            onMouseEnter={(e) => {
                e.target.style.background = "linear-gradient(135deg, #374151, #4B5563)";
                e.target.style.transform = "translateY(-1px)";
                e.target.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
            }}
            onMouseLeave={(e) => {
                e.target.style.background = "linear-gradient(135deg, #1F2937, #374151)";
                e.target.style.transform = "translateY(0)";
                e.target.style.boxShadow = "none";
            }}
        >
            <span style={{ fontSize: "9px" }}>⏸</span>
            Pause 15m
        </button>
    );
};

// Restaurant Icon Component
const RestaurantIcon = ({ name }) => {
    const getIcon = (name) => {
        if (!name) return "🏪";
        const n = name.toLowerCase();
        if (n.includes('pizza')) return "🍕";
        if (n.includes('burger')) return "🍔";
        if (n.includes('sushi')) return "🍣";
        if (n.includes('taco')) return "🌮";
        if (n.includes('coffee') || n.includes('café')) return "☕";
        if (n.includes('bistro') || n.includes('restaurant')) return "🍽️";
        if (n.includes('chicken')) return "🍗";
        if (n.includes('sandwich')) return "🥪";
        if (n.includes('noodle') || n.includes('ramen')) return "🍜";
        return "🏪";
    };

    return (
        <div style={{
            width: "32px",
            height: "32px",
            borderRadius: "8px",
            background: "linear-gradient(135deg, #FBB040, #F59E0B)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "16px",
            marginRight: "12px"
        }}>
            {getIcon(name)}
        </div>
    );
};

/* ============================================================ */
export default function RestaurantsLive({ city }) {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [sel, setSel] = useState(null);
    const [viewMode, setViewMode] = useState("orders"); // "orders", "prep", "status"

    // NEW: simple ticker so the countdown refreshes without WS
    const [, setTick] = useState(0);
    useEffect(() => {
        const t = setInterval(() => setTick((x) => x + 1), 30_000);
        return () => clearInterval(t);
    }, []);

    // NEW: track pause state by restaurant_id
    const [pauseState, setPauseState] = useState({}); // {[id]: {until:number, pending?:bool, error?:bool}}

    const PAUSE_MIN = 15;
    const pauseRestaurant = async (id) => {
        // optimistic UI
        const optimisticUntil = Date.now() + PAUSE_MIN * 60 * 1000;
        setPauseState((s) => ({ ...s, [id]: { until: optimisticUntil, pending: true } }));
        try {
            const r = await fetch(`${API}/api/restaurants/pause`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ restaurant_id: id, minutes: PAUSE_MIN }),
            });
            let d = null;
            try { d = await r.json(); } catch {} // tolerate 204/no-json
            const until = d?.until ? Date.parse(d.until) : optimisticUntil;
            setPauseState((s) => ({ ...s, [id]: { until, pending: false } }));
        } catch {
            // brief error flash then revert
            setPauseState((s) => ({ ...s, [id]: { error: true } }));
            setTimeout(() => setPauseState((s) => {
                const n = { ...s }; delete n[id]; return n;
            }), 1200);
        }
    };

    // ---- Initial + periodic fetch
    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const qs = new URLSearchParams({ limit: "50", ...(city ? { city } : {}) }).toString();
                const r = await fetch(`${API}/api/restaurants/live?${qs}`);
                const d = await r.json();
                if (!alive) return;
                setRows(Array.isArray(d) ? d : []);
                const bootstrap = {};
                (d || []).forEach(r => {
                    const ms = Number(r.paused_until_ms);
                    if (ms && ms > Date.now()) bootstrap[r.restaurant_id] = { until: ms, pending: false };
                });
                setPauseState(prev => ({ ...bootstrap, ...prev }));
                setLoading(false);
            } catch {
                /* keep last snapshot */
            }
        };
        load();
        const t = setInterval(load, 7000);
        return () => { alive = false; clearInterval(t); };
    }, [city]);

    // Optional WS stream
    let wsEvents = [];
    try { wsEvents = useWSEvents?.() || []; } catch {}
    useEffect(() => {
        if (!wsEvents.length) return;
        const e = wsEvents[0];
        if (e?.type !== "restaurant_update") return;
        const p = e.payload || {};
        const rid = p.restaurant_id;
        if (!rid) return;
        setRows((prev) => {
            const idx = prev.findIndex((r) => r.restaurant_id === rid);
            const base = idx >= 0 ? prev[idx] : { restaurant_id: rid };
            const merged = {
                ...base,
                city_name: base.city_name || e.city || base.city_name,
                restaurant_name: base.restaurant_name,
                orders_last_15m: Number(p.orders_last_15m ?? base.orders_last_15m ?? 0),
                avg_prep_time_min: Number(p.avg_prep_time_last_hour ?? base.avg_prep_time_min ?? 0),
                is_promo_active: !!p.is_promo_active,
                updated_ms: Number(p.report_timestamp || Date.now()),
            };
            const next = [...prev];
            if (idx >= 0) next[idx] = merged;
            else next.unshift(merged);
            return next.slice(0, 50);
        });
    }, [wsEvents]);

    const activeCount = rows.filter(r => !pauseState[r.restaurant_id]?.until || Date.now() >= pauseState[r.restaurant_id].until).length;
    const pausedCount = rows.filter(r => pauseState[r.restaurant_id]?.until && Date.now() < pauseState[r.restaurant_id].until).length;

    return (
        <>
            {/* Add CSS for animations and theme-aware styling */}
            <style>{`
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                @keyframes gradientShift {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
                .restaurants-container {
                    background: var(--surface-1, #1F2937);
                    border: 1px solid var(--border, rgba(75, 85, 99, 0.3));
                    border-radius: 16px;
                    padding: 24px;
                    box-shadow: var(--shadow-lg, 0 10px 25px rgba(0,0,0,0.2));
                }
                .gradient-border {
                    background: linear-gradient(145deg, #3B82F6, #8B5CF6, #EC4899);
                    background-size: 300% 300%;
                    animation: gradientShift 3s ease infinite;
                    height: 3px;
                    border-radius: 2px;
                    margin-bottom: 20px;
                }
                .tab-button {
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
                .tab-active {
                    background: linear-gradient(135deg, #3B82F6, #1E40AF);
                    color: white;
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                }
                .tab-inactive {
                    background: var(--surface-3, rgba(75, 85, 99, 0.3));
                    color: var(--text-2, #9CA3AF);
                }
                .tab-inactive:hover {
                    background: var(--surface-hover, rgba(75, 85, 99, 0.5));
                    color: var(--text-1, #F9FAFB);
                }
                .restaurant-row {
                    display: flex;
                    align-items: center;
                    padding: 16px;
                    margin-bottom: 8px;
                    background: var(--surface-2, rgba(31, 41, 55, 0.5));
                    border: 1px solid var(--border, rgba(75, 85, 99, 0.3));
                    border-radius: 12px;
                    cursor: pointer;
                    transition: all 0.2s ease-in-out;
                    backdrop-filter: blur(10px);
                }
                .restaurant-row:hover {
                    background: var(--surface-hover, rgba(55, 65, 81, 0.7));
                    border-color: var(--border-hover, rgba(107, 114, 128, 0.5));
                    transform: translateY(-2px);
                    box-shadow: var(--shadow-lg, 0 8px 25px rgba(0,0,0,0.3));
                }
                .restaurant-row.critical {
                    border-left: 4px solid #EF4444;
                    background: var(--error-bg, rgba(239, 68, 68, 0.1));
                }
                .restaurant-row.warn {
                    border-left: 4px solid #F59E0B;
                    background: var(--warning-bg, rgba(245, 158, 11, 0.1));
                }
                .restaurant-row.stale {
                    opacity: 0.6;
                }
                /* --- Light theme overrides for this component only --- */
                :root[data-theme="light"] .restaurants-container,
                body.light .restaurants-container,
                html.light .restaurants-container {
                  /* readable text on light surfaces */
                  --text-1: #111827;      /* primary text */
                  --text-2: #4b5563;      /* secondary text */
                
                  /* light surfaces + borders */
                  --surface-1: #ffffff;
                  --surface-2: #f8fafc;
                  --surface-3: #eef2f7;
                  --surface-hover: #f3f4f6;
                  --border: rgba(0,0,0,0.08);
                  --border-hover: rgba(0,0,0,0.12);
                
                  /* darker heading gradient for light bg */
                  --gradient-text: linear-gradient(135deg, #111827, #334155);
                }
                
                /* optional: ensure rows look lifted in light mode */
                :root[data-theme="light"] .restaurants-container .restaurant-row {
                  background: var(--surface-2);
                  border-color: var(--border);
                }
                :root[data-theme="light"] .restaurants-container .restaurant-row:hover {
                  background: var(--surface-hover);
                  border-color: var(--border-hover);
                }

            `}</style>

            <div className="restaurants-container">
                <div className="gradient-border"></div>

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
                            background: "linear-gradient(135deg, #3B82F6, #1E40AF)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: "18px"
                        }}>
                            🏪
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
                                Live Restaurants
                            </h3>
                            <div style={{
                                color: "var(--text-2, #9CA3AF)",
                                fontSize: "14px",
                                marginTop: "2px"
                            }}>
                                Last 24 hours
                            </div>
                        </div>
                    </div>

                    <div style={{ display: "flex", gap: "8px" }}>
                        <button
                            className={`tab-button ${viewMode === "orders" ? "tab-active" : "tab-inactive"}`}
                            onClick={() => setViewMode("orders")}
                        >
                            Orders
                        </button>
                        <button
                            className={`tab-button ${viewMode === "prep" ? "tab-active" : "tab-inactive"}`}
                            onClick={() => setViewMode("prep")}
                        >
                            Prep Time
                        </button>
                        <button
                            className={`tab-button ${viewMode === "status" ? "tab-active" : "tab-inactive"}`}
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
                        {activeCount} Active
                    </div>
                    <div style={{
                        background: "linear-gradient(135deg, #F59E0B, #D97706)",
                        color: "white",
                        padding: "8px 16px",
                        borderRadius: "20px",
                        fontSize: "12px",
                        fontWeight: "600",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px"
                    }}>
                        {pausedCount} Paused
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
                                borderTop: "3px solid #3B82F6",
                                borderRadius: "50%",
                                animation: "spin 1s linear infinite",
                                margin: "0 auto 16px"
                            }}></div>
                            Loading restaurants...
                        </div>
                    ) : rows.length > 0 ? (
                        rows.map((r, index) => {
                            const updatedMs = Number(r.updated_ms ?? (r.last_update ? Date.parse(r.last_update) : NaN));
                            const stale = isRowStale(updatedMs);
                            const isPaused = pauseState[r.restaurant_id]?.until && Date.now() < pauseState[r.restaurant_id].until;

                            return (
                                <div
                                    key={r.restaurant_id}
                                    className={`restaurant-row ${r.critical ? "critical" : r.overloaded ? "warn" : ""} ${stale ? "stale" : ""}`}
                                    onClick={() => setSel(r)}
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

                                        <RestaurantIcon name={r.restaurant_name} />

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
                                                {r.restaurant_name}
                                            </div>
                                            <div style={{
                                                color: "var(--text-2, #9CA3AF)",
                                                fontSize: "13px",
                                                display: "flex",
                                                alignItems: "center",
                                                gap: "8px"
                                            }}>
                                                <span>{r.city_name}</span>
                                                {r.is_promo_active && (
                                                    <span style={{
                                                        background: "linear-gradient(135deg, #8B5CF6, #7C3AED)",
                                                        color: "white",
                                                        padding: "2px 6px",
                                                        borderRadius: "8px",
                                                        fontSize: "10px",
                                                        fontWeight: "600",
                                                        textTransform: "uppercase"
                                                    }}>
                                                        Promo
                                                    </span>
                                                )}
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
                                                {viewMode === "orders" ? r.orders_last_15m || 0 :
                                                    viewMode === "prep" ? (r.avg_prep_time_min ? Math.round(r.avg_prep_time_min) : 0) :
                                                        isPaused ? "Paused" : "Active"}
                                            </div>
                                            <div style={{
                                                color: "var(--text-2, #6B7280)",
                                                fontSize: "11px",
                                                textTransform: "uppercase",
                                                letterSpacing: "0.5px"
                                            }}>
                                                {viewMode === "orders" ? "Orders" :
                                                    viewMode === "prep" ? "Minutes" :
                                                        "Status"}
                                            </div>
                                        </div>

                                        <PauseButton
                                            restaurant={r}
                                            pauseState={pauseState}
                                            onPause={pauseRestaurant}
                                        />
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
                            <div style={{ fontSize: "48px", marginBottom: "16px" }}>🏪</div>
                            <div style={{
                                fontSize: "16px",
                                fontWeight: "600",
                                marginBottom: "8px",
                                color: "var(--text-1, #F9FAFB)"
                            }}>
                                No restaurants found
                            </div>
                            <div style={{ fontSize: "14px" }}>
                                Restaurants will appear here when they become active
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <RestaurantDrawer restaurant={sel} onClose={() => setSel(null)} />
        </>
    );
}