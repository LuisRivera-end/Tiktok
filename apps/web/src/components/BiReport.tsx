import { useRef, type ReactNode } from "react";

import type { CategoryMetric, DashboardFocus, EventTypeMetric, RegionMetric } from "@/lib/api";
import { duration, gsap, useGSAP } from "@/lib/motion";

type Bar = { key: string; label: string; value: number; detail: string };
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

function barsFromRegions(rows: RegionMetric[]): Bar[] {
  return rows.map((row) => ({
    key: row.region,
    label: row.region,
    value: row.completion_rate,
    detail: `${percent(row.completion_rate)} · ${row.views} vistas`,
  }));
}

function barsFromCategories(rows: CategoryMetric[]): Bar[] {
  return rows.map((row) => ({
    key: row.category,
    label: row.category,
    value: row.events,
    detail: `${row.events} eventos`,
  }));
}

function barsFromTypes(rows: EventTypeMetric[]): Bar[] {
  return rows.map((row) => ({
    key: row.event_type,
    label: row.event_type,
    value: row.events,
    detail: String(row.events),
  }));
}

function Visual({ title, children, emphasis = false }: { title: string; children: ReactNode; emphasis?: boolean }) {
  return (
    <section className={emphasis ? "flex min-h-40 min-w-0 flex-col rounded-xl bg-ink p-5 text-paper" : "flex min-h-40 min-w-0 flex-col rounded-xl border border-ink/10 bg-paper p-5"}>
      <h3 className={emphasis ? "text-sm font-semibold text-paper/70" : "text-sm font-semibold text-ink/75"}>{title}</h3>
      <div className="mt-3 min-h-0 flex-1">{children}</div>
    </section>
  );
}

function CountFigure({ value, suffix = "" }: { value: number; suffix?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const decimals = Number.isInteger(value) ? 0 : String(value).split(".")[1]?.length ?? 0;
  useGSAP(() => {
    const node = ref.current;
    if (!node) return;
    const seconds = duration(0.7);
    if (seconds === 0) {
      node.textContent = `${decimals ? value.toFixed(decimals) : String(Math.round(value))}${suffix}`;
      return;
    }
    const proxy = { n: 0 };
    node.textContent = `0${suffix}`;
    gsap.to(proxy, {
      n: value,
      duration: seconds,
      ease: "power2.out",
      onUpdate: () => {
        node.textContent = `${decimals ? proxy.n.toFixed(decimals) : String(Math.round(proxy.n))}${suffix}`;
      },
    });
  }, { dependencies: [value, decimals, suffix], revertOnUpdate: true });
  return (
    <p ref={ref} className="font-display text-3xl tabular">
      {value}{suffix}
    </p>
  );
}

function BarList({
  rows,
  active,
  onPick,
}: {
  rows: Bar[];
  active: string;
  onPick?: (key: string) => void;
}) {
  const max = Math.max(...rows.map((row) => row.value), 0.0001);
  if (!rows.length) {
    return <p className="text-sm text-ink/50">Sin datos en este corte.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {rows.map((row) => {
        const pressed = row.key === active;
        return (
          <li key={row.key}>
            {onPick ? <button
              type="button"
              aria-pressed={pressed}
              onClick={() => onPick(row.key)}
              className="grid w-full grid-cols-[minmax(5rem,7rem)_minmax(2rem,1fr)_auto] items-center gap-2 rounded px-1 py-2 text-left text-sm hover:bg-ink/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lab"
            >
              <span className="truncate">{row.label}</span>
              <span className="h-3 overflow-hidden rounded-sm bg-ink/10">
                <span
                  style={{ transform: `scaleX(${Math.max(0.04, row.value / max)})` }}
                  className={pressed ? "block h-full w-full origin-left bg-heat" : "block h-full w-full origin-left bg-lab"}
                />
              </span>
              <span className="tabular whitespace-nowrap text-xs text-ink/60">{row.detail}</span>
            </button> : <div className="grid w-full grid-cols-[minmax(5rem,7rem)_minmax(2rem,1fr)_auto] items-center gap-2 px-1 py-2 text-sm">
              <span className="truncate">{row.label}</span>
              <span className="h-3 overflow-hidden rounded-sm bg-ink/10"><span style={{ transform: `scaleX(${Math.max(0.04, row.value / max)})` }} className="block h-full w-full origin-left bg-lab" /></span>
              <span className="tabular text-xs text-ink/60">{row.detail}</span>
            </div>}
          </li>
        );
      })}
    </ul>
  );
}

export function BiReport({
  regions,
  categories,
  eventTypes,
  focus,
  region,
  category,
  onRegion,
  onCategory,
}: {
  regions: RegionMetric[];
  categories: CategoryMetric[];
  eventTypes: EventTypeMetric[];
  focus: DashboardFocus | null;
  region: string;
  category: string;
  onRegion: (value: string) => void;
  onCategory: (value: string) => void;
}) {
  const scope = [region, category].filter(Boolean).join(" · ") || "Todas las regiones";

  return (
    <div className="grid min-w-0 gap-3 lg:grid-cols-2">
      <div className="grid gap-3 sm:grid-cols-2 lg:col-span-2 lg:grid-cols-4">
        <Visual title="Progreso medio de reproducción" emphasis>
          {focus?.views ? <CountFigure value={Math.round(focus.completion_rate * 1000) / 10} suffix="%" /> : <p className="font-display text-3xl">—</p>}
          <p className="mt-1 text-xs text-paper/60">{scope} · {focus?.views ?? 0} reproducciones</p>
        </Visual>
        <Visual title="Minutos vistos por usuario">
          {focus?.events ? <CountFigure value={focus.retention_minutes} /> : <p className="font-display text-3xl">—</p>}
          <p className="mt-1 text-xs text-ink/55">Tiempo acumulado del corte</p>
        </Visual>
        <Visual title="Abandono antes de 2 s">
          {focus?.views ? <CountFigure value={Math.round(focus.early_abandon_rate * 1000) / 10} suffix="%" /> : <p className="font-display text-3xl">—</p>}
          <p className="mt-1 text-xs text-ink/55">Skips cortos / reproducciones</p>
        </Visual>
        <Visual title="Eventos del corte">
          {focus ? <CountFigure value={focus.events} /> : <p className="font-display text-3xl">—</p>}
          <p className="mt-1 text-xs text-ink/55">Cruce de los filtros activos</p>
        </Visual>
      </div>
      <Visual title="Progreso medio por región del clip">
        <BarList
          rows={barsFromRegions(regions)}
          active={region}
          onPick={(value) => onRegion(value === region ? "" : value)}
        />
      </Visual>
      <Visual title="Eventos por categoría">
        <BarList
          rows={barsFromCategories(categories)}
          active={category}
          onPick={(value) => onCategory(value === category ? "" : value)}
        />
      </Visual>
      <Visual title="Tipos de evento">
        <BarList rows={barsFromTypes(eventTypes)} active="" />
      </Visual>
      <Visual title="Matriz del corte">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-ink/50">
              <tr>
                <th className="py-1 pr-3 font-medium">Región</th>
                <th className="py-1 pr-3 font-medium">Progreso</th>
                <th className="py-1 pr-3 font-medium">Min/usuario</th>
                <th className="py-1 font-medium">Eventos</th>
              </tr>
            </thead>
            <tbody>
              {regions.map((row) => (
                <tr key={row.region} className={row.region === region ? "bg-heat/15" : undefined}>
                  <td className="py-1 pr-3">
                    <button type="button" className="underline-offset-2 hover:underline" onClick={() => onRegion(row.region === region ? "" : row.region)}>
                      {row.region}
                    </button>
                  </td>
                  <td className="py-1 pr-3 tabular">{percent(row.completion_rate)}</td>
                  <td className="py-1 pr-3 tabular">{row.retention_minutes}</td>
                  <td className="py-1 tabular">{row.events}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Visual>
    </div>
  );
}
