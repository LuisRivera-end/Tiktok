import { useCallback, useEffect, useRef, useState } from "react";

import { CommentSheet } from "@/components/CommentSheet";
import { HeartBurst } from "@/components/HeartBurst";
import {
  IconChevronDown,
  IconChevronUp,
  IconComment,
  IconHeart,
  IconMusic,
  IconPlus,
  IconRotate,
  IconShare,
} from "@/components/Icons";
import { Poster } from "@/components/Poster";
import { ShareSheet } from "@/components/ShareSheet";
import { useClipFrame } from "@/components/Shell";
import { api, mediaSrc, type FeedItem } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useExposure } from "@/lib/useExposure";
import { captionTags } from "@/lib/hashtags";
import { duration, gsap, useGSAP } from "@/lib/motion";

type Lane = "foryou" | "following" | "friends";

type Props = {
  items: FeedItem[];
  token: string;
  sessionId: string;
  showLanes?: boolean;
  lane?: Lane;
  onLane?: (lane: Lane) => void;
  emptyHint?: string;
  onHashtag?: (tag: string) => void;
};

const SNAP_MS = 420;

export function FeedStage({
  items,
  token,
  sessionId,
  showLanes = false,
  lane = "foryou",
  onLane,
  emptyHint,
  onHashtag,
}: Props) {
  const root = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const progressEl = useRef<HTMLDivElement>(null);
  const trackEl = useRef<HTMLDivElement>(null);
  const timeEl = useRef<HTMLParagraphElement>(null);
  const holdTimer = useRef<number | null>(null);
  const lastTap = useRef(0);
  const lastGo = useRef(0);
  const advanceRef = useRef<() => void>(() => {});
  const durationRef = useRef(1);
  const seekingRef = useRef(false);
  const { setLandscape } = useClipFrame();

  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [liked, setLiked] = useState<Set<string>>(new Set());
  const [followed, setFollowed] = useState<Set<string>>(new Set());
  const [burst, setBurst] = useState(0);
  const [sheet, setSheet] = useState<"comments" | "share" | null>(null);
  const [forcedLandscape, setForcedLandscape] = useState(false);
  const [videoFailed, setVideoFailed] = useState<Set<string>>(new Set());
  const [narrow, setNarrow] = useState(() => (typeof window === "undefined" ? true : window.innerWidth < 1280));

  const item = items[index];
  durationRef.current = Math.max(item?.video.duration_ms ?? 1, 1);

  useEffect(() => {
    function onResize() {
      setNarrow(window.innerWidth < 1280);
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!item) {
      setLandscape(false);
      return;
    }
    setLandscape(false);
  }, [item, forcedLandscape, narrow, setLandscape]);

  const paintProgress = useCallback((ratio: number) => {
    const clamped = Math.min(1, Math.max(0, ratio));
    if (progressEl.current) progressEl.current.style.width = `${clamped * 100}%`;
    if (timeEl.current) {
      const total = Math.max(1, Math.round(durationRef.current / 1000));
      const current = Math.min(total, Math.floor((clamped * durationRef.current) / 1000));
      timeEl.current.textContent = `${current}s / ${total}s`;
    }
  }, []);

  const { send, close, click, watchRef, error: telemetryError, resetPosition } = useExposure(
    item, index, token, sessionId, stage, paused || !!sheet, paintProgress, () => advanceRef.current(),
  );

  useEffect(() => {
    const video = stage.current?.querySelector("video");
    if (!video) return;
    if (paused || sheet) video.pause();
    else void video.play().catch(() => {});
  }, [paused, sheet, item]);

  const seekToRatio = useCallback(
    (clientX: number) => {
      const track = trackEl.current;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / Math.max(rect.width, 1)));
      resetPosition();
      paintProgress(ratio);
      const video = stage.current?.querySelector("video");
      if (video) video.currentTime = ratio * durationRef.current / 1000;
    },
    [paintProgress],
  );

  const go = useCallback(
    (dir: 1 | -1, fromUser = false) => {
      if (!item || sheet) return;
      if (fromUser) {
        const now = performance.now();
        if (now - lastGo.current < SNAP_MS) return;
        lastGo.current = now;
      }
      const next = index + dir;
      if (next < 0 || next >= items.length) return;
      close(dir === 1 ? "next" : "previous");
      watchRef.current = 0;
      paintProgress(0);
      setPaused(false);
      setForcedLandscape(false);
      setIsScrubbing(false);
      setIndex(next);
    },
    [index, item, items.length, paintProgress, close, sheet],
  );

  const { contextSafe } = useGSAP(
    () => {
      const slides = gsap.utils.toArray<HTMLElement>("[data-slide]");
      if (!slides.length) return;
      gsap.set(slides, { x: 0, y: 0, xPercent: 0 });
      gsap.to(slides, {
        yPercent: (i) => (i - index) * 100,
        duration: duration(SNAP_MS / 1000),
        ease: "power3.out",
        overwrite: true,
      });
    },
    { dependencies: [index, items.length], scope: stage, revertOnUpdate: false },
  );

  useGSAP(
    () => {
      gsap.from("[data-rail] > button", {
        y: 18,
        autoAlpha: 0,
        stagger: 0.05,
        duration: duration(0.38),
        ease: "power3.out",
      });
    },
    { scope: root },
  );

  useEffect(() => {
    setIndex(0);
  }, [items]);

  advanceRef.current = () => go(1, false);

  const like = useCallback(() => {
    if (!item) return;
    setLiked((prev) => new Set(prev).add(item.video_id));
    setBurst((n) => n + 1);
    void send("like");
    contextSafe(() => {
      const heart = root.current?.querySelector('[aria-label="Me gusta"] svg');
      if (!heart) return;
      gsap.fromTo(heart, { scale: 0.72 }, { scale: 1, duration: duration(0.34), ease: "back.out(1.7)" });
    })();
  }, [contextSafe, item, send]);

  async function follow() {
    if (!item || item.video.followee || followed.has(item.video.creator_id)) return;
    try {
      await api("/follows", { method: "POST", body: JSON.stringify({ followee_id: item.video.creator_id }) }, token);
      setFollowed((prev) => new Set(prev).add(item.video.creator_id));
      void send("follow");
    } catch {
      /* ignore */
    }
  }

  function onPointerUp() {
    if (holdTimer.current) {
      window.clearTimeout(holdTimer.current);
      holdTimer.current = null;
    }
    if (sheet) return;
    const now = Date.now();
    if (now - lastTap.current < 280) like();
    lastTap.current = now;
    if (paused) setPaused(false);
  }

  function onPointerDown() {
    if (sheet) return;
    holdTimer.current = window.setTimeout(() => setPaused(true), 420);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (sheet) return;
      if (e.key === "ArrowDown" || e.key === "j") go(1, true);
      if (e.key === "ArrowUp" || e.key === "k") go(-1, true);
      if (e.key === "l" || e.key === "L") like();
      if (e.key === " ") {
        e.preventDefault();
        setPaused((p) => !p);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, like, sheet]);

  if (!item) {
    return (
      <div ref={root} className="flex h-full items-center justify-center p-8 text-center text-paper/70">
        {emptyHint ?? "No hay clips en el catálogo todavía."}
      </div>
    );
  }

  const followingCreator = item.video.followee || followed.has(item.video.creator_id);
  const tags = captionTags(item.video.tags);
  const desktop = !narrow;

  const rail = (
    <div data-rail className="pointer-events-auto flex flex-col items-center gap-4">
      <button
        type="button"
        className="relative flex size-12 items-center justify-center rounded-full text-sm"
        style={{ background: "linear-gradient(135deg,#4db8b0,#e39b6a)" }}
        aria-label="Seguir"
        disabled={followingCreator}
        onClick={(e) => {
          e.stopPropagation();
          void follow();
        }}
      >
        {item.video.creator_name.slice(0, 1)}
        {!followingCreator && (
          <span className="absolute -bottom-1 flex size-5 items-center justify-center rounded-full bg-skip text-paper">
            <IconPlus className="size-3" />
          </span>
        )}
      </button>
      <button
        type="button"
        className="flex flex-col items-center text-xs"
        aria-label="Me gusta"
        aria-pressed={liked.has(item.video_id)}
        onClick={(e) => {
          e.stopPropagation();
          like();
        }}
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-ink-2/90 text-heat">
          <IconHeart className="size-6" filled={liked.has(item.video_id)} />
        </span>
      </button>
      <button
        type="button"
        className="flex flex-col items-center text-xs text-paper/80"
        aria-label="Comentarios"
        onClick={(e) => {
          e.stopPropagation();
          void send("comment_open");
          setSheet("comments");
        }}
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-ink-2/90">
          <IconComment className="size-6" />
        </span>
        {item.video.comment_count}
      </button>
      <button
        type="button"
        className="flex flex-col items-center text-xs text-paper/80"
        aria-label="Compartir"
        onClick={(e) => {
          e.stopPropagation();
          void send("share_open");
          setSheet("share");
        }}
      >
        <span className="flex size-12 items-center justify-center rounded-full bg-ink-2/90">
          <IconShare className="size-6" />
        </span>
        {item.video.share_count}
      </button>
      {narrow && (
        <button
          type="button"
          className="flex flex-col items-center text-xs"
          aria-label="Rotar"
          aria-pressed={forcedLandscape}
          onClick={(e) => {
            e.stopPropagation();
            setForcedLandscape((v) => !v);
          }}
        >
          <IconRotate className="size-5" />
        </button>
      )}
    </div>
  );

  const caption = (
    <div className="max-w-[78%] text-pretty">
      {item.kind === "ad" && (
        <p className="mb-2 inline-block rounded-full bg-lab/20 px-3 py-1 text-xs text-lab">Patrocinado</p>
      )}
      {item.kind === "ad" && item.landing_url && (
        <button className="pointer-events-auto mb-3 block rounded-lg bg-lab px-4 py-2 font-semibold text-ink"
          onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); void click(); }}>Visitar sitio</button>
      )}
      <p data-clip-title className="font-display text-xl font-bold text-balance sm:text-2xl">
        {item.video.title}
      </p>
      <p className="mt-1 text-sm text-paper/80">@{item.video.creator_name.replace(/\s+/g, "").toLowerCase()}</p>
      <p className="mt-1 flex items-center gap-1.5 text-xs text-paper/55">
        <IconMusic className="size-3.5 shrink-0" />
        {item.video.audio_id}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <button
            key={tag}
            type="button"
            data-tags={tag}
            className="pointer-events-auto text-sm text-heat-2"
            onClick={(e) => {
              e.stopPropagation();
              void send("hashtag_tap", { context: { hashtag: tag } });
              onHashtag?.(tag);
            }}
          >
            #{tag}
          </button>
        ))}
      </div>
    </div>
  );

  const slides = items.map((entry, i) => {
    const wide = entry.video.width / Math.max(entry.video.height, 1) >= 1.2;
    const srcEntry = mediaSrc(entry.video.media_url);
    return (
      <article
        key={entry.video_id + entry.kind}
        data-slide
        className="absolute inset-0 will-change-transform"
        aria-hidden={i !== index}
      >
        <Poster item={entry} paused={paused && i === index} />
        {srcEntry && i === index && !videoFailed.has(entry.video_id) && (
          <video
            className={
              wide || forcedLandscape
                ? "absolute left-1/2 top-1/2 max-h-[56%] w-[92%] -translate-x-1/2 -translate-y-1/2 object-contain"
                : "absolute inset-0 h-full w-full object-contain"
            }
            src={srcEntry}
            muted
            playsInline
            autoPlay={!paused}
            onError={() => setVideoFailed((prev) => new Set(prev).add(entry.video_id))}
          />
        )}
        <div className="absolute inset-x-0 bottom-0 h-36 bg-gradient-to-t from-void/85 to-transparent" />
      </article>
    );
  });

  const sheets = (
    <>
      {sheet === "comments" && (
        <CommentSheet
          videoId={item.video_id}
          token={token}
          onClose={() => setSheet(null)}
          onPosted={() => {
            void send("comment");
            item.video.comment_count += 1;
          }}
        />
      )}
      {sheet === "share" && (
        <ShareSheet
          videoId={item.video_id}
          token={token}
          onClose={() => setSheet(null)}
          onShared={() => {
            void send("share");
            item.video.share_count += 1;
          }}
        />
      )}
    </>
  );

  return (
    <div
      ref={root}
      className={cn("h-full bg-void", desktop && "flex items-center justify-center gap-5 px-4")}
      onWheel={(e) => {
        if (sheet) return;
        if (Math.abs(e.deltaY) < 40) return;
        go(e.deltaY > 0 ? 1 : -1, true);
      }}
    >
      <section
        ref={stage}
        className={
          desktop
            ? "relative h-[min(92dvh,860px)] aspect-[9/16] overflow-hidden rounded-lg bg-void"
            : "relative h-full w-full overflow-hidden bg-void"
        }
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerLeave={() => holdTimer.current && window.clearTimeout(holdTimer.current)}
        role="region"
        aria-label="Escenario de clips"
        data-video-id={item.video_id}
      >
        {slides}
        {showLanes && !desktop && (
          <div className="pointer-events-none absolute inset-x-0 top-0 z-10 p-4 pt-[max(0.75rem,env(safe-area-inset-top))]">
            <div className="pointer-events-auto flex justify-center gap-5 text-sm font-semibold">
              <button
                type="button"
                className={lane === "following" ? "border-b-2 border-paper pb-0.5" : "text-paper/50"}
                onClick={() => onLane?.("following")}
              >
                Siguiendo
              </button>
              <button
                type="button"
                className={lane === "foryou" ? "border-b-2 border-paper pb-0.5" : "text-paper/50"}
                onClick={() => onLane?.("foryou")}
              >
                Para ti
              </button>
            </div>
          </div>
        )}
        <HeartBurst burstId={burst} />
        {telemetryError && <p role="status" className="absolute top-16 z-30 rounded bg-ink/90 p-2 text-xs text-paper">{telemetryError}</p>}
        <div
          className={cn(
            "pointer-events-none absolute inset-x-0 bottom-12 z-10 px-4",
            desktop ? "" : "flex items-end justify-between",
          )}
        >
          {caption}
          {!desktop && rail}
        </div>
        <div
          className="group/timeline absolute inset-x-0 bottom-0 z-20 flex items-center gap-3 px-3 pb-2 pt-1"
          onPointerDown={(e) => e.stopPropagation()}
          onPointerUp={(e) => e.stopPropagation()}
        >
          <div
            ref={trackEl}
            role="slider"
            aria-label="Tiempo del clip"
            aria-valuemin={0}
            aria-valuemax={Math.round(item.video.duration_ms / 1000)}
            tabIndex={0}
            className="flex h-5 min-w-0 flex-1 cursor-pointer items-center"
            onPointerDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
              seekingRef.current = true;
              setIsScrubbing(true);
              e.currentTarget.setPointerCapture(e.pointerId);
              seekToRatio(e.clientX);
            }}
            onPointerMove={(e) => {
              if (!seekingRef.current) return;
              e.stopPropagation();
              seekToRatio(e.clientX);
            }}
            onPointerUp={(e) => {
              e.stopPropagation();
              seekingRef.current = false;
              setIsScrubbing(false);
              if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                e.currentTarget.releasePointerCapture(e.pointerId);
              }
            }}
            onPointerCancel={(e) => {
              seekingRef.current = false;
              setIsScrubbing(false);
              if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                e.currentTarget.releasePointerCapture(e.pointerId);
              }
            }}
            onKeyDown={(e) => {
              if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
              e.preventDefault();
              const delta = e.key === "ArrowRight" ? 1000 : -1000;
              const video = stage.current?.querySelector("video");
              resetPosition();
              if (video) video.currentTime = Math.min(durationRef.current / 1000, Math.max(0, video.currentTime + delta / 1000));
            }}
          >
            <div className="relative h-1 w-full rounded-full bg-paper/25">
              <div ref={progressEl} className="relative h-full w-0 rounded-full bg-heat">
                <span className="absolute right-0 top-1/2 size-2.5 -translate-y-1/2 translate-x-1/2 rounded-full bg-paper" />
              </div>
            </div>
          </div>
          <p
            ref={timeEl}
            className={cn(
              "timeline-counter shrink-0 tabular text-[11px] text-paper/80 transition-opacity duration-200",
              isScrubbing ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
            )}
          >
            0s / {Math.max(1, Math.round(item.video.duration_ms / 1000))}s
          </p>
        </div>
        {sheets}
      </section>
      {desktop && rail}
      {desktop && (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            className="flex size-12 items-center justify-center rounded-full bg-ink-2 text-xl text-paper/80 hover:text-paper"
            aria-label="Anterior"
            onClick={() => go(-1, true)}
          >
            <IconChevronUp className="size-6" />
          </button>
          <button
            type="button"
            className="flex size-12 items-center justify-center rounded-full bg-ink-2 text-xl text-paper/80 hover:text-paper"
            aria-label="Siguiente"
            onClick={() => go(1, true)}
          >
            <IconChevronDown className="size-6" />
          </button>
        </div>
      )}
    </div>
  );
}
