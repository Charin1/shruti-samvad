"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Rss, Plus, RefreshCw, Trash2, Inbox, Pencil, Check, X, Library } from "lucide-react";
import {
  createFeed,
  deleteFeed,
  listFeeds,
  refreshFeed,
  updateFeed,
  type Feed,
} from "@/lib/api";
import { useReaderStore } from "@/lib/store";

export function Sidebar() {
  const qc = useQueryClient();
  const { view, selectedFeedId, setSelectedFeed, setView } = useReaderStore();
  const [adding, setAdding] = useState(false);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [editingFeedId, setEditingFeedId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editFreq, setEditFreq] = useState("");
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const { data: feeds = [], isLoading } = useQuery({
    queryKey: ["feeds"],
    queryFn: listFeeds,
  });

  const addFeed = useMutation({
    mutationFn: createFeed,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feeds"] });
      setUrl("");
      setTitle("");
      setAdding(false);
    },
  });

  const refresh = useMutation({
    mutationFn: refreshFeed,
    onSuccess: () => {
      setRefreshError(null);
      // Poll a few times — the arq worker typically takes 3-6s to fetch + save.
      [3000, 6000, 10000].forEach((ms) =>
        setTimeout(() => qc.invalidateQueries({ queryKey: ["articles"] }), ms)
      );
    },
    onError: (err: Error) => {
      setRefreshError(err.message);
      setTimeout(() => setRefreshError(null), 4000);
    },
  });

  const edit = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title?: string; update_frequency_minutes?: number } }) =>
      updateFeed(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feeds"] });
      setEditingFeedId(null);
    },
  });

  const remove = useMutation({
    mutationFn: deleteFeed,
    onSuccess: (_d, feedId) => {
      qc.invalidateQueries({ queryKey: ["feeds"] });
      if (selectedFeedId === feedId) setSelectedFeed(null);
    },
  });

  function startEdit(feed: Feed) {
    setEditingFeedId(feed.id);
    setEditTitle(feed.title);
    setEditUrl(feed.url);
    setEditFreq(String(feed.update_frequency_minutes));
  }

  function cancelEdit() {
    setEditingFeedId(null);
  }

  function submitEdit(feedId: string) {
    const data: { title?: string; url?: string; update_frequency_minutes?: number } = {};
    if (editTitle.trim()) data.title = editTitle.trim();
    if (editUrl.trim()) data.url = editUrl.trim();
    const freq = parseInt(editFreq, 10);
    if (!isNaN(freq) && freq > 0) data.update_frequency_minutes = freq;
    if (Object.keys(data).length > 0) edit.mutate({ id: feedId, data });
    else setEditingFeedId(null);
  }

  return (
    <aside className="w-72 shrink-0 bg-sidebar border-r border-border/60 flex flex-col h-full">
      <div className="px-5 py-5">
        <h1 className="font-newsreader text-2xl text-primary font-semibold">
          Shruti Samvad
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Your intelligence inbox
        </p>
      </div>

      <nav className="px-3 flex-1 overflow-y-auto">
        <button
          onClick={() => setSelectedFeed(null)}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
            view === "reader" && selectedFeedId === null
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-muted text-foreground"
          }`}
        >
          <Inbox size={16} /> All Articles
        </button>
        <button
          onClick={() => setView("library")}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors ${
            view === "library"
              ? "bg-primary/10 text-primary font-medium"
              : "hover:bg-muted text-foreground"
          }`}
        >
          <Library size={16} /> Podcast Library
        </button>

        <div className="flex items-center justify-between px-3 mt-5 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Feeds
          </span>
          <button
            onClick={() => setAdding((v) => !v)}
            className="text-muted-foreground hover:text-primary"
            title="Add feed"
          >
            <Plus size={16} />
          </button>
        </div>

        {adding && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (url && title) addFeed.mutate({ url, title });
            }}
            className="px-3 pb-3 space-y-2"
          >
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Feed name"
              className="w-full text-sm px-2 py-1.5 rounded-md bg-background border border-border focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/feed.xml"
              className="w-full text-sm px-2 py-1.5 rounded-md bg-background border border-border focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <button
              type="submit"
              disabled={addFeed.isPending || !url || !title}
              className="w-full text-sm bg-primary text-primary-foreground rounded-md py-1.5 font-medium disabled:opacity-50"
            >
              {addFeed.isPending ? "Adding…" : "Add feed"}
            </button>
            {addFeed.isError && (
              <p className="text-xs text-destructive">
                {(addFeed.error as Error).message}
              </p>
            )}
          </form>
        )}

        {refreshError && (
          <p className="mx-3 mb-2 text-xs text-destructive bg-destructive/10 rounded px-2 py-1">
            Refresh failed: {refreshError}
          </p>
        )}

        {isLoading && (
          <p className="px-3 py-2 text-sm text-muted-foreground">Loading…</p>
        )}
        {!isLoading && feeds.length === 0 && !adding && (
          <p className="px-3 py-2 text-sm text-muted-foreground">
            No feeds yet. Click + to add one.
          </p>
        )}

        <ul className="space-y-0.5">
          {feeds.map((feed: Feed) => (
            <li key={feed.id} className="group">
              {editingFeedId === feed.id ? (
                <div className="px-3 py-2 space-y-1.5">
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="Feed name"
                    className="w-full text-sm px-2 py-1 rounded-md bg-background border border-border focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                  <input
                    value={editUrl}
                    onChange={(e) => setEditUrl(e.target.value)}
                    placeholder="Feed URL"
                    className="w-full text-sm px-2 py-1 rounded-md bg-background border border-border focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                  <div className="flex items-center gap-1.5">
                    <input
                      value={editFreq}
                      onChange={(e) => setEditFreq(e.target.value)}
                      placeholder="Refresh (min)"
                      type="number"
                      min={1}
                      className="w-full text-sm px-2 py-1 rounded-md bg-background border border-border focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                    <button
                      onClick={() => submitEdit(feed.id)}
                      disabled={edit.isPending}
                      className="text-primary hover:text-primary/80 shrink-0"
                      title="Save"
                    >
                      <Check size={15} />
                    </button>
                    <button
                      onClick={cancelEdit}
                      className="text-muted-foreground hover:text-foreground shrink-0"
                      title="Cancel"
                    >
                      <X size={15} />
                    </button>
                  </div>
                  {edit.isError && (
                    <p className="text-xs text-destructive">
                      {(edit.error as Error).message}
                    </p>
                  )}
                </div>
              ) : (
                <div
                  className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm cursor-pointer transition-colors ${
                    selectedFeedId === feed.id
                      ? "bg-primary/10 text-primary font-medium"
                      : "hover:bg-muted text-foreground"
                  }`}
                  onClick={() => setSelectedFeed(feed.id)}
                >
                  <Rss size={15} className="shrink-0" />
                  <span className="truncate flex-1">{feed.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      refresh.mutate(feed.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    title="Refresh"
                  >
                    <RefreshCw
                      size={13}
                      className={
                        refresh.isPending && refresh.variables === feed.id
                          ? "animate-spin"
                          : ""
                      }
                    />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      startEdit(feed);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    title="Edit"
                  >
                    <Pencil size={13} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Delete "${feed.title}"?`))
                        remove.mutate(feed.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                    title="Delete"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
