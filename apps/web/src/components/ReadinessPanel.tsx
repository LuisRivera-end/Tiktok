import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/context/Auth";
import { api } from "@/lib/api";

type Task = "complete" | "engage" | "continue" | "click";
type Counts = { observed: number; positive: number; negative: number };
type Readiness = {
  status: "collecting" | "trainable" | "evaluation_ready";
  exposures: number;
  users: number;
  sessions: number;
  days: number;
  campaigns: number;
  tasks: Record<Task, Counts>;
  reasons: string[];
};

const labels: Record<Task, string> = {
  complete: "Finalización", engage: "Interacción", continue: "Continuidad", click: "Clic publicitario",
};
const statuses: Record<Readiness["status"], string> = {
  collecting: "Recopilando datos",
  trainable: "Se puede entrenar; aún falta evidencia para evaluar la activación",
  evaluation_ready: "Hay volumen para evaluar; la aprobación depende de los resultados",
};

export function ReadinessPanel() {
  const { token, user } = useAuth();
  const [data, setData] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const refresh = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      setData(await api<Readiness>("/lab/exposures/readiness", {}, token));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo calcular la preparación.");
    } finally {
      setLoading(false);
    }
  }, [token]);
  useEffect(() => { if (user?.role === "admin") void refresh(); }, [refresh, user?.role]);
  if (user?.role !== "admin") return null;

  return <section className="mt-6 max-w-6xl rounded-xl border border-ink/15 bg-paper-2/50 p-4" aria-label="Preparación MMoE">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="font-display text-xl font-bold">Preparación del MMoE</h2>
        <p className="mt-1 text-sm text-ink/65">Solo exposiciones reales. Las etiquetas necesitan 24 horas para madurar.</p>
      </div>
      <button type="button" onClick={() => void refresh()} disabled={loading}
        className="rounded-lg border border-ink/20 px-4 py-2 text-sm font-semibold disabled:opacity-50">
        {loading ? "Comprobando…" : "Actualizar diagnóstico"}
      </button>
    </div>
    {error && <p className="mt-3 text-sm text-skip" role="alert">{error}</p>}
    {data && <>
      <p className="mt-4 font-semibold" role="status">{statuses[data.status]}</p>
      <p className="mt-1 text-sm text-ink/70">{data.exposures} exposiciones · {data.users} usuarios · {data.sessions} sesiones · {data.days} días · {data.campaigns} campañas</p>
      <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm">
        <thead><tr><th className="p-2">Objetivo</th><th className="p-2">Observadas</th><th className="p-2">Positivas</th><th className="p-2">Negativas</th></tr></thead>
        <tbody>{(Object.keys(labels) as Task[]).map((task) => <tr key={task} className="border-t border-ink/10">
          <td className="p-2">{labels[task]}</td><td className="p-2">{data.tasks[task].observed}</td>
          <td className="p-2">{data.tasks[task].positive}</td><td className="p-2">{data.tasks[task].negative}</td>
        </tr>)}</tbody>
      </table></div>
      {data.reasons.length > 0 && <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-ink/70">
        {data.reasons.map((reason) => <li key={reason}>{reason}</li>)}
      </ul>}
    </>}
  </section>;
}
