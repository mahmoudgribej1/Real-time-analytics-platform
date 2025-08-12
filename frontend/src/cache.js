export const readCache = (key, fallback = null) => {
    try {
        const s = sessionStorage.getItem(key);
        return s ? JSON.parse(s) : fallback;
    } catch {
        return fallback;
    }
};

export const writeCache = (key, value) => {
    try {
        sessionStorage.setItem(key, JSON.stringify(value));
    } catch {}
};
