import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { IconMore, NAV_ICONS, type NavIconName } from "@/components/Icons";
import { MotionPage } from "@/components/MotionPage";
import { useAuth } from "@/context/Auth";
import { api, type MeProfile } from "@/lib/api";
import { cn } from "@/lib/cn";
import { duration, gsap, useGSAP } from "@/lib/motion";

const TABS: Array<{ to: string; label: string; icon: NavIconName }> = [
  { to: "/", label: "Inicio", icon: "home" },
  { to: "/amigos", label: "Amigos", icon: "friends" },
  { to: "/upload", label: "+", icon: "plus" },
  { to: "/bandeja", label: "Bandeja", icon: "inbox" },
  { to: "/yo", label: "Yo", icon: "profile" },
];

const SIDE_NAV: Array<{ to: string; label: string; icon: NavIconName; end: boolean }> = [
  { to: "/", label: "Para ti", icon: "home", end: true },
  { to: "/siguiendo", label: "Siguiendo", icon: "following", end: false },
  { to: "/amigos", label: "Amigos", icon: "friends", end: false },
  { to: "/bandeja", label: "Bandeja", icon: "inbox", end: false },
  { to: "/upload", label: "Publicar", icon: "plus", end: false },
  { to: "/yo", label: "Perfil", icon: "profile", end: false },
];

const FrameContext = createContext<{
  landscape: boolean;
  setLandscape: (value: boolean) => void;
}>({ landscape: false, setLandscape: () => undefined });

export function useClipFrame() {
  return useContext(FrameContext);
}

export function Shell() {
  const { user, token, logout } = useAuth();
  const location = useLocation();
  const [landscape, setLandscape] = useState(false);
  const [more, setMore] = useState(false);
  const [following, setFollowing] = useState<Array<{ id: string; display_name: string }>>([]);
  const value = useMemo(() => ({ landscape, setLandscape }), [landscape]);
  const edgeToEdge =
    location.pathname === "/" ||
    location.pathname === "/siguiendo" ||
    location.pathname === "/amigos" ||
    location.pathname.startsWith("/clip/");
  const aside = useRef<HTMLElement>(null);
  const moreBox = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token) return;
    void api<MeProfile>("/me/profile", {}, token)
      .then((profile) => setFollowing(profile.following ?? []))
      .catch(() => setFollowing([]));
  }, [token, location.pathname]);

  useGSAP(
    () => {
      gsap.from("[data-side-item]", {
        x: -14,
        autoAlpha: 0,
        stagger: 0.045,
        duration: duration(0.4),
        ease: "power3.out",
      });
    },
    { scope: aside },
  );

  useGSAP(
    () => {
      if (!more || !moreBox.current) return;
      gsap.from(moreBox.current.children, {
        y: -8,
        autoAlpha: 0,
        stagger: 0.04,
        duration: duration(0.28),
        ease: "power3.out",
      });
    },
    { dependencies: [more], scope: moreBox },
  );

  return (
    <FrameContext.Provider value={value}>
      <div className="h-dvh overflow-hidden bg-void text-paper xl:grid xl:grid-cols-[240px_minmax(0,1fr)] xl:grid-rows-[minmax(0,1fr)]">
        <aside ref={aside} className="hidden h-full min-h-0 flex-col overflow-y-auto border-r border-line bg-void px-3 py-4 xl:flex">
          <p data-side-item className="px-3 font-display text-3xl font-extrabold tracking-tight">
            Veta
          </p>
          <nav className="mt-6 flex flex-col gap-0.5" aria-label="Principal">
            {SIDE_NAV.map((item) => {
              const Icon = NAV_ICONS[item.icon];
              return (
                <NavLink
                  key={item.to}
                  data-side-item
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      "flex min-h-11 items-center gap-3 rounded-lg px-3 text-[15px] font-semibold",
                      isActive ? "text-heat" : "text-paper/80 hover:bg-ink-2",
                    )
                  }
                >
                  <Icon className="size-5 shrink-0" />
                  {item.label}
                </NavLink>
              );
            })}
            <button
              type="button"
              data-side-item
              className="flex min-h-11 items-center gap-3 rounded-lg px-3 text-left text-[15px] font-semibold text-paper/80 hover:bg-ink-2"
              onClick={() => setMore((open) => !open)}
            >
              <IconMore className="size-5 shrink-0" />
              Más
            </button>
            {more && (
              <div ref={moreBox} className="ml-8 mb-2 space-y-1 text-sm">
                <NavLink to="/lab" className="block rounded-md px-2 py-1.5 text-paper/70 hover:text-paper">
                  Laboratorio
                </NavLink>
                <NavLink to="/anuncios" className="block rounded-md px-2 py-1.5 text-paper/70 hover:text-paper">
                  Anuncios
                </NavLink>
                <button type="button" className="block px-2 py-1.5 text-heat" onClick={logout}>
                  Salir
                </button>
              </div>
            )}
          </nav>
          <div className="mt-4 border-t border-line pt-4">
            <p className="px-3 text-xs text-paper/45">Cuentas que sigues</p>
            <ul className="mt-2 space-y-1">
              {following.length === 0 && <li className="px-3 py-2 text-sm text-paper/40">Nadie todavía</li>}
              {following.map((person) => (
                <li key={person.id}>
                  <NavLink to="/amigos" className="flex items-center gap-2 rounded-lg px-3 py-1.5 hover:bg-ink-2">
                    <span className="flex size-8 items-center justify-center rounded-full bg-lab text-xs text-ink">
                      {person.display_name.slice(0, 1)}
                    </span>
                    <span className="truncate text-sm">{person.display_name}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
          {user && <p className="mt-auto px-3 pt-4 text-xs text-paper/40">{user.display_name}</p>}
        </aside>

        <div className="relative h-full min-h-0 min-w-0">
          <div className={cn("h-full overflow-y-auto", edgeToEdge ? "pb-0" : "pb-14 xl:pb-0")}>
            <MotionPage>
              <Outlet />
            </MotionPage>
          </div>
          <nav
            className="absolute inset-x-0 bottom-0 z-30 flex justify-around border-t border-line bg-ink/95 px-1 py-1.5 backdrop-blur xl:hidden"
            aria-label="Móvil"
          >
            {TABS.map((tab) => {
              const Icon = NAV_ICONS[tab.icon];
              return (
                <NavLink
                  key={tab.to}
                  to={tab.to}
                  end={tab.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "flex min-h-11 min-w-11 flex-col items-center justify-center px-2 text-[10px]",
                      isActive ? "text-paper" : "text-paper/45",
                    )
                  }
                  aria-label={tab.label}
                >
                  <Icon className="size-5" />
                  {tab.to !== "/upload" && <span className="mt-1">{tab.label}</span>}
                </NavLink>
              );
            })}
          </nav>
        </div>
      </div>
    </FrameContext.Provider>
  );
}
