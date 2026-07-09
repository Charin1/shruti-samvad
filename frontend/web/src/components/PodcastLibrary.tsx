"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Mic,
  RefreshCw,
  FileEdit,
  Download,
} from "lucide-react";
import {
  listEpisodes,
  getEpisode,
  createEpisode,
  PODCAST_API,
  type Episode,
  type EpisodeStatus,
} from "@/lib/api";
import { useReaderStore } from "@/lib/store";
import { useEpisodeStream } from "@/lib/useEpisodeStream";

const STATUS_LABELS: Record<EpisodeStatus, string> = {
  pending: "Waiting",
  fetching: "Fetching",
  summarizing: "Summarising",
  scripting: "Writing script",
  awaiting_review: "Review needed",
  synthesizing: "Generating audio",
  saving: "Saving",
  done: "Ready",
  error: "Failed",
};

// "awaiting_review" is intentionally excluded — nothing is in flight until
// the user acts, so it shouldn't keep the polling loop alive.
const ACTIVE = new Set<EpisodeStatus>([
  "pending",
  "fetching",
  "summarizing",
  "scripting",
  "synthesizing",
  "saving",
]);

async function downloadAudio(url: string, filename: string) {
  // A plain <a download> doesn't force a download for cross-origin URLs (the
  // podcast API runs on a different port than the frontend) — browsers just
  // navigate to it instead. Fetching as a blob and downloading via a local
  // object URL works regardless of origin.
  const res = await fetch(url);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(blobUrl);
}

function formatEta(seconds: number): string {
  if (seconds <= 5) return "almost done";
  if (seconds < 60) return `~${seconds}s remaining`;
  const mins = Math.round(seconds / 60);
  return `~${mins} min remaining`;
}

function StatusBadge({ status }: { status: EpisodeStatus }) {
  if (status === "done")
    return (
      <span className="flex items-center gap-1 text-xs text-green-700">
        <CheckCircle2 size={13} /> Ready
      </span>
    );
  if (status === "error")
    return (
      <span className="flex items-center gap-1 text-xs text-destructive">
        <XCircle size={13} /> Failed
      </span>
    );
  if (status === "awaiting_review")
    return (
      <span className="flex items-center gap-1 text-xs text-amber-600">
        <FileEdit size={13} /> Review needed
      </span>
    );
  if (ACTIVE.has(status))
    return (
      <span className="flex items-center gap-1 text-xs text-primary">
        <Loader2 size={13} className="animate-spin" />
        {STATUS_LABELS[status]}…
      </span>
    );
  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Clock size={13} /> {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function EpisodeCard({ episode }: { episode: Episode }) {
  const qc = useQueryClient();
  const setReviewingEpisode = useReaderStore((s) => s.setReviewingEpisode);
  const audioUrl = episode.audio_file_path
    ? `${PODCAST_API}/audio/${episode.id}.mp3`
    : null;
  const isActive = ACTIVE.has(episode.status);

  const { progress, etaSeconds } = useEpisodeStream(
    episode.id,
    isActive || episode.status === "awaiting_review"
  );

  const regenerate = useMutation({
    mutationFn: async () => {
      const detail = await getEpisode(episode.id);
      return createEpisode({
        article_ids: detail.articles.map((a) => a.article_id),
        title: detail.title ?? undefined,
        target_minutes: detail.target_minutes,
        review_requested: detail.review_requested,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["episodes"] }),
  });

  const title =
    episode.title ??
    (episode.article_titles.length > 0
      ? episode.article_titles[0]
      : "Untitled");

  return (
    <div className="px-5 py-4 border-b border-border/40">
      <div className="flex items-start justify-between gap-2">
        <p className="font-newsreader text-[15px] leading-snug text-foreground line-clamp-2">
          {title}
        </p>
        <button
          onClick={() => regenerate.mutate()}
          disabled={regenerate.isPending || isActive}
          title="Regenerate episode"
          className="shrink-0 text-muted-foreground hover:text-primary disabled:opacity-40 transition-colors mt-0.5"
        >
          <RefreshCw size={14} className={regenerate.isPending ? "animate-spin" : ""} />
        </button>
      </div>

      {episode.article_count > 1 && (
        <span className="inline-block mt-1 text-[11px] px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground">
          {episode.article_count} articles
        </span>
      )}

      <div className="flex items-center gap-3 mt-1.5">
        <StatusBadge status={episode.status} />
        <span className="text-xs text-muted-foreground">
          {new Date(episode.created_at).toLocaleString()}
        </span>
      </div>

      {isActive && progress !== null && (
        <div className="mt-2">
          <div className="h-1.5 rounded-full bg-muted/60 overflow-hidden">
            <div
              className="h-full bg-primary transition-[width] duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {progress}%{etaSeconds !== null ? ` · ${formatEta(etaSeconds)}` : ""}
          </p>
        </div>
      )}

      {episode.status === "error" && episode.error_message && (
        <p className="mt-1 text-xs text-destructive/80 line-clamp-2">
          {episode.error_message}
        </p>
      )}

      {episode.status === "awaiting_review" && (
        <button
          onClick={() => setReviewingEpisode(episode.id)}
          className="mt-2 inline-flex items-center gap-1.5 bg-amber-100 text-amber-800 px-3 py-1.5 rounded-md text-xs font-medium hover:bg-amber-200 transition-colors"
        >
          <FileEdit size={13} />
          Review Script
        </button>
      )}

      {audioUrl && (
        <div className="mt-3 flex items-center gap-2">
          <audio
            controls
            src={audioUrl}
            className="w-full h-9"
            style={{ accentColor: "#994400" }}
          />
          <button
            onClick={() =>
              downloadAudio(audioUrl, `${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.mp3`)
            }
            title="Download episode"
            className="shrink-0 text-muted-foreground hover:text-primary transition-colors"
          >
            <Download size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

export function PodcastLibrary() {
  const { data: episodes = [], isLoading } = useQuery({
    queryKey: ["episodes"],
    queryFn: listEpisodes,
    // WebSocket updates (useEpisodeStream) deliver most transitions instantly;
    // this polling stays on as a reconnect/safety-net fallback.
    refetchInterval: (query) => {
      const data = query.state.data as Episode[] | undefined;
      return data?.some((e) => ACTIVE.has(e.status)) ? 3000 : false;
    },
  });

  const activeCount = episodes.filter((e) => ACTIVE.has(e.status)).length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      <div className="px-5 py-4 border-b border-border/60 flex items-center gap-2">
        <Mic size={16} className="text-primary" />
        <h2 className="font-medium text-sm text-foreground">Podcast Library</h2>
        {activeCount > 0 && (
          <span className="ml-auto text-xs text-primary flex items-center gap-1">
            <Loader2 size={12} className="animate-spin" />
            {activeCount} generating…
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <p className="px-5 py-4 text-sm text-muted-foreground">Loading…</p>
        )}
        {!isLoading && episodes.length === 0 && (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            No episodes yet. Open an article and click{" "}
            <strong>Generate Podcast</strong>, or select multiple articles to
            build a combined episode.
          </div>
        )}
        {episodes.map((episode) => (
          <EpisodeCard key={episode.id} episode={episode} />
        ))}
      </div>
    </div>
  );
}
