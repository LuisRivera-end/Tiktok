const TOKEN = /^[a-z0-9-]{1,24}$/;

export function parseHashtags(raw: string, limit = 8): string[] {
  const parts = raw
    .trim()
    .toLowerCase()
    .split(/[\s,]+/)
    .map((part) => part.replace(/^#/, ""))
    .filter(Boolean);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const tag of parts) {
    if (seen.has(tag) || !TOKEN.test(tag)) continue;
    seen.add(tag);
    out.push(tag);
    if (out.length >= limit) break;
  }
  return out;
}

export function captionTags(tags: string[] | undefined): string[] {
  return (tags ?? []).filter((tag) => tag && tag !== "seed");
}
