import { useEffect, useMemo, useRef, useState } from "react";
import { API } from "./App";
import Chart from "chart.js/auto";

function toNumber(x, fallback = 0) {
    const n = Number(x);
    return Number.isFinite(n) ? n : fallback;
}

export default function DynamicModelHealth() {
    const [hours, setHours] = useState(3);
    const [rows, setRows] = useState([]);
    const [mae1h, setMae1h] = useState(0);
    const [err, setErr] = useState(null);
    const chartRef = useRef(null);
    const canvasRef = useRef(null);

    // fetch
    useEffect(() => {
        let abort = false;
        (async () => {
            try {
                setErr(null);
                const r = await fetch(`${API}/api/dsla/model_health?hours=${hours}`);
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                const data = await r.json();

                // rows may be array OR JSON string (older server versions)
                let raw = data?.rows ?? [];
                if (typeof raw === "string") {
                    try { raw = JSON.parse(raw); } catch { raw = []; }
                }
                if (!Array.isArray(raw)) raw = [];

                // Normalize & clean
                const normalized = raw
                    .filter(d => d && d.ts != null)
                    .map(d => ({
                        ts: new Date(d.ts).getTime(),
                        mae: toNumber(d.mae),
                        mape: toNumber(d.mape),
                    }))
                    .filter(d => Number.isFinite(d.ts));

                normalized.sort((a, b) => a.ts - b.ts);

                if (!abort) {
                    setRows(normalized);
                    setMae1h(toNumber(data?.mae_1h));
                }
            } catch (e) {
                if (!abort) setErr(e.message || String(e));
            }
        })();
        return () => { abort = true; };
    }, [hours]);

    const labels = useMemo(
        () => rows.map(d => new Date(d.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })),
        [rows]
    );
    const maeSeries = useMemo(() => rows.map(d => d.mae), [rows]);
    const latestMae = maeSeries.length ? maeSeries[maeSeries.length - 1] : 0;

    // chart init/update
    useEffect(() => {
        if (!canvasRef.current) return;
        if (!chartRef.current) {
            chartRef.current = new Chart(canvasRef.current, {
                type: "line",
                data: {
                    labels: [],
                    datasets: [{
                        label: "MAE (min)",
                        data: [],
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 0,
                    }],
                },
                options: {
                    responsive: true,
                    animation: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true },
                        x: { ticks: { maxRotation: 0, autoSkip: true } },
                    },
                }
            });
        }
        const ch = chartRef.current;
        ch.data.labels = labels;
        ch.data.datasets[0].data = maeSeries;
        ch.update();
    }, [labels, maeSeries]);

    useEffect(() => () => { if (chartRef.current) { chartRef.current.destroy(); chartRef.current = null; } }, []);

    return (
        <div className="card" style={{ position: "relative" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <h3 style={{ margin: 0 }}>Dynamic SLA — Model Health</h3>
                <div className="pill" style={{ fontWeight: 700 }}>
                    Latest MAE: {toNumber(latestMae).toFixed(1)} min
                </div>
            </div>

            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
                {[1, 3, 12].map(h => (
                    <button
                        key={h}
                        onClick={() => setHours(h)}
                        className="btn ghost"
                        style={{
                            padding: "6px 10px",
                            borderRadius: 12,
                            ...(hours === h ? { boxShadow: "0 0 0 3px rgba(59,130,246,.45) inset" } : {})
                        }}
                    >
                        {h}h
                    </button>
                ))}
            </div>

            <canvas ref={canvasRef} height="180" />

            {err && (
                <div style={{ marginTop: 8, color: "var(--danger)" }}>Failed to load: {err}</div>
            )}
            {!err && rows.length === 0 && (
                <div style={{ marginTop: 8, opacity: .7 }}>No data for this window.</div>
            )}
        </div>
    );
}
