import { useEffect, useRef, useState, type FormEvent } from "react";

import { api, type CommentRow } from "@/lib/api";
import { duration, gsap, useGSAP } from "@/lib/motion";

type Props = {
  videoId: string;
  token: string;
  onClose: () => void;
  onPosted: () => void;
};

export function CommentSheet({ videoId, token, onClose, onPosted }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [rows, setRows] = useState<CommentRow[]>([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api<CommentRow[]>(`/videos/${videoId}/comments`, {}, token)
      .then(setRows)
      .catch(() => setError("No se pudieron cargar los comentarios"));
  }, [videoId, token]);

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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!body.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api<CommentRow>(
        `/videos/${videoId}/comments`,
        { method: "POST", body: JSON.stringify({ body: body.trim() }) },
        token,
      );
      setRows((prev) => [...prev, created]);
      setBody("");
      onPosted();
    } catch {
      setError("no se guardó, reintenta");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      ref={root}
      className="absolute inset-0 z-40 flex flex-col justify-end bg-void/50"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <button type="button" className="h-full w-full cursor-default" aria-label="Cerrar comentarios" onClick={onClose} />
      <div
        ref={panel}
        className="max-h-[55vh] rounded-t-2xl bg-ink-2 p-4 pb-6 will-change-transform"
        role="dialog"
        aria-label="Comentarios"
        onWheel={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line" />
        <p className="font-display text-lg">{rows.length} comentarios</p>
        <ul className="mt-3 max-h-[28vh] space-y-3 overflow-y-auto text-sm">
          {rows.map((row) => (
            <li key={row.id}>
              <span className="font-semibold">{row.author_name}</span> {row.body}
            </li>
          ))}
        </ul>
        <form onSubmit={(e) => void onSubmit(e)} className="mt-4 flex gap-2">
          <label className="sr-only" htmlFor="comment-body">
            Agregar comentario
          </label>
          <input
            id="comment-body"
            className="h-11 flex-1 rounded-full border border-line bg-ink px-4 text-sm"
            placeholder="Agregar comentario…"
            value={body}
            maxLength={240}
            onChange={(e) => setBody(e.target.value)}
          />
          <button type="submit" className="h-11 rounded-full bg-heat px-4 text-ink" disabled={busy}>
            Enviar
          </button>
        </form>
        {error && (
          <p className="mt-2 text-sm text-skip" role="status">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
