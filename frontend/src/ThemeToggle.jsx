import { useEffect, useState } from "react";

function getInitialTheme(){
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
    return prefersDark ? "dark" : "light";
}

export default function ThemeToggle(){
    const [mode, setMode] = useState(getInitialTheme());

    useEffect(()=>{
        document.documentElement.setAttribute("data-theme", mode);
        localStorage.setItem("theme", mode);
    }, [mode]);

    const next = () => setMode(m => (m === "light" ? "dark" : "light"));

    return (
        <button className="btn secondary" onClick={next} title="Toggle theme" style={{padding:"8px 10px"}}
                aria-pressed={mode==="dark"} aria-label="Toggle color theme (t)"onKeyDown={(e)=>{ if (e.key.toLowerCase()==="t") next(); }}>
            {mode === "light" ? "🌙 Dark" : "☀️ Light"}
        </button>
    );
}
