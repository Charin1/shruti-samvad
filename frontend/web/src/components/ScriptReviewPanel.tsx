"use client";

import { useEffect, useState, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X, Mic, Play, Pause, Trash2, Plus, Loader2 } from "lucide-react";
import { getEpisode, submitScriptReview, previewTts } from "@/lib/api";
import { useReaderStore } from "@/lib/store";

export function ScriptReviewPanel() {
  const { reviewingEpisodeId, setReviewingEpisode } = useReaderStore();
  const qc = useQueryClient();

  const [paragraphs, setParagraphs] = useState<string[]>([]);
  const [playingIndex, setPlayingIndex] = useState<number | null>(null);
  const [loadingIndex, setLoadingIndex] = useState<number | null>(null);
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null);

  const { data: episode, isLoading } = useQuery({
    queryKey: ["episode", reviewingEpisodeId],
    queryFn: () => getEpisode(reviewingEpisodeId as string),
    enabled: !!reviewingEpisodeId,
  });

  // Parse script into paragraphs
  useEffect(() => {
    if (episode?.podcast_script) {
      setParagraphs(
        episode.podcast_script.split("\n\n").filter((p) => p.trim() !== "")
      );
    }
  }, [episode?.podcast_script]);

  // Audio cleanup on unmount or audio changes
  useEffect(() => {
    return () => {
      if (audio) {
        audio.pause();
      }
    };
  }, [audio]);

  const togglePlay = async (index: number) => {
    if (playingIndex === index) {
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
      }
      setPlayingIndex(null);
      return;
    }

    if (audio) {
      audio.pause();
    }

    const textSnippet = paragraphs[index]?.trim ? paragraphs[index].trim() : "";
    if (!textSnippet) return;

    setLoadingIndex(index);
    try {
      const voice = episode?.voice || "af_heart";
      const blobUrl = await previewTts(textSnippet, voice);

      const newAudio = new Audio(blobUrl);
      newAudio.onended = () => {
        setPlayingIndex(null);
      };
      newAudio.onerror = () => {
        setPlayingIndex(null);
        alert("Failed to play paragraph preview.");
      };

      setAudio(newAudio);
      setPlayingIndex(index);
      setLoadingIndex(null);
      await newAudio.play();
    } catch (err) {
      console.error(err);
      alert("TTS Preview generation failed.");
      setLoadingIndex(null);
    }
  };

  const updateParagraph = (index: number, value: string) => {
    const next = [...paragraphs];
    next[index] = value;
    setParagraphs(next);
  };

  const addParagraph = (index: number) => {
    const next = [...paragraphs];
    next.splice(index + 1, 0, "");
    setParagraphs(next);
  };

  const deleteParagraph = (index: number) => {
    if (paragraphs.length === 1) {
      setParagraphs([""]);
      return;
    }
    setParagraphs(paragraphs.filter((_, i) => i !== index));
    if (playingIndex === index) {
      if (audio) audio.pause();
      setPlayingIndex(null);
    }
  };

  const approve = useMutation({
    mutationFn: () => {
      const finalScript = paragraphs
        .map((p) => p.trim())
        .filter((p) => p !== "")
        .join("\n\n");
      return submitScriptReview(reviewingEpisodeId as string, finalScript);
    },
    onSuccess: () => {
      // Optimistically update the cache to show "synthesizing" (generating audio)
      // so the UI immediately triggers the progress bar and starts polling
      qc.setQueryData<Episode[]>(["episodes"], (episodes) =>
        episodes?.map((ep) =>
          ep.id === reviewingEpisodeId
            ? { ...ep, status: "synthesizing" as EpisodeStatus }
            : ep
        )
      );

      // Delay the actual refetch slightly to let the database transaction on the worker commit
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["episodes"] });
      }, 800);

      setReviewingEpisode(null);
    },
  });

  const handleClose = () => {
    if (audio) audio.pause();
    setReviewingEpisode(null);
  };

  if (!reviewingEpisodeId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-in fade-in duration-150">
      <div className="w-full max-w-2xl h-[90vh] flex flex-col bg-background rounded-lg shadow-2xl border border-border/60 animate-in zoom-in-95 duration-150 overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border/60 flex items-center gap-2">
          <Mic size={15} className="text-primary" />
          <h2 className="font-newsreader text-base font-semibold text-foreground truncate flex-1">
            Review Script: {episode?.title ?? "Untitled Episode"}
          </h2>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-muted"
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable Paragraph Editor */}
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-3 bg-sidebar/10">
          {isLoading ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="animate-spin text-primary" size={24} />
              <p className="text-sm">Loading script...</p>
            </div>
          ) : (
            <>
              <p className="text-xs text-muted-foreground pb-2 border-b border-border/40">
                The script is divided into speech segments. Edit any segment, click **Play** to preview it, and hit approve once satisfied.
              </p>

              <div className="space-y-4 pt-2">
                {paragraphs.map((para, index) => (
                  <div key={index} className="space-y-1 group">
                    <div className="flex items-center justify-between px-1">
                      <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                        Segment #{index + 1}
                      </span>
                      <div className="flex items-center gap-2">
                        {/* Play / Preview Button */}
                        <button
                          type="button"
                          onClick={() => togglePlay(index)}
                          disabled={loadingIndex === index}
                          className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border transition-colors ${
                            playingIndex === index
                              ? "bg-primary/10 border-primary text-primary hover:bg-primary/20"
                              : "bg-background border-border/60 text-muted-foreground hover:text-foreground hover:bg-muted"
                          }`}
                          title="Preview pronunciation"
                        >
                          {loadingIndex === index ? (
                            <Loader2 size={10} className="animate-spin" />
                          ) : playingIndex === index ? (
                            <Pause size={10} />
                          ) : (
                            <Play size={10} />
                          )}
                          {playingIndex === index ? "Pause" : "Play"}
                        </button>

                        {/* Delete Button */}
                        <button
                          type="button"
                          onClick={() => deleteParagraph(index)}
                          className="text-muted-foreground hover:text-destructive transition-colors p-0.5 rounded hover:bg-muted"
                          title="Delete segment"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>

                    <textarea
                      value={para}
                      onChange={(e) => updateParagraph(index, e.target.value)}
                      rows={3}
                      className="w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm text-foreground font-sans leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring resize-none"
                      placeholder="Enter script narration..."
                    />

                    {/* Add Segment Divider */}
                    <div className="relative flex justify-center py-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <div className="absolute inset-0 flex items-center" aria-hidden="true">
                        <div className="w-full border-t border-dashed border-border/40" />
                      </div>
                      <button
                        type="button"
                        onClick={() => addParagraph(index)}
                        className="relative inline-flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full bg-background border border-border text-muted-foreground hover:text-primary hover:border-primary/50 transition-colors shadow-sm"
                      >
                        <Plus size={10} />
                        Insert Segment
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border/60 flex items-center gap-3 bg-background">
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending || paragraphs.length === 0}
            className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 shadow-sm"
          >
            <Mic size={14} />
            {approve.isPending ? "Sending…" : "Approve & Generate Audio"}
          </button>
          <button
            onClick={handleClose}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
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
