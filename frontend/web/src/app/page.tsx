"use client";

import { ArticleList } from "@/components/ArticleList";
import { ArticleReader } from "@/components/ArticleReader";
import { PodcastLibrary } from "@/components/PodcastLibrary";
import { useReaderStore } from "@/lib/store";

export default function Home() {
  const { view } = useReaderStore();

  if (view === "library") {
    return <PodcastLibrary />;
  }

  return (
    <div className="flex flex-1 h-full overflow-hidden w-full">
      <ArticleList />
      <ArticleReader />
    </div>
  );
}
