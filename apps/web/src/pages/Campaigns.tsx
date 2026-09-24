import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/context/Auth";
import { api, type Campaign, type MeProfile } from "@/lib/api";
import { genderLabels, type Gender } from "@/lib/gender";

type Stats = { impressions: number; users: number; clicks: number; ctr: number | null; spend_cents: number;
  cpc_cents: number | null; remaining_cents: number; delivery: string;
  genders: { gender: Gender; impressions: number; clicks: number; ctr: number | null }[] };
const box = "mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3";
const pct = (n: number | null) => n === null ? "Sin datos" : `${(100 * n).toFixed(1)}%`;

export function CampaignsPage() {
  const { token, user } = useAuth();
  const [rows, setRows] = useState<Campaign[]>([]);
  const [videos, setVideos] = useState<MeProfile["videos"]>([]);
  const [stats, setStats] = useState<Record<string, Stats>>({});
  const [name, setName] = useState("Campaña de laboratorio");
  const [bid, setBid] = useState(90), [budget, setBudget] = useState(4000);
  const [videoId, setVideoId] = useState(""), [url, setUrl] = useState("https://example.edu");
  const [tags, setTags] = useState(""), [categories, setCategories] = useState("");
  const [genders, setGenders] = useState<string[]>([]);
  const [days, setDays] = useState(7), [gender, setGender] = useState("");
  const [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const allowed = user?.role === "advertiser" || user?.role === "admin";
  const split = (v: string) => v.split(",").map((s) => s.trim().toLowerCase().replace(/^#/, "")).filter(Boolean);
  async function load() {
    if (!token) return;
    try {
      const campaigns = await api<Campaign[]>("/campaigns", {}, token);
      setRows(campaigns);
      const measured = await Promise.all(campaigns.map(async (row) => [row.id,
        await api<Stats>(`/campaigns/${row.id}/metrics?days=${days}${gender ? `&gender=${gender}` : ""}`, {}, token)] as const));
      setStats(Object.fromEntries(measured)); setError(null);
    } catch (err) { setError(err instanceof Error ? err.message : "No se pudieron cargar resultados"); }
  }
  useEffect(() => { void load(); }, [token, days, gender]);
  useEffect(() => {
    if (token) void api<MeProfile>("/me/profile", {}, token).then((p) => setVideos(p.videos)).catch(() => {});
  }, [token]);
  async function onSubmit(e: FormEvent) {
    e.preventDefault(); if (!token) return; setBusy(true); setError(null);
    try {
      await api("/campaigns", { method: "POST", body: JSON.stringify({ name, bid_cents: bid,
        daily_budget_cents: budget, video_id: videoId, landing_url: url,
        targeting_categories: split(categories), targeting_tags: split(tags), targeting_genders: genders }) }, token);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "No se creó la campaña"); }
    finally { setBusy(false); }
  }
  async function update(row: Campaign, body: object) {
    try { await api(`/campaigns/${row.id}`, { method: "PATCH", body: JSON.stringify(body) }, token!); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "No se guardó"); }
  }
  return <main className="min-h-full bg-ink px-5 py-10 sm:px-10">
    <h1 className="font-display text-4xl font-extrabold">Anuncios</h1>
    <p className="mt-2 max-w-2xl text-paper/70">Optimiza clics al enlace. La puja es el costo simulado por clic, en centavos; no hay pagos reales.</p>
    {allowed && <form onSubmit={onSubmit} className="mt-8 grid max-w-xl gap-3">
      <label>Nombre<input className={box} value={name} onChange={(e) => setName(e.target.value)} required /></label>
      <label>Video<select className={box} value={videoId} onChange={(e) => setVideoId(e.target.value)} required>
        <option value="">Selecciona un video propio</option>{videos.map((v) => <option key={v.id} value={v.id}>{v.title}</option>)}
      </select></label>
      {!videos.length && <p className="text-sm text-paper/60">Sube un video desde Publicar para crear tu anuncio.</p>}
      <label>Enlace de destino<input type="url" className={box} value={url} onChange={(e) => setUrl(e.target.value)} required /></label>
      <div className="grid grid-cols-2 gap-3">
        <label>Puja por clic (centavos)<input type="number" className={box} value={bid} onChange={(e) => setBid(Number(e.target.value))} min={1} required /></label>
        <label>Presupuesto diario (centavos)<input type="number" className={box} value={budget} onChange={(e) => setBudget(Number(e.target.value))} min={0} required /></label>
      </div>
      <label>Categorías, separadas por comas<input className={box} value={categories} onChange={(e) => setCategories(e.target.value)} placeholder="Todas si se deja vacío" /></label>
      <label>Etiquetas, separadas por comas<input className={box} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="Todas si se deja vacío" /></label>
      <fieldset className="rounded-lg border border-line p-3"><legend>Audiencia por género</legend>
        <label className="mr-4 inline-flex gap-2"><input type="checkbox" checked={!genders.length} onChange={() => setGenders([])} />Todos</label>
        {(["man", "woman", "other"] as Gender[]).map((g) => <label key={g} className="mr-4 inline-flex gap-2">
          <input type="checkbox" checked={genders.includes(g)} onChange={() => setGenders((old) => old.includes(g) ? old.filter((x) => x !== g) : [...old, g])} />{genderLabels[g]}</label>)}
        <p className="mt-2 text-xs text-paper/60">Todos incluye personas sin respuesta. Una selección específica requiere que la persona haya declarado ese género.</p>
      </fieldset>
      <button disabled={busy} className="h-12 rounded-lg bg-lab font-display text-ink disabled:opacity-50">{busy ? "Creando…" : "Crear campaña"}</button>
    </form>}
    {error && <p role="alert" className="mt-4 text-skip">{error}</p>}
    <div className="mt-10 flex flex-wrap items-center gap-3">
      <label>Periodo<select className={box} value={days} onChange={(e) => setDays(Number(e.target.value))}>{[1,7,30].map((d) => <option key={d} value={d}>{d} días</option>)}</select></label>
      <label>Desglose<select className={box} value={gender} onChange={(e) => setGender(e.target.value)}><option value="">Todos los géneros</option>{Object.entries(genderLabels).map(([g,l]) => <option key={g} value={g}>{l}</option>)}</select></label>
      <button onClick={() => void load()} className="rounded border border-line px-4 py-2">Actualizar resultados</button>
    </div>
    <ul className="mt-6 grid gap-4 lg:grid-cols-2">{rows.map((row) => { const m = stats[row.id]; return <li key={row.id} className="rounded-xl border border-line p-5">
      <div className="flex items-center justify-between gap-2"><h2 className="font-display text-xl">{row.name}</h2>
        <button className="rounded border border-line px-3 py-1 text-sm" onClick={() => void update(row, {status: row.status === "active" ? "paused" : "active"})}>{row.status === "active" ? "Pausar" : "Activar"}</button></div>
      <fieldset className="mt-3 text-sm"><legend>Audiencia · vacío significa Todos</legend>{(["man","woman","other"] as Gender[]).map((g) => <label className="mr-3 inline-flex gap-1" key={g}><input type="checkbox" checked={(row.targeting_genders ?? []).includes(g)} onChange={() => { const old = row.targeting_genders ?? []; void update(row, {targeting_genders: old.includes(g) ? old.filter((v) => v !== g) : [...old,g]}); }} />{genderLabels[g]}</label>)}</fieldset>
      {m && <><dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">{Object.entries({Impresiones:m.impressions, Clics:m.clicks, CTR:pct(m.ctr), "Gasto (centavos)":m.spend_cents, "CPC (centavos)":m.cpc_cents?.toFixed(1) ?? "Sin datos", "Saldo diario":m.remaining_cents}).map(([label,value]) => <div key={label}><dt className="text-paper/55">{label}</dt><dd className="text-lg tabular">{value}</dd></div>)}</dl>
      <p className="mt-3 text-sm text-paper/60">{m.delivery === "paused" ? "Campaña pausada" : m.delivery === "no_budget" ? "Presupuesto insuficiente" : "Disponible según audiencia, frecuencia y calidad"}</p>
      <table className="mt-4 w-full text-left text-xs"><thead><tr><th>Género</th><th>Impresiones</th><th>Clics</th><th>CTR</th></tr></thead><tbody>{m.genders.map((g) => <tr key={g.gender}><td className="py-1">{genderLabels[g.gender]}</td><td>{g.impressions}</td><td>{g.clicks}</td><td>{pct(g.ctr)}</td></tr>)}</tbody></table></>}
    </li>; })}</ul>
  </main>;
}
