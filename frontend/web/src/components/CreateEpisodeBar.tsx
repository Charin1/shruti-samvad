"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { Mic, X, Sparkles } from "lucide-react";
import { createEpisode, listArticles } from "@/lib/api";
import { useReaderStore } from "@/lib/store";
import { estimateTargetMinutes, countWords } from "@/lib/estimator";

export function CreateEpisodeBar() {
  const { selectedArticleIds, clearSelection, toggleSelectMode, setView } =
    useReaderStore();
  const count = selectedArticleIds.size;

  const [title, setTitle] = useState("");
  const [targetMinutes, setTargetMinutes] = useState(3);
  const [reviewRequested, setReviewRequested] = useState(false);
  const [isAutoDetected, setIsAutoDetected] = useState(true);
  const [voice, setVoice] = useState("af_heart");
  const qc = useQueryClient();

  const { data: allArticles = [] } = useQuery({
    queryKey: ["articles"],
    queryFn: () => listArticles(),
  });

  const { data: voices = [] } = useQuery({
    queryKey: ["voices"],
    queryFn: async () => {
      const res = await fetch("http://localhost:8001/voices");
      if (!res.ok) return ["af_heart", "af_sky", "af_bella"];
      const data = await res.json();
      return data.voices || [];
    },
  });

  // Auto-detect target duration when articles change
  useEffect(() => {
    if (selectedArticleIds.size === 0 || !isAutoDetected) return;

    const selected = allArticles.filter((a) => selectedArticleIds.has(a.id));
    const totalWords = selected.reduce((sum, a) => {
      const text = a.clean_text || a.raw_html || "";
      return sum + countWords(text);
    }, 0);

    const estimated = estimateTargetMinutes(selectedArticleIds.size, totalWords);
    setTargetMinutes(estimated);
  }, [selectedArticleIds, allArticles, isAutoDetected]);

  const create = useMutation({
    mutationFn: () =>
      createEpisode({
        article_ids: Array.from(selectedArticleIds),
        title: title.trim() || undefined,
        target_minutes: targetMinutes,
        review_requested: reviewRequested,
        voice,
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
      <div className="flex items-center gap-2 mb-3">
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

      <div className="flex flex-col gap-3">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Episode title (optional)"
          className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />

        <div className="grid grid-cols-4 gap-2 items-end">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Duration</span>
            <div className="flex items-center gap-1">
              <input
                type="number"
                min={1}
                max={20}
                value={targetMinutes}
                onChange={(e) => {
                  setTargetMinutes(Number(e.target.value) || 1);
                  setIsAutoDetected(false);
                }}
                className="w-12 rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <span className="text-xs">min</span>
            </div>
          </label>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Voice</span>
            <select
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              className="rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {voices.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>

          {!isAutoDetected && (
            <button
              onClick={() => setIsAutoDetected(true)}
              className="inline-flex items-center justify-center gap-1 text-xs px-2 py-1.5 rounded-md text-primary hover:bg-primary/10 transition-colors bg-primary/5"
              title="Auto-detect duration based on article content"
            >
              <Sparkles size={11} />
              Auto
            </button>
          )}

          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer justify-end">
            <input
              type="checkbox"
              checked={reviewRequested}
              onChange={(e) => setReviewRequested(e.target.checked)}
              className="accent-primary"
            />
            <span>Review</span>
          </label>
        </div>

        <button
          onClick={() => create.mutate()}
          disabled={create.isPending}
          className="w-full inline-flex items-center justify-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60"
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
