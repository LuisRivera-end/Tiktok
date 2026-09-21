import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/Auth";
import { api, type Metrics } from "@/lib/api";
import { duration, gsap, useGSAP } from "@/lib/motion";

const BASE = import.meta.env.VITE_API_URL || "/api";

export function LabPage() {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [simNote, setSimNote] = useState<string | null>(null);
  const grid = useRef<HTMLElement>(null);

  async function load() {
    if (!token) return;
    setMetrics(await api<Metrics>("/lab/metrics", {}, token));
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function simulate() {
    if (!token) return;
    const result = await api<{ events: number; users: number }>("/lab/sim", {
      method: "POST",
      body: JSON.stringify({ users: 20, days: 2, events_per_user: 12 }),
    }, token);
    setSimNote(`Simulación: ${result.events} eventos de ${result.users} perfiles.`);
    await load();
  }

  function downloadCsv() {
    if (!token) return;
    void fetch(`${BASE}/lab/orange/interactions.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "veta_interactions.csv";
        a.click();
        URL.revokeObjectURL(url);
      });
  }

  const cards = metrics
    ? [
        ["Retención media (min)", metrics.retention_minutes],
        ["Finalización", `${Math.round(metrics.completion_rate * 100)}%`],
        ["Abandono < 2s", `${Math.round(metrics.early_abandon_rate * 100)}%`],
        ["Creadores nuevos", `${Math.round(metrics.new_creator_share * 100)}%`],
        ["Diversidad", metrics.diversity_index],
        ["Eventos", metrics.events],
        ["Comentarios", metrics.comments ?? 0],
        ["Compartidos", metrics.shares ?? 0],
        ["Follows", metrics.follows ?? 0],
        ["Hashtags", metrics.hashtag_taps ?? 0],
      ]
    : [];

  useGSAP(
    () => {
      if (!cards.length) return;
      gsap.from("[data-metric]", { y: 16, autoAlpha: 0, stagger: 0.05, duration: duration(0.38), ease: "power3.out" });
    },
    { dependencies: [cards.length], scope: grid },
  );

  return (
    <main className="min-h-full bg-paper px-5 py-10 text-ink sm:px-10">
      <p className="text-sm text-ink/60">Laboratorio · Orange Data Mining</p>
      <h1 className="mt-2 font-display text-4xl font-extrabold text-balance">Mesa de señales</h1>
      <p className="mt-3 max-w-xl text-ink/70">
        Estas cifras salen de Mongo, no de la tabla del reporte. Exporta el CSV e impórtalo en Orange para correlación,
        PCA y K-Means como en el Capítulo III.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void simulate()}
          className="h-11 rounded-lg bg-ink px-4 text-paper"
        >
          Correr simulador
        </button>
        <button
          type="button"
          onClick={downloadCsv}
          className="h-11 rounded-lg border border-ink/20 px-4"
        >
          Descargar CSV para Orange
        </button>
      </div>
      {simNote && (
        <p className="mt-4 text-sm text-lab" role="status">
          {simNote}
        </p>
      )}
      <section ref={grid} className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(([label, value]) => (
          <article key={String(label)} data-metric className="rounded-2xl bg-paper-2 p-5">
            <p className="text-sm text-ink/60">{label}</p>
            <p className="mt-2 font-display text-3xl tabular">{value}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
