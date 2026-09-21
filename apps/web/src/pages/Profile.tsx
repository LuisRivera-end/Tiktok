import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { IconMore } from "@/components/Icons";
import { useAuth } from "@/context/Auth";
import { api, type MeProfile } from "@/lib/api";
import { duration, gsap, useGSAP } from "@/lib/motion";

export function ProfilePage() {
  const { token, user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const grid = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token) return;
    void api<MeProfile>("/me/profile", {}, token).then(setProfile);
  }, [token]);

  useGSAP(
    () => {
      if (!profile?.videos.length) return;
      gsap.from("a", { y: 10, autoAlpha: 0, stagger: 0.03, duration: duration(0.32), ease: "power3.out" });
    },
    { dependencies: [profile?.videos.length], scope: grid },
  );

  return (
    <main className="min-h-full bg-ink px-5 py-8">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="flex size-16 items-center justify-center rounded-full bg-heat text-2xl text-ink">
            {(user?.display_name ?? "?").slice(0, 1)}
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold">{user?.display_name}</h1>
            <p className="text-sm text-paper/60">{user?.role}</p>
          </div>
        </div>
        <button type="button" className="p-1 text-paper" aria-label="Más" onClick={() => setOpen((v) => !v)}>
          <IconMore className="size-6" />
        </button>
      </div>
      {open && (
        <div className="mt-3 rounded-xl bg-ink-2 p-3 text-sm">
          <Link to="/lab" className="block py-2">
            Laboratorio
          </Link>
          <Link to="/anuncios" className="block py-2">
            Anuncios
          </Link>
          <button type="button" className="block py-2 text-heat" onClick={logout}>
            Salir
          </button>
        </div>
      )}
      <p className="mt-6 text-sm text-paper/70">
        {profile?.clip_count ?? 0} clips · {profile?.follow_count ?? 0} siguiendo
      </p>
      <div ref={grid} className="mt-4 grid grid-cols-3 gap-1">
        {profile?.videos.map((clip) => (
          <Link key={clip.id} to={`/clip/${clip.id}`} className="aspect-[9/16] bg-ink-2 p-2 text-[10px] text-paper/80">
            <span className="font-display text-sm">{clip.category}</span>
            <span className="mt-2 block truncate">{clip.title}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
