import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "@/context/Auth";
import { api, type InboxRow } from "@/lib/api";
import { duration, gsap, useGSAP } from "@/lib/motion";

function ago(iso: string) {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.max(1, Math.round(ms / 60000));
  if (min < 60) return `hace ${min} min`;
  const hours = Math.round(min / 60);
  if (hours < 24) return `hace ${hours} h`;
  return `hace ${Math.round(hours / 24)} d`;
}

export function InboxPage() {
  const { token } = useAuth();
  const list = useRef<HTMLUListElement>(null);
  const [rows, setRows] = useState<InboxRow[] | null>(null);

  useEffect(() => {
    if (!token) return;
    void api<InboxRow[]>("/inbox", {}, token).then(setRows);
  }, [token]);

  useGSAP(
    () => {
      if (!rows?.length) return;
      gsap.from("li", { y: 12, autoAlpha: 0, stagger: 0.05, duration: duration(0.35), ease: "power3.out" });
    },
    { dependencies: [rows?.length], scope: list },
  );

  return (
    <main className="min-h-full bg-ink px-5 py-8">
      <h1 className="font-display text-3xl font-extrabold">Bandeja</h1>
      {rows && rows.length === 0 && <p className="mt-6 text-paper/70">Nadie te ha mandado un corte</p>}
      <ul ref={list} className="mt-6 space-y-3">
        {rows?.map((row) => (
          <li key={row.id}>
            <Link to={`/clip/${row.video_id}`} className="flex items-center gap-3 rounded-xl bg-ink-2 p-3">
              <span className="flex size-11 items-center justify-center rounded-full bg-heat text-ink">
                {row.from_name.slice(0, 1)}
              </span>
              <span>
                <span className="block font-semibold">{row.from_name}</span>
                <span className="block text-sm text-paper/70">{row.video_title}</span>
                <span className="block text-xs text-paper/45">{ago(row.created_at)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
