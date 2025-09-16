// src/DynamicSlaViolations.jsx
import { useEffect, useState } from "react";
import { API } from "./App";

const fmtTime = (ts) =>
    ts ? new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

const scalePercent = (v) => {
    if (v == null) return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    // If it's already “percent-like” (e.g., 87.05) keep it; if it's a ratio (0.8705) scale it.
    return n >= 10 ? n : n * 100;
};

export default function DynamicSlaViolations() {
    const [win, setWin] = useState(180); // minutes window
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let alive = true;
        const load = async () => {
            try {
                const qs = new URLSearchParams({ minutes: String(win), limit: "50", threshold: "1.25" }).toString();
                const r = await fetch(`${API}/api/dsla/violations?${qs}`);
                const d = await r.json();
                if (!alive) return;
                setRows(Array.isArray(d) ? d : []);
                setLoading(false);
            } catch {
                /* keep last */
            }
        };
        load();
        const t = setInterval(load, 10000);
        return () => { alive = false; clearInterval(t); };
    }, [win]);

    return (
        <div className="card" style={{ minHeight: 420 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>Dynamic SLA — Violations</h3>
                <div style={{ display: "flex", gap: 8 }}>
                    {[60, 180, 720].map((m) => (
                        <button
                            key={m}
                            className={`btn ${win === m ? "" : "ghost"}`}
                            onClick={() => setWin(m)}
                            aria-pressed={win === m}
                        >
                            {m === 60 ? "1h" : m === 180 ? "3h" : "12h"}
                        </button>
                    ))}
                </div>
            </div>

            <div
                style={{
                    marginTop: 8,
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    overflow: "hidden",
                }}
            >
                {/* header */}
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 140px 140px 120px",
                        padding: "10px 12px",
                        background: "var(--surface-2)",
                        fontWeight: 700,
                        color: "var(--muted)",
                    }}
                >
                    <div>Order · Restaurant (City)</div>
                    <div>Actual</div>
                    <div>Pred.</div>
                    <div>Overrun</div>
                </div>

                <div style={{ maxHeight: 460, overflowY: "auto" }}>
                    {loading ? (
                        <div style={{ padding: 16, color: "var(--muted)" }}>Loading…</div>
                    ) : rows.length ? (
                        rows.map((r, i) => {
                            const pct = scalePercent(r.overrun_pct);
                            const pctStr = pct == null ? "—" : `+${Math.round(pct)}%`;
                            return (
                                <div
                                    key={`${r.order_id}-${i}`}
                                    style={{
                                        display: "grid",
                                        gridTemplateColumns: "1fr 140px 140px 120px",
                                        padding: "12px",
                                        borderTop: "1px dashed var(--border)",
                                        alignItems: "baseline",
                                    }}
                                >
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                            #{r.order_id} · {r.restaurant_name}
                                        </div>
                                        <div style={{ fontSize: 12, color: "var(--muted)" }}>
                                            {r.city_name} · {fmtTime(r.violation_timestamp)}
                                        </div>
                                    </div>

                                    <div style={{ fontVariantNumeric: "tabular-nums" }}>
                                        <b>{Math.round(r.actual_minutes)} min</b>
                                        <div style={{ fontSize: 11, color: "var(--muted)" }}>actual</div>
                                    </div>

                                    <div style={{ fontVariantNumeric: "tabular-nums" }}>
                                        <b>{Math.round(r.predicted_minutes)} min</b>
                                        <div style={{ fontSize: 11, color: "var(--muted)" }}>pred.</div>
                                    </div>

                                    <div style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                                        <div style={{ color: "var(--danger)", fontWeight: 800 }}>{pctStr}</div>
                                        <div style={{ fontSize: 11, color: "var(--muted)" }}>
                                            +{Number(r.overrun_minutes ?? 0).toFixed(1)} min
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    ) : (
                        <div style={{ padding: 16, color: "var(--muted)" }}>No violations in window.</div>
                    )}
                </div>
            </div>
        </div>
    );
}
