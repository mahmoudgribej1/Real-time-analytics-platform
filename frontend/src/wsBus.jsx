// src/wsBus.jsx
import { createContext, useContext, useEffect, useRef, useState } from "react";
export const WSContext = createContext({ events: [], connected: false });

export function WSProvider({ url, children }) {
    const [events, setEvents] = useState([]);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef(null);

    useEffect(() => {
        let ws;
        try { ws = new WebSocket(url); }
        catch (e) { console.warn("[WS] construct fail:", e); setConnected(false); return; }

        wsRef.current = ws;
        ws.onopen = () => setConnected(true);
        ws.onclose = ws.onerror = () => setConnected(false);
        ws.onmessage = (e) => { try {
            const msg = JSON.parse(e.data);
            setEvents(prev => [msg, ...prev].slice(0, 200));
        } catch {} };

        const ping = setInterval(() => { try { ws.send("ping"); } catch {} }, 25000);
        return () => { clearInterval(ping); try { ws.close(); } catch {} };
    }, [url]);

    return <WSContext.Provider value={{ events, connected }}>{children}</WSContext.Provider>;
}
export const useWSEvents = () => useContext(WSContext).events;
