import type { FeedItem } from "@/lib/api";

const PALETTES: Record<string, [string, string, string]> = {
  comedia: ["#3a2418", "#e39b6a", "#8c4a32"],
  ciencia: ["#102226", "#4db8b0", "#1d4d4a"],
  musica: ["#241428", "#c97bb0", "#5a2a4a"],
  cocina: ["#2a1c12", "#d97746", "#6a3a1c"],
  deporte: ["#1b3d28", "#6ecf8a", "#2f6a42"],
  arte: ["#1a1224", "#8e7cc3", "#3a2a58"],
  idiomas: ["#1a2a40", "#7aa2d6", "#2a3a58"],
  tecnologia: ["#152028", "#4db8b0", "#e39b6a"],
  naturaleza: ["#17321a", "#8fbf5a", "#2a4018"],
  historia: ["#1c1610", "#c4a574", "#5a4030"],
  baile: ["#1a1020", "#e25c4a", "#e39b6a"],
  manualidades: ["#181410", "#d2b48c", "#6a5030"],
  salud: ["#16382c", "#7dcea0", "#1e4a38"],
  cine: ["#3a1616", "#c45a5a", "#e39b6a"],
  emprendimiento: ["#14120c", "#e39b6a", "#4db8b0"],
};

function seedNum(seed: string): number {
  let hash = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    hash ^= seed.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function Poster({ item, paused }: { item: FeedItem; paused: boolean }) {
  const [field, flare, shade] = PALETTES[item.video.category] ?? PALETTES.tecnologia;
  const seed = seedNum(item.video.poster_seed || item.video.id);
  const angle = -32 + (seed % 48);
  const flareX = 12 + (seed % 55);
  const flareY = 10 + ((seed >> 6) % 45);
  const shadeX = 55 + ((seed >> 12) % 40);
  const shadeY = 50 + ((seed >> 18) % 40);

  return (
    <div
      data-poster
      className="absolute inset-0 overflow-hidden"
      style={{
        ["--poster-field" as string]: field,
        background: `radial-gradient(120% 80% at ${flareX}% ${flareY}%, ${flare}aa, transparent 58%),
          radial-gradient(90% 70% at ${shadeX}% ${shadeY}%, ${shade}99, transparent 52%),
          linear-gradient(165deg, ${field} 0%, ${shade} 48%, ${field} 100%)`,
        filter: paused ? "saturate(0.7)" : "none",
      }}
    >
      <div
        className="absolute -left-1/4 top-[12%] h-[70%] w-[160%] opacity-50"
        style={{
          background: `repeating-linear-gradient(${angle}deg, transparent, transparent 18px, ${flare}33 18px, ${flare}33 21px)`,
          transform: paused ? "scale(0.98)" : undefined,
        }}
      />
      <p
        data-poster-category
        className="absolute left-5 right-20 top-[16%] font-display text-5xl font-extrabold leading-[0.88] text-pretty text-paper sm:text-6xl"
      >
        {item.video.category}
      </p>
    </div>
  );
}
