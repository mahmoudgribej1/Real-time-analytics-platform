import {useState} from "react";
import {useQuery} from "@tanstack/react-query";
import {API} from "./App";
import {useCity} from "./CityContext";

const fmtTND = (v) => (v ?? 0).toLocaleString("en-TN", {style:"currency", currency:"TND", maximumFractionDigits:0});

export default function TopEntities() {
    const { city } = useCity();
    const [rMetric, setRMetric] = useState("gmv");     // gmv | orders | reviews
    const [dMetric, setDMetric] = useState("units");   // units | revenue
    const minutes = 1440;

    const { data: restaurants = [], isLoading: rLoad } = useQuery({
        queryKey: ["top-rest", {minutes, city, metric: rMetric}],
        queryFn: async () => {
            const qs = new URLSearchParams({ minutes, metric: rMetric, ...(city ? {city} : {}), limit: 10 });
            const r = await fetch(`${API}/api/top/restaurants?${qs}`);
            return r.json();
        },
        staleTime: 30_000,
    });

    const { data: dishes = [], isLoading: dLoad } = useQuery({
        queryKey: ["top-dish", {minutes, city, metric: dMetric}],
        queryFn: async () => {
            const qs = new URLSearchParams({ minutes, metric: dMetric, ...(city ? {city} : {}), limit: 8 });
            const r = await fetch(`${API}/api/top/dishes?${qs}`);
            return r.json();
        },
        staleTime: 30_000,
    });

    const getRankIcon = (index) => {
        if (index === 0) return "🏆";
        if (index === 1) return "🥈";
        if (index === 2) return "🥉";
        return `${index + 1}`;
    };

    const getPerformanceColor = (value, max, isRevenue = false) => {
        const ratio = value / max;
        if (ratio >= 0.8) return isRevenue ? "#10b981" : "#3b82f6";
        if (ratio >= 0.6) return isRevenue ? "#059669" : "#2563eb";
        if (ratio >= 0.4) return isRevenue ? "#047857" : "#1d4ed8";
        return "var(--muted)";
    };

    const maxRestaurantValue = restaurants.length > 0 ?
        Math.max(...restaurants.map(r =>
            rMetric === "gmv" ? r.gmv :
                rMetric === "orders" ? r.orders :
                    r.reviews
        )) : 0;

    const maxDishValue = dishes.length > 0 ?
        Math.max(...dishes.map(d =>
            dMetric === "units" ? d.units : d.revenue
        )) : 0;

    return (
        <div className="card" style={{
            background: "linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%)",
            border: "1px solid var(--border)",
            borderRadius: "16px",
            padding: "24px"
        }}>
            <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "20px"
            }}>
                <h3 style={{
                    margin: 0,
                    fontSize: "1.5rem",
                    fontWeight: "700",
                    background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text"
                }}>
                    Top Today
                </h3>
                <div style={{
                    fontSize: "0.85rem",
                    color: "var(--muted)",
                    background: "var(--surface-3)",
                    padding: "6px 12px",
                    borderRadius: "20px",
                    border: "1px solid var(--border)"
                }}>
                    Last 24 hours
                </div>
            </div>

            <div style={{display:"grid", gridTemplateColumns:"1.2fr 1fr", gap: 24}}>
                {/* Restaurants */}
                <div className="card" style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    padding: "20px",
                    position: "relative",
                    overflow: "hidden"
                }}>
                    <div style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "3px",
                        background: "linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899)"
                    }} />

                    <div style={{
                        display:"flex",
                        justifyContent:"space-between",
                        alignItems:"center",
                        marginBottom: 16
                    }}>
                        <div style={{display: "flex", alignItems: "center", gap: 8}}>
                            <span style={{fontSize: "1.2rem"}}>🍽️</span>
                            <b style={{fontSize: "1.1rem", color: "var(--text-1)"}}>Restaurants</b>
                        </div>

                        <div style={{
                            display:"flex",
                            gap: 4,
                            background: "var(--surface-3)",
                            padding: "4px",
                            borderRadius: "8px",
                            border: "1px solid var(--border)"
                        }}>
                            <button
                                onClick={()=>setRMetric("gmv")}
                                className={`btn ${rMetric==='gmv'?'':'ghost'}`}
                                style={{
                                    fontSize: "0.8rem",
                                    padding: "6px 12px",
                                    borderRadius: "6px",
                                    ...(rMetric === 'gmv' ? {
                                        background: "linear-gradient(135deg, #3b82f6, #2563eb)",
                                        color: "white",
                                        boxShadow: "0 2px 4px rgba(59, 130, 246, 0.3)"
                                    } : {})
                                }}
                            >
                                GMV
                            </button>
                            <button
                                onClick={()=>setRMetric("orders")}
                                className={`btn ${rMetric==='orders'?'':'ghost'}`}
                                style={{
                                    fontSize: "0.8rem",
                                    padding: "6px 12px",
                                    borderRadius: "6px",
                                    ...(rMetric === 'orders' ? {
                                        background: "linear-gradient(135deg, #10b981, #059669)",
                                        color: "white",
                                        boxShadow: "0 2px 4px rgba(16, 185, 129, 0.3)"
                                    } : {})
                                }}
                            >
                                Orders
                            </button>
                            <button
                                onClick={()=>setRMetric("reviews")}
                                className={`btn ${rMetric==='reviews'?'':'ghost'}`}
                                style={{
                                    fontSize: "0.8rem",
                                    padding: "6px 12px",
                                    borderRadius: "6px",
                                    ...(rMetric === 'reviews' ? {
                                        background: "linear-gradient(135deg, #f59e0b, #d97706)",
                                        color: "white",
                                        boxShadow: "0 2px 4px rgba(245, 158, 11, 0.3)"
                                    } : {})
                                }}
                            >
                                Reviews
                            </button>
                        </div>
                    </div>

                    <div style={{display:"grid", gridTemplateColumns:"1fr", gap: 8}}>
                        {(rLoad ? Array.from({length:8}).map((_,i)=>({skeleton:true,id:i})) : restaurants).map((r,i)=>{
                            const value = rMetric === "gmv" ? r.gmv : rMetric === "orders" ? r.orders : r.reviews;
                            const displayValue = rMetric === "gmv" ? fmtTND(r.gmv) :
                                rMetric === "orders" ? (r.orders ?? 0).toLocaleString() :
                                    `${r.reviews ?? 0}`;

                            return (
                                <div key={r.entity_id ?? i} style={{
                                    display:"flex",
                                    alignItems:"center",
                                    gap: 12,
                                    padding: "12px 16px",
                                    background: i % 2 === 0 ? "var(--surface-3)" : "var(--surface-1)",
                                    border: "1px solid var(--border)",
                                    borderRadius: "10px",
                                    transition: "all 0.2s ease",
                                    position: "relative",
                                    overflow: "hidden"
                                }}
                                     onMouseEnter={(e) => {
                                         e.currentTarget.style.transform = "translateY(-2px)";
                                         e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)";
                                     }}
                                     onMouseLeave={(e) => {
                                         e.currentTarget.style.transform = "translateY(0)";
                                         e.currentTarget.style.boxShadow = "none";
                                     }}
                                >
                                    <div style={{
                                        minWidth: "32px",
                                        height: "32px",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        background: i < 3 ? "linear-gradient(135deg, #fbbf24, #f59e0b)" : "var(--surface-2)",
                                        borderRadius: "8px",
                                        fontSize: i < 3 ? "1rem" : "0.9rem",
                                        fontWeight: "700",
                                        color: i < 3 ? "white" : "var(--text-1)"
                                    }}>
                                        {getRankIcon(i)}
                                    </div>

                                    <div style={{
                                        flex: 1,
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        fontWeight: "600",
                                        color: "var(--text-1)"
                                    }}>
                                        {r.skeleton ?
                                            <span className="skeleton" style={{display:"inline-block",width:120,height:14}}/> :
                                            r.entity_name
                                        }
                                    </div>

                                    <div style={{
                                        fontWeight: "700",
                                        fontSize: "0.9rem",
                                        color: getPerformanceColor(value, maxRestaurantValue)
                                    }}>
                                        {r.skeleton ?
                                            <span className="skeleton" style={{display:"inline-block",width:60,height:14}}/> :
                                            displayValue
                                        }
                                    </div>

                                    {/* Performance indicator bar */}
                                    {!r.skeleton && (
                                        <div style={{
                                            position: "absolute",
                                            bottom: 0,
                                            left: 0,
                                            height: "3px",
                                            width: `${(value / maxRestaurantValue) * 100}%`,
                                            background: getPerformanceColor(value, maxRestaurantValue),
                                            borderRadius: "0 0 10px 10px"
                                        }} />
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Dishes */}
                <div className="card" style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    borderRadius: "12px",
                    padding: "20px",
                    position: "relative",
                    overflow: "hidden"
                }}>
                    <div style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "3px",
                        background: "linear-gradient(90deg, #10b981, #3b82f6, #8b5cf6)"
                    }} />

                    <div style={{
                        display:"flex",
                        justifyContent:"space-between",
                        alignItems:"center",
                        marginBottom: 16
                    }}>
                        <div style={{display: "flex", alignItems: "center", gap: 8}}>
                            <span style={{fontSize: "1.2rem"}}>🍕</span>
                            <b style={{fontSize: "1.1rem", color: "var(--text-1)"}}>Dishes</b>
                        </div>

                        <div style={{
                            display:"flex",
                            gap: 4,
                            background: "var(--surface-3)",
                            padding: "4px",
                            borderRadius: "8px",
                            border: "1px solid var(--border)"
                        }}>
                            <button
                                onClick={()=>setDMetric("units")}
                                className={`btn ${dMetric==='units'?'':'ghost'}`}
                                style={{
                                    fontSize: "0.8rem",
                                    padding: "6px 12px",
                                    borderRadius: "6px",
                                    ...(dMetric === 'units' ? {
                                        background: "linear-gradient(135deg, #8b5cf6, #7c3aed)",
                                        color: "white",
                                        boxShadow: "0 2px 4px rgba(139, 92, 246, 0.3)"
                                    } : {})
                                }}
                            >
                                Units
                            </button>
                            <button
                                onClick={()=>setDMetric("revenue")}
                                className={`btn ${dMetric==='revenue'?'':'ghost'}`}
                                style={{
                                    fontSize: "0.8rem",
                                    padding: "6px 12px",
                                    borderRadius: "6px",
                                    ...(dMetric === 'revenue' ? {
                                        background: "linear-gradient(135deg, #10b981, #059669)",
                                        color: "white",
                                        boxShadow: "0 2px 4px rgba(16, 185, 129, 0.3)"
                                    } : {})
                                }}
                            >
                                Revenue
                            </button>
                        </div>
                    </div>

                    <div style={{display:"grid", gridTemplateColumns:"1fr", gap: 8}}>
                        {(dLoad ? Array.from({length:8}).map((_,i)=>({skeleton:true,id:i})) : dishes).map((d,i)=>{
                            const value = dMetric === "units" ? d.units : d.revenue;
                            const displayValue = dMetric === "units" ? (d.units ?? 0).toLocaleString() : fmtTND(d.revenue);

                            return (
                                <div key={`${d.dish ?? 'sk'}-${i}`} style={{
                                    display:"flex",
                                    alignItems:"center",
                                    gap: 12,
                                    padding: "12px 16px",
                                    background: i % 2 === 0 ? "var(--surface-3)" : "var(--surface-1)",
                                    border: "1px solid var(--border)",
                                    borderRadius: "10px",
                                    transition: "all 0.2s ease",
                                    position: "relative",
                                    overflow: "hidden"
                                }}
                                     onMouseEnter={(e) => {
                                         e.currentTarget.style.transform = "translateY(-2px)";
                                         e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)";
                                     }}
                                     onMouseLeave={(e) => {
                                         e.currentTarget.style.transform = "translateY(0)";
                                         e.currentTarget.style.boxShadow = "none";
                                     }}
                                >
                                    <div style={{
                                        minWidth: "32px",
                                        height: "32px",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        background: i < 3 ? "linear-gradient(135deg, #fbbf24, #f59e0b)" : "var(--surface-2)",
                                        borderRadius: "8px",
                                        fontSize: i < 3 ? "1rem" : "0.9rem",
                                        fontWeight: "700",
                                        color: i < 3 ? "white" : "var(--text-1)"
                                    }}>
                                        {getRankIcon(i)}
                                    </div>

                                    <div style={{
                                        flex: 1,
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        fontWeight: "600",
                                        color: "var(--text-1)"
                                    }}>
                                        {d.skeleton ?
                                            <span className="skeleton" style={{display:"inline-block",width:140,height:14}}/> :
                                            d.dish
                                        }
                                    </div>

                                    <div style={{
                                        fontWeight: "700",
                                        fontSize: "0.9rem",
                                        color: getPerformanceColor(value, maxDishValue, dMetric === 'revenue')
                                    }}>
                                        {d.skeleton ?
                                            <span className="skeleton" style={{display:"inline-block",width:60,height:14}}/> :
                                            displayValue
                                        }
                                    </div>

                                    {/* Performance indicator bar */}
                                    {!d.skeleton && (
                                        <div style={{
                                            position: "absolute",
                                            bottom: 0,
                                            left: 0,
                                            height: "3px",
                                            width: `${(value / maxDishValue) * 100}%`,
                                            background: getPerformanceColor(value, maxDishValue, dMetric === 'revenue'),
                                            borderRadius: "0 0 10px 10px"
                                        }} />
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}