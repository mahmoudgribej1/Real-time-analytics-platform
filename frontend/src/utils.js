
export const fmtTime = (ms) => ms ? new Date(ms).toLocaleTimeString([], {hour12:false}) : "—";
export const staleClass = (ms) => {
    const age = Date.now() - (ms||0);
    if (age > 5*60_000) return "stale-hard";
    if (age > 2*60_000) return "stale";
    return "";
};
// restaurant row severity
export const rSeverity = (o15, prep) => (prep??0) >= 20 || (o15??0) >= 18 ? "crit" :
    (prep??0) >= 16 || (o15??0) >= 12 ? "warn" : "";
// courier row severity
export const cSeverity = (active, speed) => (active??0) >= 6 || (speed??0) < 18 ? "crit" :
    (active??0) >= 4 || (speed??0) < 22 ? "warn" : "";
