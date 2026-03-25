"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import {
  GitBranch,
  Layers,
  FileText,
  ChevronRight,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { WikiTreeView } from "@/components/WikiTreeView";
import { Ask } from "@/components/Ask";
import { Markdown } from "@/components/Markdown";
import { fetchStream } from "@/hooks/useStreamingContent";

interface WikiPage {
  title: string;
  description: string;
  sections: string[];
  file_paths: string[];
}

interface WikiData {
  wiki_structure: { pages: WikiPage[] };
  pages: Record<string, string>;
  updated_at: string;
}

type Status = "loading" | "empty" | "generating" | "ready" | "error";

export default function WikiViewer({
  params,
}: {
  params: Promise<{ owner: string; repo: string }>;
}) {
  const { owner, repo } = use(params);
  const router = useRouter();

  const [status, setStatus] = useState<Status>("loading");
  const [wikiData, setWikiData] = useState<WikiData | null>(null);
  const [activePage, setActivePage] = useState<string>("");
  const [generatingPage, setGeneratingPage] = useState<string>("");
  const [generationProgress, setGenerationProgress] = useState(0);
  const [streamingContent, setStreamingContent] = useState<Record<string, string>>({});
  const [totalPages, setTotalPages] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const repoUrl = `https://github.com/${owner}/${repo}`;

  useEffect(() => {
    loadWiki();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner, repo]);

  async function loadWiki() {
    setStatus("loading");
    const stored = JSON.parse(localStorage.getItem("wikiGenConfig") || "{}");
    const language: string = stored.language ?? "English";
    try {
      const res = await fetch(
        `/wiki/cache?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&language=${encodeURIComponent(language)}`
      );
      if (res.ok) {
        const data = await res.json();
        setWikiData(data);
        const firstPage = data.wiki_structure?.pages?.[0]?.title ?? "";
        setActivePage(firstPage);
        setStatus("ready");
      } else if (res.status === 404) {
        setStatus("empty");
      } else {
        setErrorMsg("Failed to load wiki");
        setStatus("error");
      }
    } catch {
      setStatus("empty");
    }
  }

  async function generateWiki() {
    setStatus("generating");
    setStreamingContent({});
    setGenerationProgress(0);

    const stored = JSON.parse(localStorage.getItem("wikiGenConfig") || "{}");
    const provider: string = stored.provider ?? "google";
    const model: string | undefined = stored.model ?? undefined;
    const language: string = stored.language ?? "English";

    try {
      // Step 1: get structure
      const structRes = await fetch("/wiki/structure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, language, provider, model }),
      });
      if (!structRes.ok) {
        let detail = "Failed to get wiki structure";
        try { const err = await structRes.json(); detail = err.detail || detail; } catch {}
        throw new Error(detail);
      }
      const { wiki_structure } = await structRes.json();
      const pages: WikiPage[] = wiki_structure.pages;
      setTotalPages(pages.length);

      // Step 2: generate each page
      const generatedPages: Record<string, string> = {};
      for (let i = 0; i < pages.length; i++) {
        const page = pages[i];
        setGeneratingPage(page.title);
        setGenerationProgress(Math.round((i / pages.length) * 100));

        const content = await fetchStream(
          "/wiki/generate-page",
          {
            repo_url: repoUrl,
            page_title: page.title,
            file_paths: page.file_paths,
            language,
            provider,
            model,
          },
          (accumulated) => {
            setStreamingContent((prev) => ({
              ...prev,
              [page.title]: accumulated,
            }));
          }
        );
        generatedPages[page.title] = content;
      }

      // Step 3: save to cache
      await fetch("/wiki/cache", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner,
          repo,
          language,
          wiki_structure,
          pages: generatedPages,
        }),
      });

      const firstPage = pages[0]?.title ?? "";
      setWikiData({
        wiki_structure,
        pages: generatedPages,
        updated_at: new Date().toISOString(),
      });
      setActivePage(firstPage);
      setStreamingContent({});
      setStatus("ready");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Generation failed");
      setStatus("error");
    }
  }

  async function regenerateWiki() {
    const stored = JSON.parse(localStorage.getItem("wikiGenConfig") || "{}");
    const language: string = stored.language ?? "English";
    await fetch(
      `/wiki/cache?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&language=${encodeURIComponent(language)}`,
      { method: "DELETE" }
    );
    generateWiki();
  }

  function handleAsk(question: string, mode: "fast" | "deep") {
    const params = new URLSearchParams({ q: question, mode });
    router.push(`/${owner}/${repo}/chat?${params.toString()}`);
  }

  const activePageData = wikiData?.wiki_structure?.pages?.find(
    (p) => p.title === activePage
  );
  const activeContent = wikiData?.pages?.[activePage] ?? "";

  if (status === "loading") {
    return (
      <div className="min-h-screen flex flex-col" style={{ backgroundColor: "#FAF7F2" }}>
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <Loader2 size={32} strokeWidth={1.5} className="animate-spin" style={{ color: "#C4714A" }} />
            <p style={{ color: "#9A8A7A", fontSize: "14px" }}>Loading wiki…</p>
          </div>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen flex flex-col" style={{ backgroundColor: "#FAF7F2" }}>
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4 text-center">
            <p style={{ color: "#C4714A", fontSize: "15px", fontWeight: 500 }}>
              {errorMsg}
            </p>
            <button
              onClick={generateWiki}
              className="px-4 py-2 rounded-xl text-white text-sm"
              style={{ backgroundColor: "#C4714A" }}
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="min-h-screen flex flex-col" style={{ backgroundColor: "#FAF7F2" }}>
        <Navbar />
        <div className="flex-1 flex items-center justify-center px-6">
          <div
            className="max-w-md w-full rounded-2xl p-10 flex flex-col items-center text-center"
            style={{
              backgroundColor: "#FFFDF9",
              border: "1px solid #EDE5D8",
              boxShadow: "0 4px 24px rgba(60, 40, 20, 0.07)",
            }}
          >
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5"
              style={{ backgroundColor: "#F0E8DE" }}
            >
              <GitBranch size={24} strokeWidth={1.5} style={{ color: "#C4714A" }} />
            </div>
            <h2 style={{ color: "#2C2420", fontSize: "18px", fontWeight: 600, marginBottom: "8px" }}>
              {owner}/{repo}
            </h2>
            <p style={{ color: "#9A8A7A", fontSize: "14px", lineHeight: 1.6, marginBottom: "24px" }}>
              No wiki found for this repository. Generate one to explore the codebase.
            </p>
            <button
              onClick={generateWiki}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-white transition-all"
              style={{
                backgroundColor: "#C4714A",
                fontSize: "14px",
                fontWeight: 500,
                boxShadow: "0 2px 8px rgba(196, 113, 74, 0.3)",
              }}
            >
              Generate Wiki
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (status === "generating") {
    const doneCount = Object.keys(streamingContent).filter(
      (k) => streamingContent[k]
    ).length;
    const total = totalPages || 1;

    return (
      <div className="min-h-screen flex flex-col" style={{ backgroundColor: "#FAF7F2" }}>
        <Navbar />
        <div className="flex-1 flex items-center justify-center px-6">
          <div
            className="max-w-lg w-full rounded-2xl p-10"
            style={{
              backgroundColor: "#FFFDF9",
              border: "1px solid #EDE5D8",
              boxShadow: "0 4px 24px rgba(60, 40, 20, 0.07)",
            }}
          >
            <div className="flex items-center gap-3 mb-6">
              <Loader2
                size={20}
                strokeWidth={1.8}
                className="animate-spin"
                style={{ color: "#C4714A" }}
              />
              <h2 style={{ color: "#2C2420", fontSize: "16px", fontWeight: 600 }}>
                Generating wiki for {owner}/{repo}
              </h2>
            </div>

            {/* Progress bar */}
            <div
              className="h-1.5 rounded-full mb-4"
              style={{ backgroundColor: "#EDE5D8" }}
            >
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  backgroundColor: "#C4714A",
                  width: `${Math.min(100, total > 0 ? Math.round((doneCount / total) * 100) : generationProgress)}%`,
                }}
              />
            </div>

            <p style={{ color: "#9A8A7A", fontSize: "13px", marginBottom: "16px" }}>
              {generatingPage ? `Generating: ${generatingPage} (${doneCount}/${total} pages)` : "Analyzing repository…"}
            </p>

            {/* Live preview of current page */}
            {generatingPage && streamingContent[generatingPage] && (
              <div
                className="rounded-xl p-4 max-h-48 overflow-y-auto"
                style={{
                  backgroundColor: "#F5F0E8",
                  border: "1px solid #E8E0D5",
                }}
              >
                <p
                  style={{
                    color: "#7A6A5A",
                    fontSize: "12px",
                    fontFamily: "var(--font-geist-mono), monospace",
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.6,
                  }}
                >
                  {streamingContent[generatingPage].slice(0, 600)}
                  {streamingContent[generatingPage].length > 600 && "…"}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Ready state
  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: "#FAF7F2" }}>
      <Navbar />

      <div className="flex flex-1 max-w-7xl mx-auto w-full px-4">
        {/* Sidebar */}
        <aside
          className="w-64 shrink-0 py-6 pr-4 sticky self-start overflow-y-auto"
          style={{ height: "calc(100vh - 3.5rem)", top: "3.5rem" }}
        >
          {/* Repo info */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-1">
              <span style={{ color: "#9A8A7A", fontSize: "12px" }}>{owner}</span>
            </div>
            <h2
              style={{
                color: "#2C2420",
                fontSize: "15px",
                fontWeight: 600,
              }}
            >
              {repo}
            </h2>
            <div
              className="flex items-center gap-1 mt-1.5"
              style={{ color: "#B0A090", fontSize: "11px" }}
            >
              <GitBranch size={10} strokeWidth={1.8} />
              <span>main</span>
            </div>
          </div>

          <div className="mb-4 h-px" style={{ backgroundColor: "#E8E0D5" }} />

          <WikiTreeView
            pages={wikiData?.wiki_structure?.pages ?? []}
            activePage={activePage}
            onSelect={setActivePage}
            pageContents={wikiData?.pages}
            onScrollToHeading={(heading) => {
              // Find the heading element in the main content and scroll to it
              const mainEl = document.querySelector("main");
              if (!mainEl) return;
              const headings = mainEl.querySelectorAll("h2");
              for (const el of headings) {
                if (el.textContent?.trim() === heading) {
                  el.scrollIntoView({ behavior: "smooth", block: "start" });
                  break;
                }
              }
            }}
          />

          <div className="mt-4 pt-4" style={{ borderTop: "1px solid #EDE5D8" }}>
            <button
              onClick={regenerateWiki}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg transition-all"
              style={{
                color: "#9A8A7A",
                fontSize: "12px",
              }}
              onMouseEnter={(e) =>
                ((e.currentTarget as HTMLElement).style.backgroundColor = "#F0E8DE")
              }
              onMouseLeave={(e) =>
                ((e.currentTarget as HTMLElement).style.backgroundColor = "transparent")
              }
            >
              <RefreshCw size={12} strokeWidth={1.8} />
              Regenerate Wiki
            </button>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0 pb-28">
          <main className="flex-1 py-8 px-8">
            {/* Breadcrumb */}
            <nav className="flex items-center gap-1.5 mb-8">
              {[`${owner}/${repo}`, activePage].map((crumb, i) => (
                <span key={crumb} className="flex items-center gap-1.5">
                  {i > 0 && (
                    <ChevronRight
                      size={12}
                      strokeWidth={1.8}
                      style={{ color: "#C4B8AB" }}
                    />
                  )}
                  <span
                    style={{
                      fontSize: "13px",
                      color: i === 1 ? "#3A3228" : "#9A8A7A",
                      fontWeight: i === 1 ? 500 : 400,
                    }}
                  >
                    {crumb}
                  </span>
                </span>
              ))}
            </nav>

            {/* Article title */}
            <h1
              className="mb-8"
              style={{
                fontSize: "32px",
                fontWeight: 600,
                color: "#2C2420",
                lineHeight: 1.25,
                letterSpacing: "-0.02em",
              }}
            >
              {activePage}
            </h1>

            {/* Content */}
            <Markdown content={activeContent} />

            {/* Source files */}
            {activePageData && activePageData.file_paths.length > 0 && (
              <div
                className="mt-12 rounded-xl p-5"
                style={{
                  backgroundColor: "#F5F0E8",
                  border: "1px solid #E8E0D5",
                }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Layers
                    size={14}
                    strokeWidth={1.7}
                    style={{ color: "#8B9E7A" }}
                  />
                  <h3
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#5A4E44",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    Source Files
                  </h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  {activePageData.file_paths.map((file) => (
                    <span
                      key={file}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
                      style={{
                        backgroundColor: "#E8E0D5",
                        color: "#7A6A5A",
                        fontSize: "12px",
                        fontFamily: "var(--font-geist-mono), monospace",
                      }}
                    >
                      <FileText size={11} strokeWidth={1.8} style={{ flexShrink: 0 }} />
                      {file}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </main>
        </div>
      </div>

      <Ask onAsk={handleAsk} />
    </div>
  );
}
