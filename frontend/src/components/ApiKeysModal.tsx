"use client";

import { useState, useEffect, useRef } from "react";
import { X, Key, Eye, EyeOff, Check } from "lucide-react";

interface ApiKeys {
  google: string;
  openrouter: string;
}

interface ApiKeysModalProps {
  onClose: () => void;
}

export function ApiKeysModal({ onClose }: ApiKeysModalProps) {
  const [keys, setKeys] = useState<ApiKeys>({ google: "", openrouter: "" });
  const [showGoogle, setShowGoogle] = useState(false);
  const [showOpenrouter, setShowOpenrouter] = useState(false);
  const [saved, setSaved] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("apiKeys");
      if (stored) setKeys(JSON.parse(stored));
    } catch {}
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  function handleSave() {
    localStorage.setItem("apiKeys", JSON.stringify(keys));
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 800);
  }

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ backgroundColor: "rgba(44, 36, 32, 0.35)", backdropFilter: "blur(4px)" }}
    >
      <div
        className="w-full max-w-md rounded-2xl"
        style={{
          backgroundColor: "#FFFDF9",
          border: "1px solid #E8E0D5",
          boxShadow: "0 8px 40px rgba(44, 36, 32, 0.18), 0 2px 8px rgba(44, 36, 32, 0.08)",
          padding: "24px",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: "#F0E8DE" }}
            >
              <Key size={13} strokeWidth={1.8} style={{ color: "#C4714A" }} />
            </div>
            <span style={{ color: "#2C2420", fontSize: "14px", fontWeight: 600 }}>
              API Keys
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors"
            style={{ color: "#B0A090" }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.backgroundColor = "#F0EAE2")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.backgroundColor = "transparent")}
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <p style={{ color: "#9A8A7A", fontSize: "13px", lineHeight: 1.6, marginBottom: "20px" }}>
          Keys are stored only in your browser and sent directly to the backend — they are never saved on the server.
        </p>

        {/* Google API Key */}
        <div style={{ marginBottom: "16px" }}>
          <label
            style={{
              display: "block",
              color: "#7A6A5A",
              fontSize: "11.5px",
              fontWeight: 500,
              letterSpacing: "0.03em",
              marginBottom: "6px",
            }}
          >
            Google API Key
          </label>
          <div className="relative flex items-center">
            <input
              type={showGoogle ? "text" : "password"}
              value={keys.google}
              onChange={(e) => setKeys((k) => ({ ...k, google: e.target.value }))}
              placeholder="AIzaSy…"
              className="w-full outline-none"
              style={{
                padding: "8px 36px 8px 12px",
                borderRadius: "10px",
                border: "1.5px solid #EDE5D8",
                backgroundColor: "#FAF7F2",
                color: "#3A3228",
                fontSize: "13px",
                fontFamily: "ui-monospace, monospace",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "#C4714A")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#EDE5D8")}
            />
            <button
              onClick={() => setShowGoogle((v) => !v)}
              className="absolute right-2.5"
              style={{ color: "#B0A090" }}
              type="button"
            >
              {showGoogle ? <EyeOff size={15} strokeWidth={1.8} /> : <Eye size={15} strokeWidth={1.8} />}
            </button>
          </div>
        </div>

        {/* OpenRouter API Key */}
        <div style={{ marginBottom: "24px" }}>
          <label
            style={{
              display: "block",
              color: "#7A6A5A",
              fontSize: "11.5px",
              fontWeight: 500,
              letterSpacing: "0.03em",
              marginBottom: "6px",
            }}
          >
            OpenRouter API Key
          </label>
          <div className="relative flex items-center">
            <input
              type={showOpenrouter ? "text" : "password"}
              value={keys.openrouter}
              onChange={(e) => setKeys((k) => ({ ...k, openrouter: e.target.value }))}
              placeholder="sk-or-…"
              className="w-full outline-none"
              style={{
                padding: "8px 36px 8px 12px",
                borderRadius: "10px",
                border: "1.5px solid #EDE5D8",
                backgroundColor: "#FAF7F2",
                color: "#3A3228",
                fontSize: "13px",
                fontFamily: "ui-monospace, monospace",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "#C4714A")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#EDE5D8")}
            />
            <button
              onClick={() => setShowOpenrouter((v) => !v)}
              className="absolute right-2.5"
              style={{ color: "#B0A090" }}
              type="button"
            >
              {showOpenrouter ? <EyeOff size={15} strokeWidth={1.8} /> : <Eye size={15} strokeWidth={1.8} />}
            </button>
          </div>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl transition-all"
          style={{
            backgroundColor: saved ? "#8B9E7A" : "#C4714A",
            color: "white",
            fontSize: "13.5px",
            fontWeight: 500,
            boxShadow: saved
              ? "0 2px 8px rgba(139, 158, 122, 0.3)"
              : "0 2px 8px rgba(196, 113, 74, 0.3)",
          }}
        >
          {saved ? (
            <>
              <Check size={14} strokeWidth={2.5} />
              Saved
            </>
          ) : (
            "Save Keys"
          )}
        </button>
      </div>
    </div>
  );
}
