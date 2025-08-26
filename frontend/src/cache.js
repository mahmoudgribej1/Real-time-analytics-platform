export const readCache = (key, fallback = null) => {
    try {
        const s = sessionStorage.getItem(key);
        if (!s) return fallback;
        const { v, exp } = JSON.parse(s);
        if (exp && Date.now() > exp) { sessionStorage.removeItem(key); return fallback; }
        return v;
    } catch { return fallback; }
};

export const writeCache = (key, value, ttlMs = 0) => {
    try {
        sessionStorage.setItem(key, JSON.stringify({ v: value, exp: ttlMs ? (Date.now()+ttlMs) : 0 }));
    } catch {}
};
