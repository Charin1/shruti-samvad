"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { Mic, X, Sparkles, Volume2, VolumeX } from "lucide-react";
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
  const [podcastFormat, setPodcastFormat] = useState("monologue");
  const [voice, setVoice] = useState("af_heart");
  const [voiceCohost, setVoiceCohost] = useState("af_sky");
  const [podcastStyle, setPodcastStyle] = useState("conversational");
  const [customPrompt, setCustomPrompt] = useState("");
  const [bgMusic, setBgMusic] = useState(false);
  
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);
  const [audioPreview, setAudioPreview] = useState<HTMLAudioElement | null>(null);
  
  const [isPlayingPreviewCohost, setIsPlayingPreviewCohost] = useState(false);
  const [audioPreviewCohost, setAudioPreviewCohost] = useState<HTMLAudioElement | null>(null);

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

  // Voice preview cleanup on unmount or voice change
  useEffect(() => {
    return () => {
      if (audioPreview) audioPreview.pause();
      if (audioPreviewCohost) audioPreviewCohost.pause();
    };
  }, [audioPreview, audioPreviewCohost]);

  useEffect(() => {
    if (audioPreview) {
      audioPreview.pause();
      setIsPlayingPreview(false);
      setAudioPreview(null);
    }
  }, [voice]);

  useEffect(() => {
    if (audioPreviewCohost) {
      audioPreviewCohost.pause();
      setIsPlayingPreviewCohost(false);
      setAudioPreviewCohost(null);
    }
  }, [voiceCohost]);

  const togglePlayPreview = () => {
    if (isPlayingPreview) {
      if (audioPreview) {
        audioPreview.pause();
        audioPreview.currentTime = 0;
      }
      setIsPlayingPreview(false);
    } else {
      if (audioPreviewCohost) {
        audioPreviewCohost.pause();
        setIsPlayingPreviewCohost(false);
      }
      const url = `http://localhost:8001/voices/${voice}/preview`;
      const audio = new Audio(url);
      audio.onended = () => {
        setIsPlayingPreview(false);
      };
      audio.onerror = () => {
        setIsPlayingPreview(false);
        alert("Failed to play voice preview. Make sure the podcast API is running.");
      };
      setAudioPreview(audio);
      setIsPlayingPreview(true);
      audio.play().catch((err) => {
        console.error(err);
        setIsPlayingPreview(false);
      });
    }
  };

  const togglePlayPreviewCohost = () => {
    if (isPlayingPreviewCohost) {
      if (audioPreviewCohost) {
        audioPreviewCohost.pause();
        audioPreviewCohost.currentTime = 0;
      }
      setIsPlayingPreviewCohost(false);
    } else {
      if (audioPreview) {
        audioPreview.pause();
        setIsPlayingPreview(false);
      }
      const url = `http://localhost:8001/voices/${voiceCohost}/preview`;
      const audio = new Audio(url);
      audio.onended = () => {
        setIsPlayingPreviewCohost(false);
      };
      audio.onerror = () => {
        setIsPlayingPreviewCohost(false);
        alert("Failed to play voice preview. Make sure the podcast API is running.");
      };
      setAudioPreviewCohost(audio);
      setIsPlayingPreviewCohost(true);
      audio.play().catch((err) => {
        console.error(err);
        setIsPlayingPreviewCohost(false);
      });
    }
  };

  const create = useMutation({
    mutationFn: () =>
      createEpisode({
        article_ids: Array.from(selectedArticleIds),
        title: title.trim() || undefined,
        target_minutes: targetMinutes,
        review_requested: reviewRequested,
        voice,
        voice_cohost: voiceCohost,
        podcast_format: podcastFormat,
        podcast_style: podcastStyle,
        custom_prompt: customPrompt.trim() || undefined,
        bg_music: bgMusic,
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

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Podcast Format</span>
            <div className="flex gap-1 p-0.5 bg-sidebar rounded-md border border-border/60 h-8">
              <button
                type="button"
                onClick={() => setPodcastFormat("monologue")}
                className={`flex-1 py-0.5 rounded text-center text-[11px] transition-all ${
                  podcastFormat === "monologue"
                    ? "bg-background text-foreground font-semibold shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Monologue
              </button>
              <button
                type="button"
                onClick={() => setPodcastFormat("dialogue")}
                className={`flex-1 py-0.5 rounded text-center text-[11px] transition-all ${
                  podcastFormat === "dialogue"
                    ? "bg-background text-foreground font-semibold shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Co-Hosted
              </button>
            </div>
          </div>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Duration</span>
            <div className="flex items-center gap-1.5 h-8">
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
              {!isAutoDetected && (
                <button
                  type="button"
                  onClick={() => setIsAutoDetected(true)}
                  className="inline-flex items-center gap-1 text-[10px] px-1.5 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors border border-primary/20 shrink-0"
                  title="Auto-detect duration based on article content"
                >
                  <Sparkles size={9} />
                  Auto
                </button>
              )}
            </div>
          </label>
        </div>

        {podcastFormat === "monologue" ? (
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Voice</span>
            <div className="flex gap-1.5 items-center h-8">
              <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="flex-1 min-w-0 rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                {voices.map((v: string) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={togglePlayPreview}
                title={isPlayingPreview ? "Stop preview" : "Play voice preview"}
                className={`p-1.5 rounded-md border transition-colors shrink-0 ${
                  isPlayingPreview
                    ? "border-primary bg-primary/5 text-primary hover:bg-primary/10"
                    : "border-border/60 bg-background hover:bg-background/80 text-muted-foreground hover:text-foreground"
                }`}
              >
                {isPlayingPreview ? <VolumeX size={14} /> : <Volume2 size={14} />}
              </button>
            </div>
          </label>
        ) : (
          <div className="grid grid-cols-2 gap-3 border-l border-primary/20 pl-2">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span>Host Voice (Aarav)</span>
              <div className="flex gap-1.5 items-center h-8">
                <select
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                  className="flex-1 min-w-0 rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {voices.map((v: string) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={togglePlayPreview}
                  title={isPlayingPreview ? "Stop preview" : "Play voice preview"}
                  className={`p-1.5 rounded-md border transition-colors shrink-0 ${
                    isPlayingPreview
                      ? "border-primary bg-primary/5 text-primary hover:bg-primary/10"
                      : "border-border/60 bg-background hover:bg-background/80 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {isPlayingPreview ? <VolumeX size={14} /> : <Volume2 size={14} />}
                </button>
              </div>
            </label>

            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span>Co-Host Voice (Ananya)</span>
              <div className="flex gap-1.5 items-center h-8">
                <select
                  value={voiceCohost}
                  onChange={(e) => setVoiceCohost(e.target.value)}
                  className="flex-1 min-w-0 rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  {voices.map((v: string) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={togglePlayPreviewCohost}
                  title={isPlayingPreviewCohost ? "Stop preview" : "Play voice preview"}
                  className={`p-1.5 rounded-md border transition-colors shrink-0 ${
                    isPlayingPreviewCohost
                      ? "border-primary bg-primary/5 text-primary hover:bg-primary/10"
                      : "border-border/60 bg-background hover:bg-background/80 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {isPlayingPreviewCohost ? <VolumeX size={14} /> : <Volume2 size={14} />}
                </button>
              </div>
            </label>
          </div>
        )}

        <div className="flex flex-col gap-2.5">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Style & Tone</span>
            <select
              value={podcastStyle}
              onChange={(e) => setPodcastStyle(e.target.value)}
              className="w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="conversational">Conversational (Warm & Storytelling)</option>
              <option value="briefing">News Briefing (Concise & Professional)</option>
              <option value="analytical">Analytical (Deep-Dive & Explanatory)</option>
              <option value="dramatic">Dramatic (Suspenseful & High-Energy)</option>
              <option value="humorous">Humorous (Witty & Lighthearted)</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            <span>Custom Instructions / Prompt (Optional)</span>
            <textarea
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              placeholder="e.g. Focus on technology impacts, skip financial tables, explain terms simply..."
              rows={2}
              className="w-full rounded-md border border-border/60 bg-background px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring resize-none font-sans"
            />
          </label>
        </div>

        <div className="flex items-center gap-4 py-0.5 select-none">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={reviewRequested}
              onChange={(e) => setReviewRequested(e.target.checked)}
              className="accent-primary"
            />
            <span>Awaiting Review</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
            <input
              type="checkbox"
              checked={bgMusic}
              onChange={(e) => setBgMusic(e.target.checked)}
              className="accent-primary"
            />
            <span>Background Music</span>
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
