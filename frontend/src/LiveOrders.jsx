// LiveOrders.jsx
import { useQuery } from "@tanstack/react-query";
import { API } from "./App";
import { useMemo } from "react";
import { useState, useEffect } from "react";

const pill = (s) => ({
    Delivering: { text: "DELIVERING", cls: "pill delivering" },
    Processing: { text: "PROCESSING", cls: "pill preparing" },
    Completed:  { text: "DONE",       cls: "pill ok" },
    Cancelled:  { text: "Cancelled",  cls: "pill" },
}[s] || { text: s, cls: "pill" });

export default function LiveOrders() {
    const { data: rows = [] } = useQuery({
        queryKey: ["orders-live"],
        queryFn: async () => {
            const r = await fetch(`${API}/api/orders/live?limit=30`);
            return r.json();
        },
        refetchInterval: 5_000,
        staleTime: 4_000,
    });

    const activeCount = useMemo(
        () => rows.filter((r) => r.status === "Processing" || r.status === "Delivering").length,
        [rows]
    );

    return (
        <div className="card card-lg">
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3>Live Orders</h3>
                <span className="badge">{activeCount} Active</span>
            </div>

            {/* scroll container */}
            <div className="orders" style={{maxHeight: 420, overflowY: "auto", paddingRight: 4}}>
                {rows.map((o) => {
                    const p = pill(o.status);
                    const isLive = o.status === "Processing" || o.status === "Delivering";
                    const mins   = isLive ? (o.eta_min ?? o.elapsed_min ?? 0) : (o.elapsed_min ?? 0);
                    const minsLabel = isLive && o.eta_min != null ? `${mins} min ETA` : `${mins} min`;

                    return (
                        <div key={o.order_id} className="order-card">
                            <div className="left">
                                <span className={p.cls}>{p.text}</span>
                                <div className="ord-id">#{o.order_id}</div>
                                <div className="city">
                                    {o.city_name} · <span style={{opacity:.8}}>{o.restaurant_name}</span>
                                </div>
                            </div>
                            <div className="right">
                                <div className="eta">{minsLabel}</div>
                                <div className="price">TND {Math.round(o.price || 0)}</div>
                            </div>
                        </div>
                    );
                })}
                {!rows.length && <div style={{opacity:.7}}>No recent activity.</div>}
            </div>
        </div>
    );
}
