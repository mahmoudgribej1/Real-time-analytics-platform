import { useEffect, useState } from "react";
import { API } from "./App";

const kindIcon = (k) =>
    k === "driver_shortage" ? "🚦"
        : k === "sla_spike"       ? "🚨"
            : k === "peak_start"      ? "📈"
                : "🔔";

const sevStyle = (s) => ({
    info:     { bg: "rgba(59,130,246,.12)",  bd: "rgba(59,130,246,.35)",  fg: "#60a5fa" },
    warning:  { bg: "rgba(245,158,11,.12)",  bd: "rgba(245,158,11,.35)",  fg: "#fbbf24" },
    critical: { bg: "rgba(239,68,68,.12)",   bd: "rgba(239,68,68,.35)",   fg: "#f87171" },
}[s] || { bg: "var(--surface-2)", bd: "var(--border)", fg: "var(--text)" });

function DetailChips({ a }) {
    const chips = [];
    if (a.kind === "driver_shortage") {
        chips.push({ label: "Pressure", val: a.details?.pressure });
        chips.push({ label: "Orders", val: a.details?.orders });
        chips.push({ label: "Couriers", val: a.details?.available_couriers });
    } else if (a.kind === "sla_spike") {
        chips.push({ label: "Breaches (10m)", val: a.details?.breaches_10m });
    } else if (a.kind === "peak_start") {
        chips.push({ label: "Orders/min", val: a.details?.opm });
    }
    return (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {chips.map((c, i) => (
                <span
                    key={i}
                    className="pill"
                    style={{
                        padding: "4px 8px",
                        fontSize: 12,
                        borderRadius: 999,
                        border: "1px solid var(--border)",
                        background: "var(--surface-2)"
                    }}
                    title={c.label}
                >
          <b style={{ opacity: 0.85 }}>{c.label}:</b>{" "}
                    <span style={{ fontVariantNumeric: "tabular-nums" }}>{c.val ?? "—"}</span>
        </span>
            ))}
        </div>
    );
}

export default function SmartAlerts() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);

    const load = async () => {
        try {
            const r = await fetch(`${API}/api/alerts/active`);
            const d = await r.json();
            setRows(Array.isArray(d) ? d : []);
        } catch {
            /* keep last view */
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
        const t = setInterval(load, 10000);
        return () => clearInterval(t);
    }, []);

    return (
        <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3>Smart Alerts</h3>
                <span className="badge">{rows.length} Active</span>
            </div>

            <div style={{ maxHeight: 420, overflowY: "auto", paddingRight: 6 }}>
                {loading && <div style={{ opacity: 0.7, padding: 12 }}>Loading…</div>}
                {!loading && rows.length === 0 && (
                    <div style={{ opacity: 0.7, padding: 12 }}>No active alerts.</div>
                )}

                {rows.map((a, i) => {
                    const sev = sevStyle(a.severity);
                    return (
                        <div
                            key={`${a.kind}:${a.city_name}:${i}`}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                gap: 16,
                                padding: "12px 14px",
                                margin: "10px 0",
                                borderRadius: 12,
                                border: `1px solid ${sev.bd}`,
                                background: sev.bg,
                            }}
                        >
                            <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                                <div
                                    style={{
                                        width: 30,
                                        height: 30,
                                        borderRadius: 8,
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        background: "var(--surface-1)",
                                        border: "1px solid var(--border)",
                                        color: sev.fg,
                                        fontSize: 16,
                                    }}
                                >
                                    {kindIcon(a.kind)}
                                </div>
                                <div style={{ minWidth: 0 }}>
                                    <div
                                        style={{
                                            fontWeight: 700,
                                            marginBottom: 4,
                                            color: "var(--text)",
                                            whiteSpace: "nowrap",
                                            overflow: "hidden",
                                            textOverflow: "ellipsis",
                                        }}
                                        title={a.title}
                                    >
                                        {a.title}
                                    </div>
                                    <DetailChips a={a} />
                                </div>
                            </div>
                            {/* read-only: no buttons */}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
