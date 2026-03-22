"use client";

import { useState } from "react";
import { Send, BookOpen } from "lucide-react";

interface AskProps {
  onAsk: (question: string) => void;
  placeholder?: string;
}

export function Ask({ onAsk, placeholder = "Ask a question about this repo…" }: AskProps) {
  const [question, setQuestion] = useState("");

  const handleAsk = () => {
    if (!question.trim()) return;
    onAsk(question.trim());
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
      style={{ background: "linear-gradient(to top, #FAF7F2 70%, transparent)" }}
    >
      <div
        className="max-w-4xl mx-auto flex items-center gap-3 p-2 rounded-2xl"
        style={{
          backgroundColor: "#FFFDF9",
          boxShadow:
            "0 4px 20px rgba(60, 40, 20, 0.1), 0 1px 4px rgba(60, 40, 20, 0.06)",
          border: "1px solid #EDE5D8",
        }}
      >
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ml-1"
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
    </div>
  );
}
