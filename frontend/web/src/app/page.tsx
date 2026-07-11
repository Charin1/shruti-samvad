"use client";

import { ArticleList } from "@/components/ArticleList";
import { ArticleReader } from "@/components/ArticleReader";
import { PodcastLibrary } from "@/components/PodcastLibrary";
import { CustomPodcastGenerator } from "@/components/CustomPodcastGenerator";
import { useReaderStore } from "@/lib/store";

export default function Home() {
  const { view } = useReaderStore();

  if (view === "library") {
    return <PodcastLibrary />;
  }

  if (view === "custom") {
    return <CustomPodcastGenerator />;
  }

  return (
    <div className="flex flex-1 h-full overflow-hidden w-full">
      <ArticleList />
      <ArticleReader />
    </div>
  );
}
