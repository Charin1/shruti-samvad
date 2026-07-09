"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { getArticle } from "@/lib/api";
import { useReaderStore } from "@/lib/store";
import { GeneratePodcastButton } from "./GeneratePodcastButton";

export function ArticleReader() {
  const { selectedArticleId } = useReaderStore();

  const { data: article, isLoading } = useQuery({
    queryKey: ["article", selectedArticleId],
    queryFn: () => getArticle(selectedArticleId as string),
    enabled: !!selectedArticleId,
  });

  if (!selectedArticleId) {
    return (
      <div className="flex-1 h-full flex items-center justify-center text-muted-foreground">
        <p className="font-newsreader text-lg">
          Select an article to start reading.
        </p>
      </div>
    );
  }

  if (isLoading || !article) {
    return (
      <div className="flex-1 h-full flex items-center justify-center text-muted-foreground">
        Loading…
      </div>
    );
  }

  const body = article.clean_text
    ? `<p>${article.clean_text.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br/>")}</p>`
    : article.raw_html ?? "<p>No content extracted yet.</p>";

  return (
    <div className="flex-1 h-full flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto min-h-0">
        <article className="max-w-2xl mx-auto px-8 py-10">
          <h1 className="font-newsreader text-3xl leading-tight text-foreground">
            {article.title}
          </h1>
          <div className="flex items-center gap-3 mt-3 text-sm text-muted-foreground">
            <time>{new Date(article.published_at).toLocaleString()}</time>
            <a
              href={article.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 hover:text-primary"
            >
              Original <ExternalLink size={13} />
            </a>
          </div>

          <div className="my-6">
            <GeneratePodcastButton articleId={article.id} />
          </div>

          <div
            className="prose-reader font-newsreader text-[17px] leading-[1.7] text-foreground/90 space-y-4"
            dangerouslySetInnerHTML={{ __html: body }}
          />
        </article>
      </div>
    </div>
  );
}
