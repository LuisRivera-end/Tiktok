import { useCallback, useEffect, useState } from "react";

import { FeedStage } from "@/components/FeedStage";
import { useAuth } from "@/context/Auth";
import { api, type FeedResponse } from "@/lib/api";

type Lane = "foryou" | "following" | "friends";

export function FeedPage({ initialLane = "foryou", showLanes = true }: { initialLane?: Lane; showLanes?: boolean }) {
  const { token } = useAuth();
  const [lane, setLane] = useState<Lane>(initialLane);
  const [data, setData] = useState<FeedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => `web-${crypto.randomUUID()}`);

  const load = useCallback(() => {
    if (!token) return;
    const query = lane === "foryou" ? "foryou" : lane;
    api<FeedResponse>(`/feed?lane=${query}`, {}, token)
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, [token, lane]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setLane(initialLane);
  }, [initialLane]);

  if (error) {
    return (
      <main className="p-8">
        <h1 className="font-display text-3xl">El escenario no responde</h1>
        <p className="mt-2 text-paper/70">{error}</p>
      </main>
    );
  }
  if (!data || !token) {
    return <main className="p-8 text-paper/70">Cargando el corte…</main>;
  }

  const empty =
    lane === "friends"
      ? "Sigue a alguien desde el + del avatar"
      : lane === "following"
        ? "Sigue a alguien desde el + del avatar"
        : "No hay clips en el catálogo todavía.";

  return (
    <main className="h-full">
      <FeedStage
        items={data.items}
        token={token}
        sessionId={sessionId}
        showLanes={showLanes}
        lane={lane === "friends" ? "foryou" : lane}
        onLane={(next) => setLane(next)}
        emptyHint={empty}
        onHashtag={() => load()}
      />
    </main>
  );
}
