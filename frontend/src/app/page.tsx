"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, BookOpen, Clock, GitBranch, Sparkles, FileText } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { ConfigCard, WikiConfig } from "@/components/ConfigCard";

interface Project {
  owner: string;
  repo: string;
  language: string;
  page_count: number;
  created_at: string;
  updated_at: string;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function parseRepoUrl(input: string): { owner: string; repo: string } | null {
  const trimmed = input.trim().replace(/\/$/, "");
  const githubMatch = trimmed.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (githubMatch) return { owner: githubMatch[1], repo: githubMatch[2] };
  const slashMatch = trimmed.match(/^([^/]+)\/([^/]+)$/);
  if (slashMatch) return { owner: slashMatch[1], repo: slashMatch[2] };
  return null;
}

export default function Home() {
  const [inputValue, setInputValue] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");
  const [showConfig, setShowConfig] = useState(false);
  const router = useRouter();

  useEffect(() => {
    fetch("/api/processed_projects")
      .then((r) => r.json())
      .then((data) => setProjects(data.projects || []))
      .catch(() => {});
  }, []);

  const openConfig = () => setShowConfig(true);

  const handleConfigGenerate = (config: WikiConfig) => {
    const parsed = parseRepoUrl(config.url);
    if (!parsed) {
      setError("Enter a valid GitHub URL or owner/repo");
      setShowConfig(false);
      return;
    }
    setError("");
    setShowConfig(false);
    sessionStorage.setItem(
      "wikiGenConfig",
      JSON.stringify({ provider: config.provider, model: config.model, language: config.language })
    );
    router.push(`/${parsed.owner}/${parsed.repo}`);
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#FAF7F2" }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-24 pb-16 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <div
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full mb-8"
            style={{
              backgroundColor: "#F0E8DE",
              color: "#C4714A",
              fontSize: "12px",
              fontWeight: 500,
            }}
          >
            <Sparkles size={11} strokeWidth={1.8} />
            AI-powered wiki generation
          </div>

          <h1
            className="mb-4"
            style={{
              fontSize: "42px",
              fontWeight: 600,
              color: "#2C2420",
              lineHeight: 1.2,
              letterSpacing: "-0.02em",
            }}
          >
            Turn any GitHub repo into
            <br />
            <span style={{ color: "#C4714A" }}>living documentation</span>
          </h1>

          <p
            className="mb-10"
            style={{ color: "#9A8A7A", fontSize: "17px", lineHeight: 1.6 }}
          >
            Paste a repository URL and get a structured, searchable wiki
            <br />
            with built-in Q&amp;A — ready in seconds.
          </p>

          <div
            className="flex items-center gap-0 p-2 rounded-2xl mb-3"
            style={{
              backgroundColor: "#FFFDF9",
              boxShadow:
                "0 2px 6px rgba(60, 40, 20, 0.06), 0 8px 24px rgba(60, 40, 20, 0.08)",
              border: `1px solid ${error ? "#C4714A" : "#EDE5D8"}`,
            }}
          >
            <div className="flex items-center gap-3 flex-1 px-4">
              <GitBranch
                size={17}
                strokeWidth={1.6}
                style={{ color: "#B0A090", flexShrink: 0 }}
              />
              <input
                type="text"
                value={inputValue}
                onChange={(e) => { setInputValue(e.target.value); setError(""); }}
                onKeyDown={(e) => { if (e.key === "Enter") openConfig(); }}
                placeholder="https://github.com/owner/repo"
                className="flex-1 bg-transparent outline-none"
                style={{ color: "#3A3228", fontSize: "15px", caretColor: "#C4714A" }}
              />
            </div>
            <button
              onClick={openConfig}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl transition-all"
              style={{
                backgroundColor: "#C4714A",
                color: "white",
                fontSize: "14px",
                fontWeight: 500,
                boxShadow: "0 2px 8px rgba(196, 113, 74, 0.3)",
              }}
              onMouseEnter={(e) =>
                ((e.currentTarget as HTMLElement).style.backgroundColor = "#B3623C")
              }
              onMouseLeave={(e) =>
                ((e.currentTarget as HTMLElement).style.backgroundColor = "#C4714A")
              }
            >
              Generate Wiki
              <ArrowRight size={14} strokeWidth={2} />
            </button>
          </div>

          {error ? (
            <p style={{ color: "#C4714A", fontSize: "13px" }}>{error}</p>
          ) : (
            <p style={{ color: "#B0A090", fontSize: "13px" }}>
              Public repositories only · No account required
            </p>
          )}

        </div>
      </section>

      {showConfig && (
        <ConfigCard
          initialUrl={inputValue}
          onClose={() => setShowConfig(false)}
          onGenerate={handleConfigGenerate}
        />
      )}

      {/* Recent Wikis */}
      <section className="px-6 pb-24">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h2
              style={{ color: "#3A3228", fontSize: "16px", fontWeight: 600 }}
            >
              Recent Wikis
            </h2>
            <span style={{ color: "#B0A090", fontSize: "13px" }}>
              {projects.length} wiki{projects.length !== 1 ? "s" : ""}
            </span>
          </div>

          {projects.length === 0 ? (
            <div
              className="rounded-2xl p-16 flex flex-col items-center text-center"
              style={{
                backgroundColor: "#F5F0E8",
                border: "1.5px dashed #D8CEC0",
              }}
            >
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
                style={{ backgroundColor: "#EDE5D8" }}
              >
                <BookOpen size={24} strokeWidth={1.4} style={{ color: "#B0A090" }} />
              </div>
              <p
                style={{
                  color: "#7A6A5A",
                  fontSize: "15px",
                  fontWeight: 500,
                  marginBottom: "6px",
                }}
              >
                No wikis yet
              </p>
              <p style={{ color: "#B0A090", fontSize: "13px" }}>
                Paste a repo URL above to get started
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <ProjectCard
                  key={`${p.owner}/${p.repo}/${p.language}`}
                  project={p}
                  onClick={() => router.push(`/${p.owner}/${p.repo}`)}
                />
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function ProjectCard({
  project,
  onClick,
}: {
  project: Project;
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="text-left rounded-2xl p-5 transition-all w-full"
      style={{
        backgroundColor: hovered ? "#FFFDF9" : "#FDFAF5",
        boxShadow: hovered
          ? "0 4px 16px rgba(60, 40, 20, 0.1), 0 1px 3px rgba(60, 40, 20, 0.06)"
          : "0 1px 4px rgba(60, 40, 20, 0.05)",
        border: "1px solid",
        borderColor: hovered ? "#DDD3C4" : "#EDE5D8",
        transform: hovered ? "translateY(-1px)" : "translateY(0)",
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p style={{ color: "#9A8A7A", fontSize: "11px" }}>{project.owner}</p>
          <p
            style={{
              color: "#2C2420",
              fontSize: "14px",
              fontWeight: 600,
              lineHeight: 1.2,
            }}
          >
            {project.repo}
          </p>
        </div>
        <div
          className="flex items-center gap-1 px-2 py-0.5 rounded-full"
          style={{
            backgroundColor: "#F0EAE2",
            fontSize: "11px",
            color: "#7A6A5A",
          }}
        >
          {project.language}
        </div>
      </div>

      <div className="flex items-center gap-1.5 mb-3" style={{ color: "#9A8A7A", fontSize: "12px" }}>
        <FileText size={11} strokeWidth={1.8} />
        {project.page_count} page{project.page_count !== 1 ? "s" : ""}
      </div>

      <div className="flex items-center justify-end">
        <div
          className="flex items-center gap-1"
          style={{ color: "#B0A090", fontSize: "12px" }}
        >
          <Clock size={11} strokeWidth={1.8} />
          {timeAgo(project.updated_at)}
        </div>
      </div>
    </button>
  );
}
