"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { Mic, Plus, Trash2, Sparkles, Volume2, VolumeX, FileText } from "lucide-react";
import { createEpisode, type CustomArticle } from "@/lib/api";
import { useReaderStore } from "@/lib/store";
import { estimateTargetMinutes, countWords } from "@/lib/estimator";

export function CustomPodcastGenerator() {
  const qc = useQueryClient();
  const setView = useReaderStore((s) => s.setView);

  // Custom articles state
  const [articles, setArticles] = useState<CustomArticle[]>([
    { title: "", content: "" },
  ]);

  // Podcast settings state
  const [title, setTitle] = useState("");
  const [targetMinutes, setTargetMinutes] = useState(3);
  const [reviewRequested, setReviewRequested] = useState(false);
  const [isAutoDetected, setIsAutoDetected] = useState(true);
  const [voice, setVoice] = useState("af_heart");
  const [podcastStyle, setPodcastStyle] = useState("conversational");
  const [customPrompt, setCustomPrompt] = useState("");
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);
  const [audioPreview, setAudioPreview] = useState<HTMLAudioElement | null>(null);

  // Fetch available voices
  const { data: voices = [] } = useQuery({
    queryKey: ["voices"],
    queryFn: async () => {
      const res = await fetch("http://localhost:8001/voices");
      if (!res.ok) return ["af_heart", "af_sky", "af_bella"];
      const data = await res.json();
      return data.voices || [];
    },
  });

  // Calculate word count and estimated minutes
  const totalWords = articles.reduce(
    (sum, a) => sum + countWords(a.content),
    0
  );
  const estimatedMinutes = estimateTargetMinutes(articles.length, totalWords);

  // Auto-detect target duration
  useEffect(() => {
    if (!isAutoDetected) return;
    setTargetMinutes(estimatedMinutes);
  }, [articles, isAutoDetected, estimatedMinutes]);

  // Cleanup audio preview
  useEffect(() => {
    return () => {
      if (audioPreview) {
        audioPreview.pause();
      }
    };
  }, [audioPreview]);

  useEffect(() => {
    if (audioPreview) {
      audioPreview.pause();
      setIsPlayingPreview(false);
      setAudioPreview(null);
    }
  }, [voice]);

  const togglePlayPreview = () => {
    if (isPlayingPreview) {
      if (audioPreview) {
        audioPreview.pause();
        audioPreview.currentTime = 0;
      }
      setIsPlayingPreview(false);
    } else {
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

  const addArticleBlock = () => {
    setArticles([...articles, { title: "", content: "" }]);
  };

  const removeArticleBlock = (index: number) => {
    if (articles.length === 1) {
      setArticles([{ title: "", content: "" }]);
      return;
    }
    setArticles(articles.filter((_, i) => i !== index));
  };

  const updateArticle = (
    index: number,
    field: keyof CustomArticle,
    value: string
  ) => {
    const next = [...articles];
    next[index][field] = value;
    setArticles(next);
  };

  const generate = useMutation({
    mutationFn: () => {
      const validArticles = articles.filter((a) => a.content.trim() !== "");
      if (validArticles.length === 0) {
        throw new Error("Please fill in the content for at least one article block.");
      }
      return createEpisode({
        custom_articles: validArticles,
        title: title.trim() || undefined,
        target_minutes: targetMinutes,
        review_requested: reviewRequested,
        voice,
        podcast_style: podcastStyle,
        custom_prompt: customPrompt.trim() || undefined,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["episodes"] });
      setView("library");
    },
  });

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-background">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-primary" />
          <h2 className="font-newsreader text-lg font-semibold text-foreground">
            Custom Podcast Creator
          </h2>
        </div>
        <div className="text-xs text-muted-foreground">
          {articles.length} block(s) · {totalWords} words
        </div>
      </div>

      {/* Editor Panes */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: Pasted Blocks Editor */}
        <div className="flex-1 overflow-y-auto px-6 py-5 border-r border-border/40 space-y-4">
          {articles.map((article, index) => (
            <div
              key={index}
              className="p-4 rounded-lg border border-border bg-sidebar/40 shadow-sm relative group"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-muted-foreground uppercase">
                  Article Block #{index + 1}
                </span>
                <button
                  onClick={() => removeArticleBlock(index)}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                  title="Remove block"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              <div className="space-y-3">
                <input
                  type="text"
                  value={article.title}
                  onChange={(e) => updateArticle(index, "title", e.target.value)}
                  placeholder="Article/Blog Title (optional)"
                  className="w-full text-sm px-3 py-1.5 rounded-md border border-border bg-background text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <textarea
                  value={article.content}
                  onChange={(e) => updateArticle(index, "content", e.target.value)}
                  placeholder="Paste clean blog text, notes, or article contents here..."
                  rows={6}
                  className="w-full text-sm px-3 py-2 rounded-md border border-border bg-background text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring font-sans"
                />
              </div>
            </div>
          ))}

          <button
            onClick={addArticleBlock}
            className="w-full py-2.5 border border-dashed border-border/60 hover:border-primary/50 hover:bg-primary/5 rounded-lg flex items-center justify-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-primary transition-all"
          >
            <Plus size={16} />
            Add Content Block
          </button>
        </div>

        {/* Right Pane: Options & Generation Panel */}
        <div className="w-80 shrink-0 overflow-y-auto bg-sidebar/30 px-5 py-5 flex flex-col gap-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Podcast Settings
          </h3>

          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span>Episode Title</span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Custom Episode Title"
                className="w-full rounded-md border border-border/60 bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </label>

            {/* Duration and Voice */}
            <div className="grid grid-cols-5 gap-2 items-end">
              <label className="flex flex-col gap-1 text-xs text-muted-foreground col-span-2">
                <span>Duration</span>
                <div className="flex items-center gap-1 h-8">
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={targetMinutes}
                    onChange={(e) => {
                      setTargetMinutes(Number(e.target.value) || 1);
                      setIsAutoDetected(false);
                    }}
                    className="w-10 rounded-md border border-border/60 bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                  <span className="text-xs">min</span>
                  {!isAutoDetected && (
                    <button
                      type="button"
                      onClick={() => setIsAutoDetected(true)}
                      className="inline-flex items-center gap-0.5 text-[9px] p-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors border border-primary/20 shrink-0"
                      title="Reset to estimated duration based on text length"
                    >
                      <Sparkles size={8} />
                    </button>
                  )}
                </div>
              </label>

              <label className="flex flex-col gap-1 text-xs text-muted-foreground col-span-3">
                <span>Voice</span>
                <div className="flex gap-1 items-center h-8">
                  <select
                    value={voice}
                    onChange={(e) => setVoice(e.target.value)}
                    className="flex-1 min-w-0 rounded-md border border-border/60 bg-background px-1.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    {voices.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={togglePlayPreview}
                    title={isPlayingPreview ? "Stop preview" : "Play preview"}
                    className={`p-1.5 rounded-md border transition-colors shrink-0 ${
                      isPlayingPreview
                        ? "border-primary bg-primary/5 text-primary hover:bg-primary/10"
                        : "border-border/60 bg-background hover:bg-background/80 text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {isPlayingPreview ? <VolumeX size={13} /> : <Volume2 size={13} />}
                  </button>
                </div>
              </label>
            </div>

            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              <span>Style & Tone</span>
              <select
                value={podcastStyle}
                onChange={(e) => setPodcastStyle(e.target.value)}
                className="w-full rounded-md border border-border/60 bg-background px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
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
                placeholder="e.g. Focus on technology impacts, explain terms simply..."
                rows={3}
                className="w-full rounded-md border border-border/60 bg-background px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring resize-none font-sans"
              />
            </label>

            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none py-1">
              <input
                type="checkbox"
                checked={reviewRequested}
                onChange={(e) => setReviewRequested(e.target.checked)}
                className="accent-primary"
              />
              <span>Awaiting Review before synthesis</span>
            </label>
          </div>

          <button
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="w-full mt-2 inline-flex items-center justify-center gap-2 bg-primary text-primary-foreground px-4 py-2.5 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 shadow-sm"
          >
            <Mic size={14} />
            {generate.isPending ? "Queuing…" : "Generate Podcast"}
          </button>

          {generate.isError && (
            <span className="text-xs text-destructive text-center">
              {(generate.error as Error).message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
