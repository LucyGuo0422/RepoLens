"use client";

import { useState, useEffect, useRef, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  Send,
  FileText,
  BookOpen,
  ChevronRight,
  ChevronDown,
  CircleHelp,
  Code2,
  Layers,
  Loader2,
  Zap,
  ScanSearch,
} from "lucide-react";
import {
  fetchStreamWithSources,
  SourceFile,
} from "@/hooks/useStreamingContent";
import { Markdown } from "@/components/Markdown";

type ChatMode = "fast" | "deep";

interface Message {
  id: string;
  question: string;
  answer: string;
  sources: SourceFile[];
  mode: ChatMode;
  isStreaming?: boolean;
}

function ModeBadge({ mode, small = false }: { mode: ChatMode; small?: boolean }) {
  const px = small ? "6px" : "8px";
  const py = small ? "1px" : "2px";
  const fs = small ? "10px" : "11px";
  if (mode === "fast") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded-md font-medium"
        style={{
          backgroundColor: "#FEF3EB",
          color: "#C4714A",
          border: "1px solid #F5D9C4",
          padding: `${py} ${px}`,
          fontSize: fs,
        }}
      >
        <Zap size={9} strokeWidth={2} />⚡ Fast
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md font-medium"
      style={{
        backgroundColor: "#EDF3EA",
        color: "#6B8F5E",
        border: "1px solid #C8DEC0",
        padding: `${py} ${px}`,
        fontSize: fs,
      }}
    >
      <ScanSearch size={9} strokeWidth={2} />🔬 Deep
    </span>
  );
}

export default function ChatPage({
  params,
}: {
  params: Promise<{ owner: string; repo: string }>;
}) {
  const { owner, repo } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();

  const [messages, setMessages] = useState<Message[]>([]);
  const [followUp, setFollowUp] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const [sessionId] = useState(() => `${owner}__${repo}__${Date.now()}`);
  const initialAsked = useRef(false);
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<ChatMode>(
    (searchParams.get("mode") as ChatMode) ?? "fast"
  );

  const repoUrl = `https://github.com/${owner}/${repo}`;
  const initialQuestion = searchParams.get("q") || "";

  useEffect(() => {
    if (initialQuestion && !initialAsked.current) {
      initialAsked.current = true;
      askQuestion(initialQuestion, (searchParams.get("mode") as ChatMode) ?? "fast");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function askQuestion(question: string, questionMode: ChatMode) {
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const newMsg: Message = {
      id,
      question,
      answer: "",
      sources: [],
      mode: questionMode,
      isStreaming: true,
    };

    setMessages((prev) => {
      const next = [...prev, newMsg];
      setActiveIdx(next.length - 1);
      return next;
    });
    setExpandedFiles(new Set());

    const stored = JSON.parse(localStorage.getItem("wikiGenConfig") || "{}");
    const provider = stored.provider ?? "google";
    const chatModel = stored.model ?? undefined;
    const language = stored.language ?? "English";

    try {
      if (questionMode === "deep") {
        await fetchStreamWithSources(
          "/chat/deep-research",
          {
            repo_url: repoUrl,
            query: question,
            provider,
            model: chatModel,
            language,
          },
          (accumulated) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, answer: accumulated } : m))
            );
          },
          (sources) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, sources } : m))
            );
            if (sources.length > 0) {
              setExpandedFiles(new Set([sources[0].file_path]));
            }
          }
        );
      } else {
        await fetchStreamWithSources(
          "/chat/stream",
          {
            repo_url: repoUrl,
            query: question,
            provider,
            model: chatModel,
            language,
            session_id: sessionId,
          },
          (accumulated) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, answer: accumulated } : m))
            );
          },
          (sources) => {
            setMessages((prev) =>
              prev.map((m) => (m.id === id ? { ...m, sources } : m))
            );
            if (sources.length > 0) {
              setExpandedFiles(new Set([sources[0].file_path]));
            }
          }
        );
      }

      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, isStreaming: false } : m))
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? {
                ...m,
                answer: "Sorry, something went wrong. Please try again.",
                isStreaming: false,
              }
            : m
        )
      );
    }
  }

  const handleAsk = () => {
    if (!followUp.trim()) return;
    askQuestion(followUp.trim(), mode);
    setFollowUp("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  function toggleFile(filePath: string) {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filePath)) next.delete(filePath);
      else next.add(filePath);
      return next;
    });
  }

  const activeMessage = messages[activeIdx];

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: "#FAF7F2" }}
    >
      {/* Top bar */}
      <div
        className="sticky top-0 z-50 h-14 px-6 flex items-center gap-4"
        style={{
          backgroundColor: "#FAF7F2",
          borderBottom: "1px solid #E8E0D5",
        }}
      >
        <button
          onClick={() => router.push(`/${owner}/${repo}`)}
          className="flex items-center gap-1.5 transition-colors"
          style={{ color: "#9A8A7A", fontSize: "13px" }}
          onMouseEnter={(e) =>
            ((e.currentTarget as HTMLElement).style.color = "#3A3228")
          }
          onMouseLeave={(e) =>
            ((e.currentTarget as HTMLElement).style.color = "#9A8A7A")
          }
        >
          <ArrowLeft size={14} strokeWidth={1.8} />
          Back to Wiki
        </button>

        <div className="h-4 w-px" style={{ backgroundColor: "#E8E0D5" }} />

        <div className="flex items-center gap-1.5">
          {[`${owner}/${repo}`, "Q&A"].map((crumb, i) => (
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
        </div>

        {/* Current mode badge */}
        <div className="ml-auto">
          <ModeBadge mode={mode} />
        </div>
      </div>

      {/* Empty state */}
      {messages.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-center">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: "#F0E8DE" }}
            >
              <BookOpen size={20} strokeWidth={1.5} style={{ color: "#C4714A" }} />
            </div>
            <p style={{ color: "#9A8A7A", fontSize: "14px" }}>
              Ask a question about{" "}
              <span style={{ color: "#3A3228", fontWeight: 500 }}>
                {owner}/{repo}
              </span>
            </p>
          </div>
        </div>
      )}

      {/* Main content */}
      {messages.length > 0 && (
        <div className="flex-1 flex max-w-7xl w-full mx-auto px-4 gap-0 pb-36">
          {/* Left panel — answer thread */}
          <div
            className="flex-1 min-w-0 py-8 px-6 overflow-y-auto"
            style={{ maxWidth: "58%" }}
          >
            {/* Previous messages */}
            {messages.length > 1 && (
              <div className="mb-8 space-y-3">
                {messages.slice(0, -1).map((msg, idx) => (
                  <button
                    key={msg.id}
                    onClick={() => setActiveIdx(idx)}
                    className="w-full text-left p-3.5 rounded-xl transition-all"
                    style={{
                      backgroundColor:
                        activeIdx === idx ? "#F0E8DE" : "#F5F0E8",
                      border: "1px solid",
                      borderColor:
                        activeIdx === idx ? "#D8C8B4" : "#EDE5D8",
                    }}
                  >
                    <div className="flex items-start gap-2.5">
                      <CircleHelp
                        size={13}
                        strokeWidth={1.7}
                        style={{
                          color: "#C4714A",
                          marginTop: "2px",
                          flexShrink: 0,
                        }}
                      />
                      <p
                        style={{
                          color: "#5A4E44",
                          fontSize: "13px",
                          lineHeight: 1.5,
                          flex: 1,
                        }}
                      >
                        {msg.question}
                      </p>
                      <ModeBadge mode={msg.mode} small />
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Active Q&A */}
            {activeMessage && (
              <div>
                {/* Question callout */}
                <div
                  className="rounded-xl p-4 mb-6 flex items-start gap-3"
                  style={{
                    backgroundColor: "#F0E8DE",
                    border: "1px solid #DDD0BE",
                  }}
                >
                  <div
                    className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                    style={{ backgroundColor: "#C4714A" }}
                  >
                    <CircleHelp size={13} strokeWidth={1.8} color="white" />
                  </div>
                  <p
                    style={{
                      color: "#3A3228",
                      fontSize: "15px",
                      fontWeight: 500,
                      lineHeight: 1.5,
                      flex: 1,
                    }}
                  >
                    {activeMessage.question}
                  </p>
                  <ModeBadge mode={activeMessage.mode} />
                </div>

                {/* Answer */}
                {activeMessage.isStreaming && !activeMessage.answer ? (
                  <div className="flex items-center gap-2" style={{ color: "#9A8A7A" }}>
                    <Loader2 size={16} className="animate-spin" />
                    <span style={{ fontSize: "14px" }}>
                      {activeMessage.mode === "deep" ? "Researching…" : "Thinking…"}
                    </span>
                  </div>
                ) : (
                  <Markdown content={activeMessage.answer} />
                )}

                {/* Sources (fast mode only) */}
                {!activeMessage.isStreaming &&
                  activeMessage.sources.length > 0 && (
                    <div
                      className="mt-8 p-4 rounded-xl"
                      style={{
                        backgroundColor: "#F5F0E8",
                        border: "1px solid #E8E0D5",
                      }}
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <Layers
                          size={13}
                          strokeWidth={1.7}
                          style={{ color: "#8B9E7A" }}
                        />
                        <h4
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#7A6A5A",
                            textTransform: "uppercase",
                            letterSpacing: "0.06em",
                          }}
                        >
                          Sources Referenced
                        </h4>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {activeMessage.sources.map((src) => (
                          <span
                            key={src.file_path}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg"
                            style={{
                              backgroundColor: "#E8E0D5",
                              color: "#7A6A5A",
                              fontSize: "11.5px",
                              fontFamily: "var(--font-geist-mono), monospace",
                            }}
                          >
                            <FileText
                              size={10}
                              strokeWidth={1.8}
                              style={{ flexShrink: 0 }}
                            />
                            {src.file_path}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            )}
          </div>

          {/* Divider */}
          <div
            className="shrink-0 w-px my-8"
            style={{ backgroundColor: "#E8E0D5" }}
          />

          {/* Right panel */}
          <div
            className="py-8 px-6 shrink-0 overflow-y-auto flex flex-col gap-4"
            style={{ width: "42%", height: "calc(100vh - 3.5rem)" }}
          >
            {/* Repository card */}
            <div
              className="rounded-xl p-5 shrink-0"
              style={{
                backgroundColor: "#F5F0E8",
                border: "1px solid #E8E0D5",
              }}
            >
              <div className="flex items-center gap-2 mb-3">
                <BookOpen size={14} strokeWidth={1.7} style={{ color: "#8B9E7A" }} />
                <h3
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#5A4E44",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  Repository
                </h3>
              </div>
              <p style={{ color: "#7A6A5A", fontSize: "13px" }}>
                <span style={{ fontWeight: 500, color: "#3A3228" }}>
                  {owner}/{repo}
                </span>
              </p>
              <a
                href={repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "#C4714A",
                  fontSize: "12px",
                  textDecoration: "underline",
                }}
              >
                View on GitHub →
              </a>
            </div>

            {/* Related Code (fast mode only) */}
            {activeMessage && activeMessage.sources.length > 0 && (
              <div
                className="rounded-xl p-5 flex-1 min-h-0 overflow-y-auto"
                style={{
                  backgroundColor: "#F5F0E8",
                  border: "1px solid #E8E0D5",
                }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Code2 size={14} strokeWidth={1.7} style={{ color: "#8B9E7A" }} />
                  <h3
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#5A4E44",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    Related Code ({activeMessage.sources.length} files)
                  </h3>
                </div>

                <div className="space-y-1">
                  {activeMessage.sources.map((src) => {
                    const isExpanded = expandedFiles.has(src.file_path);
                    return (
                      <div key={src.file_path}>
                        <button
                          onClick={() => toggleFile(src.file_path)}
                          className="w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg transition-all"
                          style={{
                            backgroundColor: isExpanded ? "#EDE5D8" : "transparent",
                            color: "#5A4E44",
                            fontSize: "12px",
                            fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
                          }}
                          onMouseEnter={(e) => {
                            if (!isExpanded)
                              (e.currentTarget as HTMLElement).style.backgroundColor = "#F0E8DE";
                          }}
                          onMouseLeave={(e) => {
                            if (!isExpanded)
                              (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
                          }}
                        >
                          {isExpanded ? (
                            <ChevronDown size={12} strokeWidth={2} style={{ flexShrink: 0 }} />
                          ) : (
                            <ChevronRight size={12} strokeWidth={2} style={{ flexShrink: 0 }} />
                          )}
                          <FileText size={11} strokeWidth={1.8} style={{ flexShrink: 0, color: "#9A8A7A" }} />
                          <span className="truncate">{src.file_path}</span>
                          <span
                            className="ml-auto shrink-0 px-1.5 py-0.5 rounded text-center"
                            style={{
                              backgroundColor: "#E8E0D5",
                              color: "#9A8A7A",
                              fontSize: "10px",
                              minWidth: "20px",
                            }}
                          >
                            {src.chunks.length}
                          </span>
                        </button>

                        {isExpanded && (
                          <div className="mt-1 mb-2 space-y-2 pl-2">
                            {src.chunks.map((chunk, ci) => (
                              <pre
                                key={ci}
                                className="rounded-lg p-3 overflow-x-auto text-xs"
                                style={{
                                  backgroundColor: "#2C2420",
                                  color: "rgba(255,255,255,0.85)",
                                  fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
                                  lineHeight: 1.6,
                                  whiteSpace: "pre-wrap",
                                  wordBreak: "break-word",
                                }}
                              >
                                {chunk.content}
                              </pre>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Conversation list */}
            <div
              className="rounded-xl p-5 shrink-0"
              style={{
                backgroundColor: "#F5F0E8",
                border: "1px solid #E8E0D5",
              }}
            >
              <div className="flex items-center gap-2 mb-3">
                <CircleHelp size={14} strokeWidth={1.7} style={{ color: "#8B9E7A" }} />
                <h3
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#5A4E44",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                  }}
                >
                  Conversation ({messages.length})
                </h3>
              </div>
              <div className="space-y-2">
                {messages.map((msg, idx) => (
                  <button
                    key={msg.id}
                    onClick={() => setActiveIdx(idx)}
                    className="w-full text-left rounded-lg px-3 py-2 transition-all"
                    style={{
                      backgroundColor:
                        activeIdx === idx ? "#EDE5D8" : "transparent",
                      color: activeIdx === idx ? "#3A3228" : "#7A6A5A",
                      fontSize: "12.5px",
                      lineHeight: 1.4,
                    }}
                  >
                    {msg.question.length > 55
                      ? msg.question.slice(0, 52) + "…"
                      : msg.question}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating ask bar with mode toggle */}
      <div
        className="fixed bottom-0 left-0 right-0 px-6 pb-5 pt-3"
        style={{
          background: "linear-gradient(to top, #FAF7F2 65%, transparent)",
        }}
      >
        <div
          className="max-w-4xl mx-auto rounded-2xl overflow-hidden"
          style={{
            backgroundColor: "#FFFDF9",
            boxShadow: "0 4px 24px rgba(60,40,20,0.1)",
            border: "1px solid #EDE5D8",
          }}
        >
          {/* Input row */}
          <div className="flex items-center gap-3 px-3 pt-3 pb-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
              style={{ backgroundColor: "#F0E8DE" }}
            >
              <BookOpen size={13} strokeWidth={1.8} style={{ color: "#C4714A" }} />
            </div>
            <input
              type="text"
              value={followUp}
              onChange={(e) => setFollowUp(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                messages.length === 0
                  ? "Ask a question about this repo…"
                  : "Ask a follow-up question…"
              }
              className="flex-1 bg-transparent outline-none"
              style={{ color: "#3A3228", fontSize: "14px", caretColor: "#C4714A" }}
            />
            <button
              onClick={handleAsk}
              disabled={!followUp.trim()}
              className="w-8 h-8 rounded-xl flex items-center justify-center transition-all"
              style={{
                backgroundColor: followUp.trim() ? "#C4714A" : "#EDE5D8",
                color: followUp.trim() ? "white" : "#B0A090",
              }}
            >
              <Send size={13} strokeWidth={2} />
            </button>
          </div>

          {/* Divider */}
          <div style={{ height: "1px", backgroundColor: "#F0EAE2", margin: "0 12px" }} />

          {/* Mode toggle row */}
          <div className="flex items-center gap-3 px-3 py-2">
            <div
              className="flex items-center p-0.5 rounded-lg"
              style={{ backgroundColor: "#F0EAE2" }}
            >
              <button
                onClick={() => setMode("fast")}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all"
                style={{
                  backgroundColor: mode === "fast" ? "#FFFDF9" : "transparent",
                  color: mode === "fast" ? "#C4714A" : "#9A8A7A",
                  fontSize: "12px",
                  fontWeight: 500,
                  boxShadow:
                    mode === "fast"
                      ? "0 1px 3px rgba(60,40,20,0.08), 0 0 0 1px rgba(60,40,20,0.06)"
                      : "none",
                }}
              >
                <Zap size={11} strokeWidth={2} />
                Fast
              </button>
              <button
                onClick={() => setMode("deep")}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-all"
                style={{
                  backgroundColor: mode === "deep" ? "#FFFDF9" : "transparent",
                  color: mode === "deep" ? "#6B8F5E" : "#9A8A7A",
                  fontSize: "12px",
                  fontWeight: 500,
                  boxShadow:
                    mode === "deep"
                      ? "0 1px 3px rgba(60,40,20,0.08), 0 0 0 1px rgba(60,40,20,0.06)"
                      : "none",
                }}
              >
                <ScanSearch size={11} strokeWidth={2} />
                Deep Research
              </button>
            </div>
            <span style={{ fontSize: "11.5px", color: "#B0A090" }}>
              {mode === "fast"
                ? "Quick answer from indexed docs"
                : "Thorough analysis across the full codebase"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
