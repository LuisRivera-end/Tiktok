import { describe, expect, it } from "vitest";

import { parseHashtags } from "@/lib/hashtags";

describe("parseHashtags", () => {
  it("parte espacios, comas y recorta a 8", () => {
    expect(parseHashtags("#A #B,C")).toEqual(["a", "b", "c"]);
    expect(parseHashtags("#laboratorio #corto #veta #x #y #z #1 #2 #3")).toHaveLength(8);
  });

  it("tira tokens inválidos", () => {
    expect(parseHashtags("#ok #Bad Tag!")).toEqual(["ok", "bad"]);
    expect(parseHashtags("#si #no!")).toEqual(["si"]);
  });
});
