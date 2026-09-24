import { useRef, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "@/context/Auth";
import { duration, gsap, useGSAP } from "@/lib/motion";
import { GenderSelect } from "@/components/GenderSelect";
import type { Gender } from "@/lib/gender";

export function LoginPage() {
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("viewer@veta.local");
  const [password, setPassword] = useState("veta1234");
  const [name, setName] = useState("Lía");
  const [gender, setGender] = useState<Gender>("unspecified");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const page = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      gsap.from("[data-login-hero]", {
        y: 28,
        opacity: 0,
        duration: duration(0.7),
        ease: "power3.out",
      });
      gsap.from("[data-login-form] > *", {
        y: 14,
        opacity: 0,
        stagger: 0.05,
        duration: duration(0.4),
        delay: 0.08,
        ease: "power3.out",
      });
    },
    { scope: page },
  );

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register({ email, password, display_name: name, role: "viewer", gender });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo entrar");
    } finally {
      setPending(false);
    }
  }

  return (
    <main ref={page} className="grid min-h-full bg-void lg:grid-cols-2">
      <section className="relative hidden overflow-hidden lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(900px_500px_at_20%_20%,#e39b6a33,transparent),radial-gradient(700px_500px_at_80%_80%,#4db8b033,transparent)]" />
        <div data-login-hero className="relative flex h-full flex-col justify-end p-12">
          <p className="font-display text-6xl font-extrabold leading-[0.9] text-paper">
            No te sigue.
            <br />
            Te calcula.
          </p>
          <p className="mt-6 max-w-sm text-lg text-paper/70">
            Laboratorio escolar de recomendación y publicidad. El feed se queda si el clip merece el segundo.
          </p>
        </div>
      </section>
      <section className="flex items-center justify-center bg-paper px-6 py-16 text-ink">
        <form data-login-form onSubmit={onSubmit} className="w-full max-w-sm" noValidate>
          <h1 className="font-display text-4xl font-extrabold">Veta</h1>
          <p className="mt-2 text-ink/70">Entra al escenario. Demo: viewer@veta.local / veta1234</p>
          {mode === "register" && (
            <div className="mt-6">
              <label htmlFor="name" className="text-sm">
                Nombre
              </label>
              <input
                id="name"
                className="mt-1 h-11 w-full rounded-lg border border-ink/20 bg-paper-2 px-3"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="nickname"
                required
              />
            </div>
          )}
          {mode === "register" && <GenderSelect value={gender} onChange={setGender} />}
          <div className="mt-4">
            <label htmlFor="email" className="text-sm">
              Correo
            </label>
            <input
              id="email"
              type="email"
              className="mt-1 h-11 w-full rounded-lg border border-ink/20 bg-paper-2 px-3"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              aria-required="true"
            />
          </div>
          <div className="mt-4">
            <label htmlFor="password" className="text-sm">
              Clave
            </label>
            <input
              id="password"
              type="password"
              className="mt-1 h-11 w-full rounded-lg border border-ink/20 bg-paper-2 px-3"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              aria-required="true"
              aria-invalid={!!error}
              aria-describedby={error ? "auth-error" : undefined}
            />
          </div>
          {error && (
            <p id="auth-error" role="alert" className="mt-3 text-sm text-skip">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={pending}
            className="mt-6 h-12 w-full rounded-lg bg-ink font-display text-lg text-paper disabled:opacity-60"
          >
            {pending ? "Entrando…" : mode === "login" ? "Entrar al escenario" : "Crear cuenta"}
          </button>
          <button
            type="button"
            className="mt-4 text-sm text-ink/70 underline-offset-4 hover:underline"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "No tengo cuenta" : "Ya tengo cuenta"}
          </button>
        </form>
      </section>
    </main>
  );
}
