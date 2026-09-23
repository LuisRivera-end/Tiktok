import { useEffect, useState } from "react";

import { BiReport } from "@/components/BiReport";
import { useAuth } from "@/context/Auth";
import { api, type Metrics } from "@/lib/api";

const BASE = import.meta.env.VITE_API_URL || "/api";

export function LabPage() {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [region, setRegion] = useState("");
  const [category, setCategory] = useState("");
  const [simNote, setSimNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    const params = new URLSearchParams();
    if (region) params.set("region", region);
    if (category) params.set("category", category);
    const query = params.toString() ? `?${params.toString()}` : "";
    void api<Metrics>(`/lab/metrics${query}`, {}, token)
      .then((body) => {
        if (!cancelled) { setMetrics(body); setError(null); }
      })
      .catch((cause: unknown) => {
        if (!cancelled) { setMetrics(null); setError(cause instanceof Error ? cause.message : "No se pudieron cargar las métricas."); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => {
      cancelled = true;
    };
  }, [token, region, category]);

  async function reload() {
    if (!token) return;
    const params = new URLSearchParams();
    if (region) params.set("region", region);
    if (category) params.set("category", category);
    const query = params.toString() ? `?${params.toString()}` : "";
    setMetrics(await api<Metrics>(`/lab/metrics${query}`, {}, token));
    setError(null);
  }

  async function simulate() {
    if (!token || busy) return;
    setBusy(true);
    try {
      const result = await api<{ events: number; users: number }>("/lab/sim", {
        method: "POST",
        body: JSON.stringify({ users: 80, days: 5, events_per_user: 8 }),
      }, token);
      setSimNote(`Simulación: ${result.events} eventos de ${result.users} perfiles.`);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo completar la simulación.");
    } finally {
      setBusy(false);
    }
  }

  async function injectOrange() {
    if (!token || busy) return;
    setBusy(true);
    try {
      const result = await api<{ events: number; users: number; regions?: number }>("/lab/sim", {
        method: "POST",
        body: JSON.stringify({ users: 25, days: 5, events_per_user: 8, pass_id: "orange-1000" }),
      }, token);
      setSimNote(`Pasada Orange: ${result.events} eventos de ${result.users} perfiles, en ${result.regions ?? 0} regiones.`);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo preparar el corte de Orange.");
    } finally {
      setBusy(false);
    }
  }

  function downloadCsv() {
    if (!token) return;
    void fetch(`${BASE}/lab/orange/interactions.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("No se pudo descargar el CSV.");
        return res.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "veta_interactions.csv";
        a.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "No se pudo descargar el CSV."));
  }
  const regions = metrics?.regions ?? [];

  return (
    <main className="min-h-full bg-paper px-5 py-8 text-ink sm:px-10 lg:px-12">
      <header className="max-w-6xl border-b border-ink/15 pb-4 sm:pb-6">
        <p className="text-sm text-ink/60">Laboratorio / BI</p>
        <h1 className="mt-2 font-display text-3xl font-extrabold tracking-tight text-balance sm:text-5xl">Mesa de señales</h1>
        <p className="mt-3 max-w-2xl text-ink/70">Explora el progreso de los clips por región y categoría.</p>
        <p className="mt-3 text-sm text-ink/60">
          Últimos 7 días · {metrics?.events ?? 0} eventos · {metrics?.views ?? 0} reproducciones · {metrics?.active_users ?? 0} usuarios
        </p>
        {metrics?.truncated && <p className="mt-2 rounded-md bg-skip/10 px-3 py-2 text-sm text-ink" role="status">Muestra limitada a los 20 000 eventos más recientes del periodo.</p>}
      </header>
      <details className="mt-4 rounded-xl border border-ink/10 bg-paper-2/50 px-4 py-3 open:pb-4">
        <summary className="cursor-pointer font-semibold focus-visible:outline-2 focus-visible:outline-lab">Simulación y exportación</summary>
        <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void simulate()}
          disabled={busy}
          className="h-11 rounded-lg bg-ink px-4 font-semibold text-paper disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lab"
        >
          {busy ? "Preparando datos…" : "Correr simulador"}
        </button>
        <button
          type="button"
          onClick={() => void injectOrange()}
          disabled={busy}
          className="h-11 rounded-lg border border-ink/20 px-4 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lab"
        >
          Inyectar ~1000 para Orange
        </button>
        <button
          type="button"
          onClick={downloadCsv}
          className="h-11 rounded-lg border border-ink/20 px-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lab"
        >
          Descargar CSV para Orange
        </button>
        </div>
      </details>
      {simNote && (
        <p className="mt-4 text-sm text-lab" role="status">
          {simNote}
        </p>
      )}
      {error && <p className="mt-4 rounded-md border border-skip/30 bg-skip/10 px-4 py-3 text-sm" role="alert">{error}</p>}

      <section className="mt-6 max-w-7xl sm:mt-8" aria-labelledby="bi-dashboard">
        <h2 id="bi-dashboard" className="font-display text-2xl font-extrabold">
          Reproducciones
        </h2>
        <p className="mt-2 max-w-xl text-ink/70">Los porcentajes usan reproducciones; el volumen incluye todos los eventos.</p>
        {loading && <p className="mt-4 text-sm text-ink/60" role="status">Cargando métricas…</p>}
        {!loading && metrics?.events === 0 && <p className="mt-4 rounded-lg bg-paper-2 p-4 text-sm">Aún no hay eventos en los últimos 7 días. Abre «Simulación y exportación» y corre el simulador para explorar el tablero.</p>}
        <div className="mt-5 grid min-w-0 gap-4 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <aside className="grid h-fit grid-cols-2 gap-x-3 rounded-xl border border-ink/10 bg-paper-2/60 p-4 lg:block">
            <h3 className="col-span-2 font-display text-lg font-bold">Corte</h3>
            <label className="mt-3 block min-w-0 text-sm text-ink/70">
              Región del clip
              <select
                className="mt-1 h-11 w-full rounded-md border border-ink/20 bg-paper px-3 text-ink focus-visible:outline-2 focus-visible:outline-lab"
                value={region}
                onChange={(event) => setRegion(event.target.value)}
              >
                <option value="">Todas</option>
                {(metrics?.available_regions ?? []).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-3 block min-w-0 text-sm text-ink/70 lg:mt-4">
              Categoría
              <select
                className="mt-1 h-11 w-full rounded-md border border-ink/20 bg-paper px-3 text-ink focus-visible:outline-2 focus-visible:outline-lab"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                <option value="">Todas</option>
                {(metrics?.available_categories ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <button
              type="button"
              onClick={() => {
                setRegion("");
                setCategory("");
              }}
              disabled={!region && !category}
              className="col-span-2 mt-4 w-fit text-sm font-semibold text-ink underline underline-offset-4 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-lab"
            >
              Borrar filtros
            </button>
          </aside>
          <BiReport
            regions={regions}
            categories={metrics?.categories ?? []}
            eventTypes={metrics?.event_types ?? []}
            focus={metrics?.focus ?? null}
            region={region}
            category={category}
            onRegion={setRegion}
            onCategory={setCategory}
          />
        </div>
      </section>

      <section className="mt-10 max-w-2xl" aria-labelledby="etl">
        <h2 id="etl" className="font-display text-2xl font-extrabold">
          Proceso ETL
        </h2>
        <ol className="mt-4 space-y-4">
          <li>
            <h3 className="font-display text-lg font-extrabold">Extraer</h3>
            <p className="mt-1 text-ink/70">
              Se leen los eventos de interacción y el catálogo de usuarios y clips, incluida la región de la cuenta y
              la del clip.
            </p>
          </li>
          <li>
            <h3 className="font-display text-lg font-extrabold">Transformar</h3>
            <p className="mt-1 text-ink/70">
              Se separan las reproducciones de las acciones sociales sin tiempo visto. El progreso usa completion_ratio
              y early_skip marca solo skips con menos de 2 segundos. Los porcentajes se recalculan para cada corte.
            </p>
          </li>
          <li>
            <h3 className="font-display text-lg font-extrabold">Cargar</h3>
            <p className="mt-1 text-ink/70">
              El tablero agrega los eventos de los últimos 7 días. El CSV de Orange se genera al descargarlo a partir
              de esos eventos, con un alcance histórico de hasta 50 000 filas. En Orange abre File con el CSV y sigue con Correlations (watch_ms vs completion_ratio), PCA (2
              componentes) y k-Means (k = 4). early_skip es la clase. user_region y video_region son columnas
              discretas.
            </p>
          </li>
        </ol>
      </section>
    </main>
  );
}
