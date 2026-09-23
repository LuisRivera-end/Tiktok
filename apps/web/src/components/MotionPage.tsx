import { useRef, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { duration, gsap, useGSAP } from "@/lib/motion";

export function MotionPage({ children }: { children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useGSAP(
    () => {
      if (!root.current) return;
      gsap.fromTo(
        root.current,
        { opacity: 0, y: 14 },
        { opacity: 1, y: 0, duration: duration(0.36), ease: "power3.out" },
      );
    },
    { dependencies: [location.pathname], scope: root },
  );

  return (
    <div ref={root} className="min-h-full">
      {children}
    </div>
  );
}
