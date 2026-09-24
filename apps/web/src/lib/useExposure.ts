import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { api, type FeedItem } from "@/lib/api";

export class PlaybackMeasure {
  watch = 0;
  coverage = 0;
  private ranges: [number, number][] = [];
  private last: number | null = null;
  resetPosition() { this.last = null; }
  sample(position: number, elapsed: number, playing: boolean) {
    if (playing && this.last !== null) {
      const delta = position - this.last;
      if (delta > 0 && delta <= elapsed * 1.5 + 100) {
        this.watch += Math.min(delta, elapsed * 1.5);
        const ranges = [...this.ranges, [this.last, position] as [number, number]].sort((a, b) => a[0] - b[0]);
        this.ranges = [];
        for (const range of ranges) {
          const tail = this.ranges.at(-1);
          if (tail && range[0] <= tail[1]) tail[1] = Math.max(tail[1], range[1]);
          else this.ranges.push([...range]);
        }
        this.coverage = this.ranges.reduce((sum, [a, b]) => sum + b - a, 0);
      }
    }
    this.last = playing ? position : null;
  }
}

type Session = { id: string; item: FeedItem; measure: PlaybackMeasure; ready: Promise<unknown>; closed: boolean; played: boolean };

async function retry<T>(operation: () => Promise<T>): Promise<T> {
  let last: unknown;
  for (let i = 0; i < 3; i++) {
    try { return await operation(); } catch (err) {
      last = err;
      if (err instanceof Error && "status" in err && Number(err.status) < 500) throw err;
      await new Promise((resolve) => window.setTimeout(resolve, 250 * (i + 1)));
    }
  }
  throw last;
}

export function useExposure(item: FeedItem | undefined, index: number, token: string, sessionId: string,
  stage: RefObject<HTMLDivElement | null>, paused: boolean, paint: (ratio: number) => void, ended: () => void) {
  const current = useRef<Session | null>(null);
  const latest = useRef({ paused, paint, ended });
  latest.current = { paused, paint, ended };
  const [error, setError] = useState("");
  const watchRef = useRef(0);
  const dispatch = useCallback(async (s: Session, type: string, reason?: string, context?: Record<string, string>) => {
    const event = { event_id: crypto.randomUUID(), exposure_id: s.id, event_ts: new Date().toISOString(),
      session_id: sessionId, video_id: s.item.video_id, event_type: type,
      watch_ms: Math.round(s.measure.watch), coverage_ms: Math.round(s.measure.coverage),
      duration_ms: s.item.video.duration_ms, completion_ratio: s.measure.coverage / s.item.video.duration_ms,
      feed_position: s.item.position, close_reason: reason, context: context ?? {} };
    await s.ready;
    await retry(() => api("/events", { method: "POST", body: JSON.stringify({ events: [event] }), keepalive: true }, token));
  }, [sessionId, token]);
  const report = useCallback((err: unknown) => {
    setError(err instanceof Error ? err.message : "No se pudo registrar la exposición");
    if (err instanceof Error && "status" in err && err.status === 409) window.dispatchEvent(new Event("veta:refresh-feed"));
  }, []);
  const close = useCallback((reason = "exit") => {
    const s = current.current;
    if (!s || s.closed) return;
    s.closed = true;
    void dispatch(s, "close", reason).catch(report);
  }, [dispatch, report]);
  const send = useCallback(async (type: string, extra: { context?: Record<string, string>; watch_ms?: number; is_ad?: boolean } = {}) => {
    const s = current.current;
    if (s) await dispatch(s, type, undefined, extra.context).catch(report);
  }, [dispatch, report]);
  const click = useCallback(async () => {
    const s = current.current;
    if (!s?.item.landing_url) return;
    // Create the tab synchronously in the user gesture to avoid popup blocking.
    const tab = window.open("about:blank", "_blank");
    if (tab) tab.opener = null;
    try {
      await s.ready;
      const result = await retry(() => api<{ landing_url: string }>("/campaigns/click", {
        method: "POST", body: JSON.stringify({ exposure_id: s.id }),
      }, token));
      close("ad_click");
      if (tab) tab.location.href = result.landing_url;
      else window.location.assign(result.landing_url);
    } catch (err) { tab?.close(); report(err); }
  }, [close, token, report]);
  useEffect(() => {
    if (!item) return;
    let cancelled = false;
    let tick: number | undefined;
    let s: Session | null = null;
    setError("");
    watchRef.current = 0;
    // React StrictMode's probe must not create a second impression.
    const start = () => {
      if (cancelled || s || document.hidden) return;
      const id = crypto.randomUUID();
      const startedAt = new Date().toISOString();
      s = { id, item, measure: new PlaybackMeasure(), closed: false, played: false,
        ready: retry(() => api("/exposures", { method: "POST", body: JSON.stringify({
          exposure_id: id, decision_id: item.decision_id, video_id: item.video_id, session_id: sessionId, started_at: startedAt,
        }) }, token)) };
      current.current = s;
      void s.ready.catch(report);
      void dispatch(s, "impression").catch(report);
      let previous = performance.now(), heartbeat = previous;
      tick = window.setInterval(() => {
        if (!s || s.closed) return;
        const video = stage.current?.querySelector("video");
        const now = performance.now();
        const visible = !document.hidden && !!stage.current && stage.current.getBoundingClientRect().bottom > 0;
        const playing = !!video && !video.paused && !video.seeking && video.readyState >= 3 && visible && !latest.current.paused;
        s.measure.sample((video?.currentTime ?? 0) * 1000, now - previous, playing);
        previous = now;
        watchRef.current = s.measure.watch;
        if (playing && !s.played) { s.played = true; void dispatch(s, "play").catch(report); }
        latest.current.paint((video?.currentTime ?? 0) * 1000 / item.video.duration_ms);
        if (now - heartbeat >= 5000 && s.played) { heartbeat = now; void dispatch(s, "heartbeat").catch(report); }
        if (video?.ended) { close("ended"); latest.current.ended(); }
      }, 200);
    };
    queueMicrotask(start);
    document.addEventListener("visibilitychange", start);
    const pagehide = () => close("exit");
    window.addEventListener("pagehide", pagehide);
    return () => {
      cancelled = true;
      window.clearInterval(tick);
      window.removeEventListener("pagehide", pagehide);
      document.removeEventListener("visibilitychange", start);
      if (s && !s.closed) { s.closed = true; void dispatch(s, "close", "exit").catch(report); }
      if (current.current === s) current.current = null;
    };
  }, [item?.decision_id, item?.video_id, index, token, sessionId, dispatch, report, stage, close]); // item is captured per exposure
  return { send, close, click, watchRef, error, resetPosition: () => current.current?.measure.resetPosition() };
}
