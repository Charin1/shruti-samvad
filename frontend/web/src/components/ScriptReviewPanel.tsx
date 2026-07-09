"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Mic } from "lucide-react";
import { getEpisode, submitScriptReview } from "@/lib/api";
import { useReaderStore } from "@/lib/store";

export function ScriptReviewPanel() {
  const { reviewingEpisodeId, setReviewingEpisode } = useReaderStore();
  const qc = useQueryClient();
  const [script, setScript] = useState("");

  const { data: episode, isLoading } = useQuery({
    queryKey: ["episode", reviewingEpisodeId],
    queryFn: () => getEpisode(reviewingEpisodeId as string),
    enabled: !!reviewingEpisodeId,
  });

  useEffect(() => {
    if (episode?.podcast_script) setScript(episode.podcast_script);
  }, [episode?.podcast_script]);

  const approve = useMutation({
    mutationFn: () =>
      submitScriptReview(reviewingEpisodeId as string, script),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["episodes"] });
      setReviewingEpisode(null);
    },
  });

  if (!reviewingEpisodeId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 animate-in fade-in duration-150">
      <div className="w-full max-w-2xl max-h-[85vh] flex flex-col bg-background rounded-lg shadow-xl border border-border/60 animate-in zoom-in-95 duration-150">
        <div className="px-5 py-4 border-b border-border/60 flex items-center gap-2">
          <Mic size={15} className="text-primary" />
          <h2 className="font-medium text-sm text-foreground">
            {episode?.title ?? "Review Script"}
          </h2>
          <button
            onClick={() => setReviewingEpisode(null)}
            className="ml-auto text-muted-foreground hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}
          {!isLoading && (
            <>
              <p className="text-xs text-muted-foreground mb-2">
                Read through the generated narration below. Edit anything
                before it's converted to audio.
              </p>
              <textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                rows={16}
                className="w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm text-foreground font-newsreader leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring resize-none"
              />
            </>
          )}
        </div>

        <div className="px-5 py-4 border-t border-border/60 flex items-center gap-3">
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending || !script.trim()}
            className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            <Mic size={14} />
            {approve.isPending ? "Sending…" : "Approve & Generate Audio"}
          </button>
          <button
            onClick={() => setReviewingEpisode(null)}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Cancel
          </button>
          {approve.isError && (
            <span className="text-xs text-destructive ml-auto">
              {(approve.error as Error).message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
