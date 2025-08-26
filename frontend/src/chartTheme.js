export const tickSmall = { fill: "var(--muted)", fontSize: 12 };
export const gridDash = "3 3";
export function safeDomain(data, keys) {
    const max = Math.max(1, ...data.map(d => keys.reduce((s,k)=> s + (Number(d[k])||0), 0)));
    return [0, Math.ceil(max * 1.08)];
}
