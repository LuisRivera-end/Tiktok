const BASE = import.meta.env.VITE_API_URL || "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = "No se pudo completar la petición";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  age: number;
};

export type AuthResponse = {
  access_token: string;
  user: User;
};

export type FeedItem = {
  kind: "organic" | "ad";
  video_id: string;
  campaign_id: string | null;
  creative_id: string | null;
  source: string;
  position: number;
  scores: Record<string, number>;
  reasons: string[];
  video: {
    id: string;
    title: string;
    description: string;
    category: string;
    tags: string[];
    audio_id: string;
    duration_ms: number;
    poster_seed: string;
    media_path: string | null;
    media_url: string | null;
    play_count: number;
    creator_id: string;
    creator_name: string;
    width: number;
    height: number;
    comment_count: number;
    share_count: number;
    followee: boolean;
  };
};

export type FeedResponse = {
  items: FeedItem[];
  trace: Record<string, unknown>;
  latency_ms: number;
  new_user: boolean;
};

export type Metrics = {
  retention_minutes: number;
  completion_rate: number;
  early_abandon_rate: number;
  new_creator_share: number;
  diversity_index: number;
  ad_fill_rate: number;
  events: number;
  active_users?: number;
  comments?: number;
  shares?: number;
  follows?: number;
  hashtag_taps?: number;
  comment_opens?: number;
  share_opens?: number;
};

export type CommentRow = {
  id: string;
  user_id: string;
  author_name: string;
  body: string;
  created_at: string;
};

export type InboxRow = {
  id: string;
  from_user_id: string;
  from_name: string;
  video_id: string;
  video_title: string;
  created_at: string;
};

export type ShareTarget = {
  id: string;
  display_name: string;
  role: string;
};

export type MeProfile = {
  user: User;
  clip_count: number;
  follow_count: number;
  following?: Array<{ id: string; display_name: string }>;
  videos: Array<{
    id: string;
    title: string;
    category: string;
    poster_seed: string;
    width: number;
    height: number;
    media_url: string | null;
  }>;
};

export type VideoOut = FeedItem["video"] & { age_restricted?: boolean; status?: string };

export function mediaSrc(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${BASE}${url}`;
}

export type Campaign = {
  id: string;
  name: string;
  status: string;
  bid_cents: number;
  daily_budget_cents: number;
  spent_today_cents: number;
  targeting_tags: string[];
  targeting_categories: string[];
};
