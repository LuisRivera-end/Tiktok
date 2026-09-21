import { useGSAP } from "@gsap/react";
import gsap from "gsap";

gsap.registerPlugin(useGSAP);

export const MOTION = {
  ease: "power3.out",
  snap: 0.42,
  sheet: 0.4,
  enter: 0.36,
  pop: 0.32,
} as const;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function duration(seconds: number): number {
  return prefersReducedMotion() ? 0 : seconds;
}

export function initGsap() {
  gsap.defaults({
    ease: MOTION.ease,
    duration: MOTION.enter,
    overwrite: "auto",
  });
}

export { gsap, useGSAP };
