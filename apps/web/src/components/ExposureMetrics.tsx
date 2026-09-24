import { useEffect, useState } from "react";
import { useAuth } from "@/context/Auth";
import { api } from "@/lib/api";
import { genderLabels, type Gender } from "@/lib/gender";

type Group = { gender: Gender; users: number; impressions: number; clicks: number; ctr: number | null;
  complete_rate: number | null; engage_rate: number | null; continue_rate: number | null };
export function ExposureMetrics() {
  const { token, user } = useAuth();
  const [gender, setGender] = useState("");
  const [origin, setOrigin] = useState("real");
  const [groups, setGroups] = useState<Group[]>([]);
  const [error, setError] = useState("");
  const pct = (n: number | null) => n == null ? "Sin datos" : `${(100*n).toFixed(1)}%`;
  useEffect(() => {
    if (token) void api<{ genders: Group[] }>(`/lab/exposures/metrics?origin=${origin}${gender ? `&gender=${gender}` : ""}`, {}, token)
      .then((r) => { setGroups(r.genders); setError(""); }).catch((e: Error) => setError(e.message));
  }, [token, gender, origin]);
  async function download() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || "/api"}/lab/orange/exposures.csv?origin=${origin}`, {headers:{Authorization:`Bearer ${token}`}});
      if (!response.ok) throw new Error("No se pudo exportar el dataset");
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a"); a.href = url; a.download = `veta_exposures_${origin}.csv`; a.click();
      window.setTimeout(() => URL.revokeObjectURL(url),1000);
    } catch (err) { setError(err instanceof Error ? err.message : "Error al exportar"); }
  }
  return <section className="mt-8 rounded-xl border border-ink/15 p-4">
    <h2 className="font-display text-xl font-bold">Exposiciones y género · últimos 7 días</h2>
    <p className="mt-2 text-sm text-ink/65">Resultados por aparición visible. Finalización, interacción y continuidad requieren etiquetas maduras (24 horas). Los históricos sin exposición quedan fuera.</p>
    {origin === "simulated" && <p className="mt-2 text-sm text-ink/65">Ejemplo aleatorio reproducible: 60 perfiles ficticios y 5 días de exposiciones. Se genera al consultar, sin usar datos de la aplicación; sirve solo para pruebas.</p>}
    <div className="my-4 flex flex-wrap gap-3">
      <label>Género <select className="rounded border p-2" value={gender} onChange={(e) => setGender(e.target.value)}><option value="">Todos</option>{Object.entries(genderLabels).map(([g,l]) => <option key={g} value={g}>{l}</option>)}</select></label>
      <label>Origen <select className="rounded border p-2" value={origin} onChange={(e) => setOrigin(e.target.value)}><option value="real">Real</option><option value="simulated">Simulado</option></select></label>
      {user?.role === "admin" && <button className="rounded bg-ink px-4 py-2 text-paper" onClick={() => void download()}>Exportar exposiciones para MMoE / Orange</button>}
    </div>
    {error && <p role="alert">{error}</p>}
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Género","Usuarios","Exposiciones","Finalización","Interacción","Continuidad","Clics","CTR"].map((s) => <th className="p-2" key={s}>{s}</th>)}</tr></thead>
      <tbody>{groups.map((g) => <tr key={g.gender} className="border-t border-ink/10"><td className="p-2">{genderLabels[g.gender]}</td><td>{g.users}</td><td>{g.impressions}</td><td>{pct(g.complete_rate)}</td><td>{pct(g.engage_rate)}</td><td>{pct(g.continue_rate)}</td><td>{g.clicks}</td><td>{pct(g.ctr)}</td></tr>)}</tbody>
    </table></div>
  </section>;
}
