import { useRef } from "react";

import { IconHeart } from "@/components/Icons";
import { duration, gsap, useGSAP } from "@/lib/motion";

export function HeartBurst({ burstId }: { burstId: number }) {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (!burstId || !root.current) return;
      const hearts = root.current.querySelectorAll("[data-heart]");
      gsap.fromTo(
        hearts,
        { y: 0, scale: 0.4, autoAlpha: 1 },
        {
          y: (i) => -80 - i * 18,
          x: (i) => (i % 2 === 0 ? -24 : 28) * (1 + i * 0.15),
          scale: 1,
          autoAlpha: 0,
          duration: duration(0.7),
          stagger: 0.04,
          ease: "power2.out",
        },
      );
    },
    { dependencies: [burstId], scope: root },
  );

  if (!burstId) return null;
  return (
    <div ref={root} className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
      {Array.from({ length: 5 }).map((_, i) => (
        <span key={`${burstId}-${i}`} data-heart className="absolute text-heat" aria-hidden="true">
          <IconHeart className="size-10" filled />
        </span>
      ))}
    </div>
  );
}
