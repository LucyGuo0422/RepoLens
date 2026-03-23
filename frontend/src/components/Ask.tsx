"use client";

import { useState } from "react";
import { Send, BookOpen, Zap, ScanSearch } from "lucide-react";

export type ChatMode = "fast" | "deep";

interface AskProps {
  onAsk: (question: string, mode: ChatMode) => void;
  placeholder?: string;
}

export function Ask({ onAsk, placeholder = "Ask a question about this repo…" }: AskProps) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<ChatMode>("fast");

  const handleAsk = () => {
    if (!question.trim()) return;
    onAsk(question.trim(), mode);
    setQuestion("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  return (
    <div
      className="fixed bottom-0 left-0 right-0 px-6 pb-5 pt-3"
      style={{ background: "linear-gradient(to top, #FAF7F2 65%, transparent)" }}
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
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 bg-transparent outline-none"
            style={{ color: "#3A3228", fontSize: "14px", caretColor: "#C4714A" }}
          />
          <button
            onClick={handleAsk}
            disabled={!question.trim()}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-all"
            style={{
              backgroundColor: question.trim() ? "#C4714A" : "#EDE5D8",
              color: question.trim() ? "white" : "#B0A090",
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
  );
}
