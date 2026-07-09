"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mic, X } from "lucide-react";
import { createEpisode } from "@/lib/api";
import { useReaderStore } from "@/lib/store";

export function CreateEpisodeBar() {
  const { selectedArticleIds, clearSelection, toggleSelectMode, setView } =
    useReaderStore();
  const count = selectedArticleIds.size;

  const [title, setTitle] = useState("");
  const [targetMinutes, setTargetMinutes] = useState(3);
  const [reviewRequested, setReviewRequested] = useState(false);
  const qc = useQueryClient();

  const create = useMutation({
    mutationFn: () =>
      createEpisode({
        article_ids: Array.from(selectedArticleIds),
        title: title.trim() || undefined,
        target_minutes: targetMinutes,
        review_requested: reviewRequested,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["episodes"] });
      clearSelection();
      toggleSelectMode();
      setView("library");
    },
  });

  if (count === 0) return null;

  return (
    <div className="border-t border-border/60 bg-sidebar px-4 py-3 shadow-[0_-2px_10px_rgba(28,28,21,0.06)]">
      <div className="flex items-center gap-2 mb-2.5">
        <Mic size={14} className="text-primary shrink-0" />
        <span className="text-sm font-medium text-foreground">
          Create episode from {count} article{count > 1 ? "s" : ""}
        </span>
        <button
          onClick={clearSelection}
          className="ml-auto text-muted-foreground hover:text-foreground"
          title="Clear selection"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex flex-col gap-2">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Episode title (optional)"
          className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />

        <div className="flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            Duration
            <input
              type="number"
              min={1}
              max={20}
              value={targetMinutes}
              onChange={(e) => setTargetMinutes(Number(e.target.value) || 1)}
              className="w-14 rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            min
          </label>

          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={reviewRequested}
              onChange={(e) => setReviewRequested(e.target.checked)}
              className="accent-primary"
            />
            Review script before audio
          </label>
        </div>

        <button
          onClick={() => create.mutate()}
          disabled={create.isPending}
          className="mt-1 inline-flex items-center justify-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60"
        >
          <Mic size={14} />
          {create.isPending ? "Queuing…" : "Generate Episode"}
        </button>

        {create.isError && (
          <span className="text-xs text-destructive">
            {(create.error as Error).message}
          </span>
        )}
      </div>
    </div>
  );
}
