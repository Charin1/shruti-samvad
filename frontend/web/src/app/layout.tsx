import type { Metadata } from "next";
import { Newsreader, Work_Sans } from "next/font/google";
import "./globals.css";
import { Providers } from "@/lib/providers";
import { Sidebar } from "@/components/Sidebar";
import { ScriptReviewPanel } from "@/components/ScriptReviewPanel";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
});

const workSans = Work_Sans({
  subsets: ["latin"],
  variable: "--font-work-sans",
});

export const metadata: Metadata = {
  title: "Shruti Samvad",
  description: "Agentic RSS Reader + AI Podcast Generator",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${newsreader.variable} ${workSans.variable} font-sans h-screen overflow-hidden flex flex-col`}
      >
        <Providers>
          <div className="flex flex-1 h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-hidden flex">{children}</main>
          </div>
          <ScriptReviewPanel />
        </Providers>
      </body>
    </html>
  );
}
