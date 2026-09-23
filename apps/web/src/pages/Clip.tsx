import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { FeedStage } from "@/components/FeedStage";
import { useAuth } from "@/context/Auth";
import { api, type FeedItem, type VideoOut } from "@/lib/api";

export function ClipPage() {
  const { id } = useParams();
  const { token } = useAuth();
  const [item, setItem] = useState<FeedItem | null>(null);
  const [missing, setMissing] = useState(false);
  const [sessionId] = useState(() => `web-${crypto.randomUUID()}`);

  useEffect(() => {
    if (!token || !id) return;
    api<VideoOut>(`/videos/${id}`, {}, token)
      .then((video) => {
        setItem({
          kind: "organic",
          video_id: video.id,
          campaign_id: null,
          creative_id: null,
          source: "clip",
          position: 1,
          scores: {},
          reasons: [],
          video: {
            ...video,
            media_url: video.media_url ?? null,
            width: video.width ?? 1080,
            height: video.height ?? 1920,
            comment_count: video.comment_count ?? 0,
            share_count: video.share_count ?? 0,
            followee: video.followee ?? false,
          },
        });
      })
      .catch(() => setMissing(true));
  }, [id, token]);

  if (missing) {
    return (
      <main className="p-8">
        <h1 className="font-display text-2xl">Ese corte no está en el catálogo</h1>
        <Link to="/" className="mt-4 inline-block text-heat">
          Volver a Inicio
        </Link>
      </main>
    );
  }
  if (!item || !token) {
    return <main className="p-8 text-paper/70">Cargando el corte…</main>;
  }
  return (
    <main className="h-dvh">
      <FeedStage items={[item]} token={token} sessionId={sessionId} />
    </main>
  );
}
