import { useState, type FormEvent } from "react";

import { useAuth } from "@/context/Auth";
import { parseHashtags } from "@/lib/hashtags";

const CATEGORIES = [
  "comedia",
  "ciencia",
  "musica",
  "cocina",
  "deporte",
  "arte",
  "idiomas",
  "tecnologia",
  "naturaleza",
  "historia",
  "baile",
  "manualidades",
  "salud",
  "cine",
  "emprendimiento",
];

const BASE = import.meta.env.VITE_API_URL || "/api";

function readMediaMeta(file: File): Promise<{ width: number; height: number; duration_ms: number }> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      resolve({
        width: video.videoWidth || 1080,
        height: video.videoHeight || 1920,
        duration_ms: Math.round((video.duration || 14) * 1000),
      });
      URL.revokeObjectURL(url);
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      resolve({ width: 1080, height: 1920, duration_ms: 14000 });
    };
    video.src = url;
  });
}

export function UploadPage() {
  const { token, user } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hashtags, setHashtags] = useState("#laboratorio ");
  const [category, setCategory] = useState("ciencia");
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const canPublish = user?.role === "creator" || user?.role === "admin";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !canPublish) return;
    const form = new FormData();
    form.set("title", title);
    form.set("category", category);
    form.set("description", description);
    form.set("hashtags", parseHashtags(hashtags).join(" "));
    if (file) {
      const meta = await readMediaMeta(file);
      form.set("width", String(meta.width));
      form.set("height", String(meta.height));
      form.set("duration_ms", String(meta.duration_ms || 14000));
      form.set("file", file);
    } else {
      form.set("width", "1080");
      form.set("height", "1920");
      form.set("duration_ms", "14000");
    }
    const res = await fetch(`${BASE}/videos`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!res.ok) {
      setNote("No se pudo publicar. Usa una cuenta creador.");
      return;
    }
    setNote("Clip en el catálogo. Ya puede entrar al sourcing exploratorio.");
    setTitle("");
    setDescription("");
    setFile(null);
  }

  return (
    <main className="min-h-full bg-ink px-5 py-10 sm:px-10">
      <h1 className="font-display text-4xl font-extrabold">Publicar un corte</h1>
      <p className="mt-2 max-w-md text-paper/70">
        Rol actual: {user?.role}. Sube mp4 o webm, hashtags y categoría. Sin archivo se usa el póster de la categoría.
      </p>
      {!canPublish && (
        <p className="mt-6 text-heat" role="status">
          Esta cuenta no publica
        </p>
      )}
      <form onSubmit={(e) => void onSubmit(e)} className="mt-8 max-w-md space-y-4">
        <div>
          <label htmlFor="title" className="text-sm">
            Título
          </label>
          <input
            id="title"
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            disabled={!canPublish}
          />
        </div>
        <div>
          <label htmlFor="description" className="text-sm">
            Descripción
          </label>
          <textarea
            id="description"
            className="mt-1 min-h-20 w-full rounded-lg border border-line bg-ink-2 px-3 py-2"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={!canPublish}
          />
        </div>
        <div>
          <label htmlFor="hashtags" className="text-sm">
            Hashtags
          </label>
          <input
            id="hashtags"
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3"
            value={hashtags}
            onChange={(e) => setHashtags(e.target.value)}
            placeholder="#laboratorio #corto"
            disabled={!canPublish}
          />
        </div>
        <div>
          <label htmlFor="category" className="text-sm">
            Categoría
          </label>
          <select
            id="category"
            className="mt-1 h-11 w-full rounded-lg border border-line bg-ink-2 px-3"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={!canPublish}
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="file" className="text-sm">
            Video (mp4 o webm)
          </label>
          <input
            id="file"
            type="file"
            accept="video/mp4,video/webm"
            className="mt-1 w-full text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={!canPublish}
          />
        </div>
        <button
          type="submit"
          className="h-12 rounded-lg bg-heat px-5 font-display text-ink disabled:opacity-40"
          disabled={!canPublish}
        >
          Publicar
        </button>
        {note && (
          <p role="status" className="text-sm text-lab">
            {note}
          </p>
        )}
      </form>
    </main>
  );
}
