import { describe, expect, it } from "vitest";
import { PlaybackMeasure } from "./useExposure";

describe("reproducción efectiva", () => {
  it("no cuenta pausas, buffering, saltos del cursor ni cobertura repetida", () => {
    const m = new PlaybackMeasure();
    m.sample(0, 200, true); m.sample(200, 200, true);
    expect(m.watch).toBe(200); expect(m.coverage).toBe(200);
    m.sample(200, 200, false); m.sample(200, 1000, false);
    expect(m.watch).toBe(200);
    m.sample(8000, 200, true); m.sample(8200, 200, true);
    expect(m.watch).toBe(400); expect(m.coverage).toBe(400);
    m.resetPosition(); m.sample(0, 200, true); m.sample(200, 200, true);
    expect(m.watch).toBe(600); expect(m.coverage).toBe(400);
  });
});
