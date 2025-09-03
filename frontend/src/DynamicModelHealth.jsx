import { useQuery } from "@tanstack/react-query";
import { API } from "./App";

export default function DynamicModelHealth() {
    const { data = [], isFetching } = useQuery({
        queryKey: ["dsla-model-health", { hours: 6 }],
        queryFn: async () => (await fetch(`${API}/api/dsla/model_health?hours=6`)).json(),
        refetchInterval: 30_000,
        staleTime: 25_000,
    });

    const mae = data.map(d => d.mae ?? 0);

    return (
        <div className="card" style={{padding:20}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <h3 style={{margin:0}}>Dynamic SLA — Model Health</h3>
                {isFetching && <span className="badge">Refreshing…</span>}
            </div>
            <div style={{fontSize:12,color:"var(--muted)", marginBottom:8}}>MAE (min), last 6h</div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(30,1fr)",gap:6}}>
                {mae.slice(-30).map((v,i)=>(<div key={i} style={{height:28, background:"var(--surface-3)", position:"relative"}}>
                    <div style={{position:"absolute", bottom:0, left:0, right:0, height:`${Math.min(100, v*4)}%`, background:"#3b82f6"}}/>
                </div>))}
            </div>
        </div>
    );
}
