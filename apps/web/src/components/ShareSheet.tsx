import { useEffect, useRef, useState } from "react";

import { api, type ShareTarget } from "@/lib/api";
import { duration, gsap, useGSAP } from "@/lib/motion";

type Props = {
  videoId: string;
  token: string;
  onClose: () => void;
  onShared: () => void;
};

export function ShareSheet({ videoId, token, onClose, onShared }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [targets, setTargets] = useState<ShareTarget[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api<ShareTarget[]>("/users/share-targets", {}, token).then(setTargets);
  }, [token]);

  useGSAP(
    () => {
      gsap.fromTo(root.current, { autoAlpha: 0 }, { autoAlpha: 1, duration: duration(0.22) });
      gsap.fromTo(
        panel.current,
        { yPercent: 22, autoAlpha: 0 },
        { yPercent: 0, autoAlpha: 1, duration: duration(0.42), ease: "power3.out" },
      );
    },
    { scope: root },
  );

  async function sendTo(userId: string) {
    setError(null);
    try {
      await api("/inbox", { method: "POST", body: JSON.stringify({ to_user_id: userId, video_id: videoId }) }, token);
      onShared();
      onClose();
    } catch {
      setError("no se guardó, reintenta");
    }
  }

  async function copyLink() {
    const url = `${window.location.origin}/clip/${videoId}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      setNote(url);
    }
    onShared();
    setNote("Enlace copiado");
  }

  return (
    <div
      ref={root}
      className="absolute inset-0 z-40 flex flex-col justify-end bg-void/50"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <button type="button" className="h-full w-full cursor-default" aria-label="Cerrar compartir" onClick={onClose} />
      <div
        ref={panel}
        className="rounded-t-2xl bg-ink-2 p-4 pb-6 will-change-transform"
        role="dialog"
        aria-label="Compartir"
        onWheel={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line" />
        <p className="font-display text-lg">Enviar a</p>
        <div className="mt-4 flex gap-4 overflow-x-auto pb-2">
          {targets.map((person) => (
            <button
              key={person.id}
              type="button"
              className="flex w-16 shrink-0 flex-col items-center gap-1 text-xs"
              onClick={() => void sendTo(person.id)}
            >
              <span className="flex size-12 items-center justify-center rounded-full bg-lab text-sm text-ink">
                {person.display_name.slice(0, 1)}
              </span>
              {person.display_name.split(" ")[0]}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="mt-4 h-11 w-full rounded-xl bg-ink text-sm"
          onClick={() => void copyLink()}
        >
          Copiar enlace del laboratorio
        </button>
        {note && (
          <p className="mt-2 text-sm text-lab" role="status">
            {note}
          </p>
        )}
        {error && (
          <p className="mt-2 text-sm text-skip" role="status">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
