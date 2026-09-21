import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/context/Auth";
import { api, type Campaign } from "@/lib/api";

export function CampaignsPage() {
  const { token } = useAuth();
  const [rows, setRows] = useState<Campaign[]>([]);
  const [name, setName] = useState("Campaña de laboratorio");
  const [bid, setBid] = useState(90);
  const [budget, setBudget] = useState(4000);
  const [videoId, setVideoId] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!token) return;
    setRows(await api<Campaign[]>("/campaigns", {}, token));
  }

  useEffect(() => {
    void load();
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    try {
      await api(
        "/campaigns",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            bid_cents: bid,
            daily_budget_cents: budget,
            targeting_categories: ["ciencia", "tecnologia"],
            targeting_tags: ["laboratorio"],
            video_id: videoId,
          }),
        },
        token,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se creó la campaña");
    }
  }

  return (
    <main className="min-h-full bg-ink px-5 py-10 sm:px-10">
      <h1 className="font-display text-4xl font-extrabold">Anuncios</h1>
      <p className="mt-2 max-w-xl text-paper/70">
        La subasta no compra el primer lugar del feed. Si no hay presupuesto o el anuncio empuja al abandono, el
        ensamblador deja el paquete orgánico intacto.
      </p>
      <form onSubmit={onSubmit} className="mt-8 grid max-w-lg gap-3">
        <label className="text-sm">
          Nombre
          <input
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          Id de video creative
          <input
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3"
            value={videoId}
            onChange={(e) => setVideoId(e.target.value)}
            required
          />
        </label>
        <label className="text-sm">
          Puja (centavos)
          <input
            type="number"
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3 tabular"
            value={bid}
            onChange={(e) => setBid(Number(e.target.value))}
            min={1}
          />
        </label>
        <label className="text-sm">
          Presupuesto diario
          <input
            type="number"
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3 tabular"
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            min={0}
          />
        </label>
        <button type="submit" className="h-12 rounded-lg bg-lab px-5 font-display text-ink">
          Crear campaña
        </button>
        {error && (
          <p role="alert" className="text-sm text-skip">
            {error}
          </p>
        )}
      </form>
      <ul className="mt-10 max-w-lg space-y-3">
        {rows.map((row) => (
          <li key={row.id} className="rounded-xl border border-line p-4">
            <p className="font-display text-xl">{row.name}</p>
            <p className="tabular text-sm text-paper/60">
              puja {row.bid_cents} · presupuesto {row.daily_budget_cents} · gastado {row.spent_today_cents}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
