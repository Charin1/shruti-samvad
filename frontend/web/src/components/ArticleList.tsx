"use client";

import { useQuery } from "@tanstack/react-query";
import { ListChecks, X } from "lucide-react";
import { listArticles, type Article } from "@/lib/api";
import { useReaderStore } from "@/lib/store";
import { CreateEpisodeBar } from "@/components/CreateEpisodeBar";

function timeAgo(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function ArticleList() {
  const {
    selectedFeedId,
    selectedArticleId,
    setSelectedArticle,
    isSelectMode,
    selectedArticleIds,
    toggleSelectMode,
    toggleArticleSelection,
  } = useReaderStore();

  const { data: articles = [], isLoading } = useQuery({
    queryKey: ["articles", selectedFeedId],
    queryFn: () => listArticles(selectedFeedId ?? undefined),
  });

  return (
    <div className="w-[380px] shrink-0 border-r border-border/60 flex flex-col h-full bg-background/40">
      <div className="px-5 py-4 border-b border-border/60 flex items-center gap-2">
        <h2 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">
          {selectedFeedId ? "Feed" : "All Articles"}
        </h2>
        <button
          onClick={toggleSelectMode}
          className={`ml-auto inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md transition-colors ${
            isSelectMode
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
          }`}
        >
          {isSelectMode ? <X size={12} /> : <ListChecks size={12} />}
          {isSelectMode ? "Cancel" : "Select"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {isLoading && (
          <p className="px-5 py-4 text-sm text-muted-foreground">Loading…</p>
        )}
        {!isLoading && articles.length === 0 && (
          <div className="px-5 py-8 text-sm text-muted-foreground">
            No articles yet. Add a feed, or hover a feed and hit refresh to
            fetch — articles appear here once the worker has pulled them.
          </div>
        )}

        <ul>
          {articles.map((a: Article) => {
            const checked = selectedArticleIds.has(a.id);
            return (
              <li key={a.id}>
                <button
                  onClick={() =>
                    isSelectMode
                      ? toggleArticleSelection(a.id)
                      : setSelectedArticle(a.id)
                  }
                  className={`w-full text-left px-5 py-3.5 border-b border-border/40 transition-colors flex items-start gap-3 ${
                    checked || (!isSelectMode && selectedArticleId === a.id)
                      ? "bg-primary/10"
                      : "hover:bg-muted/60"
                  }`}
                >
                  {isSelectMode && (
                    <input
                      type="checkbox"
                      checked={checked}
                      readOnly
                      className="mt-1 accent-primary shrink-0"
                    />
                  )}
                  <div className="min-w-0">
                    <h3 className="font-newsreader text-[15px] leading-snug text-foreground line-clamp-2">
                      {a.title}
                    </h3>
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground">
                      <span>{hostOf(a.url)}</span>
                      <span>·</span>
                      <span>{timeAgo(a.published_at)}</span>
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {isSelectMode && <CreateEpisodeBar />}
    </div>
  );
}
