import { useState, type ReactNode } from "react";

import type { CategoryMetric, DailyMetric, DashboardFocus, EventTypeMetric, RegionMetric } from "@/lib/api";

type Dimension = "region" | "category";
type Measure = "events" | "completion_rate";
type DetailRow = RegionMetric | CategoryMetric;
type SortKey = "name" | "events" | "views" | "completion_rate" | "retention_minutes";

const number = new Intl.NumberFormat("es-MX");
const decimal = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 });
const percent = (value: number) => `${decimal.format(value * 100)} %`;

const EVENT_NAMES: Record<string, string> = {
  complete: "Reproducción completa",
  skip: "Omisión",
  heartbeat: "Seguimiento de reproducción",
  impression: "Impresión",
  play: "Inicio de reproducción",
  replay: "Repetición",
  like: "Me gusta",
  comment: "Comentario",
  follow: "Seguimiento de cuenta",
  share: "Compartido",
  hashtag_tap: "Toque en etiqueta",
  close: "Cierre de reproducción",
  comment_open: "Apertura de comentarios",
  share_open: "Apertura de opciones para compartir",
  ad_impression: "Impresión de anuncio",
  ad_click: "Clic en anuncio",
  ad_complete: "Anuncio visto completo",
};

function eventName(key: string): string {
  return EVENT_NAMES[key] ?? key.replaceAll("_", " ").replace(/^./, (letter) => letter.toLocaleUpperCase("es-MX"));
}

function Panel({ title, hint, children, className = "" }: { title: string; hint?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-xl border border-ink/10 bg-paper p-5 ${className}`}>
      <div className="mb-5">
        <h3 className="font-display text-lg font-bold leading-tight">{title}</h3>
        {hint && <p className="mt-1 text-xs leading-relaxed text-ink/60">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Kpi({ title, value, note, strong = false }: { title: string; value: string; note: string; strong?: boolean }) {
  return (
    <div className={`min-w-0 rounded-xl border p-5 ${strong ? "border-ink bg-ink text-paper" : "border-ink/10 bg-paper text-ink"}`}>
      <p className={`text-sm font-semibold ${strong ? "text-paper/70" : "text-ink/65"}`}>{title}</p>
      <p className="mt-4 whitespace-nowrap font-sans text-[clamp(1.45rem,2.4vw,2.25rem)] font-bold tracking-tight tabular">{value}</p>
      <p className={`mt-2 text-xs leading-snug ${strong ? "text-paper/60" : "text-ink/55"}`}>{note}</p>
    </div>
  );
}

function ActivityChart({ daily }: { daily: DailyMetric[] }) {
  const max = Math.max(1, ...daily.map((row) => Math.max(row.events, row.views)));
  if (!daily.some((row) => row.events || row.views)) {
    return <p className="py-12 text-center text-sm text-ink/55">Aún no hay actividad fechada para este corte.</p>;
  }
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-ink/65">
        <div className="flex gap-5" aria-hidden="true">
          <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm bg-lab" />Eventos</span>
          <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm bg-ink/45" />Reproducciones</span>
        </div>
        <span className="tabular">Escala máxima: {number.format(max)}</span>
      </div>
      <div className="grid h-48 items-end gap-1 border-b border-ink/15 sm:gap-3" style={{ gridTemplateColumns: `repeat(${daily.length}, minmax(0, 1fr))` }} role="img" aria-label={`Actividad diaria: ${daily.map((row) => `${row.date}, ${row.events} eventos y ${row.views} reproducciones`).join("; ")}`}>
        {daily.map((row) => (
          <div key={row.date} title={`${row.date}: ${number.format(row.events)} eventos, ${number.format(row.views)} reproducciones`} className="flex h-full min-w-0 items-end justify-center gap-0.5 sm:gap-1">
            <span className="w-1/3 max-w-7 rounded-t-sm bg-lab" style={{ height: `${row.events ? Math.max(3, row.events / max * 100) : 0}%` }} />
            <span className="w-1/3 max-w-7 rounded-t-sm bg-ink/45" style={{ height: `${row.views ? Math.max(3, row.views / max * 100) : 0}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-2 grid gap-1 text-center text-[11px] text-ink/60 sm:gap-3" style={{ gridTemplateColumns: `repeat(${daily.length}, minmax(0, 1fr))` }}>
        {daily.map((row) => <span key={row.date} className="tabular">{new Date(`${row.date}T12:00:00Z`).toLocaleDateString("es-MX", { day: "numeric", month: "short", timeZone: "UTC" })}</span>)}
      </div>
    </>
  );
}

function EventChart({ rows, total }: { rows: EventTypeMetric[]; total: number }) {
  const [order, setOrder] = useState<"count" | "name">("count");
  const sorted = [...rows].sort((a, b) => order === "count" ? b.events - a.events || eventName(a.event_type).localeCompare(eventName(b.event_type), "es") : eventName(a.event_type).localeCompare(eventName(b.event_type), "es"));
  const max = Math.max(1, ...rows.map((row) => row.events));
  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-3 text-xs text-ink/60">
        <span>{number.format(total)} eventos en el corte</span>
        <label className="flex items-center gap-2">Orden
          <select className="rounded-md border border-ink/20 bg-paper px-2 py-1.5 text-ink focus-visible:outline-2 focus-visible:outline-lab" value={order} onChange={(event) => setOrder(event.target.value as "count" | "name")}>
            <option value="count">Mayor volumen</option>
            <option value="name">Nombre</option>
          </select>
        </label>
      </div>
      {sorted.length ? <ul className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {sorted.map((row) => (
          <li key={row.event_type}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
              <span title={row.event_type} className="min-w-0 break-words">{eventName(row.event_type)}</span>
              <span className="shrink-0 tabular font-semibold">{number.format(row.events)} <span className="font-normal text-ink/50">({total ? decimal.format(row.events / total * 100) : 0} %)</span></span>
            </div>
            <div className="h-2 overflow-hidden rounded-sm bg-ink/10" aria-hidden="true">
              <div className="h-full rounded-sm bg-lab" style={{ width: `${row.events / max * 100}%` }} />
            </div>
          </li>
        ))}
      </ul> : <p className="text-sm text-ink/55">Sin eventos para este corte.</p>}
    </>
  );
}

function DimensionChart({ title, hint, rows, dimension, active, onPick }: {
  title: string;
  hint: string;
  rows: DetailRow[];
  dimension: Dimension;
  active: string;
  onPick: (value: string) => void;
}) {
  const [measure, setMeasure] = useState<Measure>("completion_rate");
  const sorted = [...rows].sort((a, b) => b[measure] - a[measure]);
  const max = Math.max(1, ...rows.map((row) => row[measure]));
  const labelOf = (row: DetailRow) => dimension === "region" ? (row as RegionMetric).region : (row as CategoryMetric).category;
  return (
    <Panel title={title} hint={hint}>
      <div className="mb-4 flex flex-wrap gap-1 rounded-lg bg-paper-2/65 p-1" role="group" aria-label={`Medida para ${title.toLocaleLowerCase("es-MX")}`}>
        {(["completion_rate", "events"] as const).map((key) => <button key={key} type="button" aria-pressed={measure === key} onClick={() => setMeasure(key)} className={`rounded-md px-3 py-1.5 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-lab ${measure === key ? "bg-ink text-paper" : "text-ink/65 hover:text-ink"}`}>{key === "completion_rate" ? "Progreso" : "Eventos"}</button>)}
      </div>
      {sorted.length ? <ul className="space-y-1">
        {sorted.map((row) => {
          const label = labelOf(row);
          const pressed = label === active;
          return <li key={label}>
            <button type="button" aria-pressed={pressed} aria-label={`${label}, ${measure === "events" ? `${number.format(row.events)} eventos` : `${percent(row.completion_rate)} de progreso medio`}. ${pressed ? "Quitar filtro" : "Filtrar"}`} onClick={() => onPick(pressed ? "" : label)} className={`grid w-full grid-cols-[minmax(0,7rem)_minmax(2rem,1fr)_auto] items-center gap-2 rounded-md px-2 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-lab sm:grid-cols-[minmax(0,9rem)_minmax(2rem,1fr)_auto] ${pressed ? "bg-heat/20" : "hover:bg-ink/5"}`}>
              <span className="truncate" title={label}>{label}</span>
              <span className="h-2.5 overflow-hidden rounded-sm bg-ink/10" aria-hidden="true"><span className={`block h-full rounded-sm ${pressed ? "bg-heat" : "bg-lab"}`} style={{ width: `${row[measure] / max * 100}%` }} /></span>
              <span className="shrink-0 tabular text-xs font-semibold">{measure === "events" ? number.format(row.events) : percent(row.completion_rate)}</span>
            </button>
          </li>;
        })}
      </ul> : <p className="text-sm text-ink/55">Sin datos para esta selección.</p>}
    </Panel>
  );
}

function csvCell(value: string | number): string {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function DetailTable({ regions, categories, region, category, onRegion, onCategory }: {
  regions: RegionMetric[];
  categories: CategoryMetric[];
  region: string;
  category: string;
  onRegion: (value: string) => void;
  onCategory: (value: string) => void;
}) {
  const [dimension, setDimension] = useState<Dimension>("region");
  const [sort, setSort] = useState<SortKey>("events");
  const [descending, setDescending] = useState(true);
  const rows = dimension === "region" ? regions : categories;
  const labelOf = (row: DetailRow) => dimension === "region" ? (row as RegionMetric).region : (row as CategoryMetric).category;
  const sorted = [...rows].sort((a, b) => {
    const delta = sort === "name" ? labelOf(a).localeCompare(labelOf(b), "es") : a[sort] - b[sort];
    return (descending ? -1 : 1) * delta;
  });
  function chooseSort(key: SortKey) {
    if (sort === key) setDescending(!descending);
    else { setSort(key); setDescending(key !== "name"); }
  }
  function download() {
    const header = [dimension === "region" ? "Región" : "Categoría", "Eventos", "Reproducciones", "Progreso medio (%)", "Minutos por usuario"];
    const lines = [header, ...sorted.map((row) => [labelOf(row), row.events, row.views, decimal.format(row.completion_rate * 100), decimal.format(row.retention_minutes)])];
    const blob = new Blob(["\uFEFF", lines.map((line) => line.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `veta-resumen-${dimension === "region" ? "regiones" : "categorias"}.csv`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const columns: { key: SortKey; label: string }[] = [
    { key: "name", label: dimension === "region" ? "Región" : "Categoría" },
    { key: "events", label: "Eventos" },
    { key: "views", label: "Reproducciones" },
    { key: "completion_rate", label: "Progreso medio" },
    { key: "retention_minutes", label: "Min/usuario" },
  ];
  return (
    <Panel title="Detalle del corte" hint="Selecciona una fila para cruzar filtros con el resto del informe." className="lg:col-span-2">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 rounded-lg bg-paper-2/65 p-1" role="group" aria-label="Dimensión de la tabla">
          {(["region", "category"] as const).map((key) => <button key={key} type="button" aria-pressed={dimension === key} onClick={() => setDimension(key)} className={`rounded-md px-3 py-1.5 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-lab ${dimension === key ? "bg-ink text-paper" : "text-ink/65 hover:text-ink"}`}>{key === "region" ? "Regiones" : "Categorías"}</button>)}
        </div>
        <button type="button" onClick={download} disabled={!sorted.length} className="rounded-md border border-ink/25 px-3 py-2 text-sm font-semibold hover:bg-ink/5 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-lab">Descargar tabla CSV</button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[39rem] border-collapse text-left text-sm">
          <thead className="border-b border-ink/20 text-xs text-ink/65">
            <tr>{columns.map((column) => <th key={column.key} scope="col" aria-sort={sort === column.key ? descending ? "descending" : "ascending" : "none"} className="py-2 pr-4 font-medium"><button type="button" onClick={() => chooseSort(column.key)} className="flex items-center gap-1 rounded text-left hover:text-ink focus-visible:outline-2 focus-visible:outline-lab">{column.label}<span aria-hidden="true">{sort === column.key ? descending ? "↓" : "↑" : ""}</span></button></th>)}</tr>
          </thead>
          <tbody>
            {sorted.map((row) => {
              const label = labelOf(row);
              const selected = label === (dimension === "region" ? region : category);
              return <tr key={label} className={`border-b border-ink/10 ${selected ? "bg-heat/15" : ""}`}>
                <th scope="row" className="py-3 pr-4 font-semibold"><button type="button" aria-pressed={selected} onClick={() => dimension === "region" ? onRegion(selected ? "" : label) : onCategory(selected ? "" : label)} className="rounded text-left underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-lab">{label}</button></th>
                <td className="py-3 pr-4 tabular">{number.format(row.events)}</td>
                <td className="py-3 pr-4 tabular">{number.format(row.views)}</td>
                <td className="py-3 pr-4 tabular">{percent(row.completion_rate)}</td>
                <td className="py-3 pr-4 tabular">{decimal.format(row.retention_minutes)}</td>
              </tr>;
            })}
          </tbody>
        </table>
        {!sorted.length && <p className="py-5 text-sm text-ink/55">No hay filas para esta selección.</p>}
      </div>
    </Panel>
  );
}

export function BiReport({ regions, categories, eventTypes, daily, focus, region, category, onRegion, onCategory }: {
  regions: RegionMetric[];
  categories: CategoryMetric[];
  eventTypes: EventTypeMetric[];
  daily: DailyMetric[];
  focus: DashboardFocus | null;
  region: string;
  category: string;
  onRegion: (value: string) => void;
  onCategory: (value: string) => void;
}) {
  const hasViews = !!focus?.views;
  return (
    <div className="grid min-w-0 gap-4 lg:grid-cols-2">
      <div className="grid grid-cols-2 gap-2 sm:gap-3 xl:col-span-2 xl:grid-cols-4">
        <Kpi title="Reproducciones" value={number.format(focus?.views ?? 0)} note="Exposiciones con reproducción observada" strong />
        <Kpi title="Progreso medio" value={hasViews ? percent(focus!.completion_rate) : "—"} note="Porcentaje medio visto por reproducción" />
        <Kpi title="Abandono antes de 2 s" value={hasViews ? percent(focus!.early_abandon_rate) : "—"} note="Omisiones tempranas / reproducciones" />
        <Kpi title="Minutos por usuario" value={hasViews ? decimal.format(focus!.retention_minutes) : "—"} note="Tiempo visto / usuarios con reproducción" />
      </div>
      <Panel title="Actividad diaria" hint="Eventos y reproducciones del corte por día, en UTC." className="lg:col-span-2">
        <ActivityChart daily={daily} />
      </Panel>
      <Panel title="Tipos de evento" hint="Cada evento registrado cuenta una vez; una reproducción puede generar varios eventos." className="lg:col-span-2">
        <EventChart rows={eventTypes} total={focus?.events ?? 0} />
      </Panel>
      <DimensionChart title="Regiones del clip" hint="Elige una región para actualizar las otras vistas." rows={regions} dimension="region" active={region} onPick={onRegion} />
      <DimensionChart title="Categorías" hint="Elige una categoría para actualizar las otras vistas." rows={categories} dimension="category" active={category} onPick={onCategory} />
      <DetailTable regions={regions} categories={categories} region={region} category={category} onRegion={onRegion} onCategory={onCategory} />
    </div>
  );
}
