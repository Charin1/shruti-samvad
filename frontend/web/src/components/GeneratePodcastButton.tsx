"use client";

import { useMutation } from "@tanstack/react-query";
import { Mic, Library } from "lucide-react";
import { createEpisode } from "@/lib/api";
import { useReaderStore } from "@/lib/store";

export function GeneratePodcastButton({ articleId }: { articleId: string }) {
  const setView = useReaderStore((s) => s.setView);
  const gen = useMutation({
    mutationFn: () => createEpisode({ article_ids: [articleId] }),
  });

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <button
        onClick={() => gen.mutate()}
        disabled={gen.isPending || gen.isSuccess}
        className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60"
      >
        <Mic size={15} />
        {gen.isPending ? "Queuing…" : gen.isSuccess ? "Queued" : "Generate Podcast"}
      </button>
      {gen.isSuccess && (
        <button
          onClick={() => setView("library")}
          className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
        >
          <Library size={13} /> Open Podcast Library
        </button>
      )}
      {gen.isError && (
        <span className="text-xs text-destructive">
          {(gen.error as Error).message}
        </span>
      )}
    </div>
  );
}
