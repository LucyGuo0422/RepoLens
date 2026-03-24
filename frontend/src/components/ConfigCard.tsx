"use client";

import { useState, useEffect, useRef } from "react";
import {
  GitBranch,
  ArrowRight,
  ChevronDown,
  Globe,
  Cpu,
  Layers,
  X,
  Check,
} from "lucide-react";

const MODELS: Record<string, { value: string; label: string; tag?: string }[]> = {
  google: [
    { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash", tag: "Fast" },
    { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash", tag: "New" },
    { value: "gemini-1.5-pro",   label: "Gemini 1.5 Pro" },
  ],
  openrouter: [
    { value: "anthropic/claude-sonnet-4-5",        label: "Claude Sonnet 4.5",  tag: "Powerful" },
    { value: "openai/gpt-4o",                      label: "GPT-4o",             tag: "Popular" },
    { value: "openai/gpt-4o-mini",                 label: "GPT-4o Mini",        tag: "Fast" },
    { value: "anthropic/claude-3-5-haiku",         label: "Claude 3.5 Haiku",   tag: "Lightweight" },
    { value: "meta-llama/llama-3.3-70b-instruct",  label: "Llama 3.3 70B",      tag: "Open" },
  ],
};

export interface WikiConfig {
  url: string;
  language: "English" | "Chinese";
  provider: "google" | "openrouter";
  model: string;
}

interface ConfigCardProps {
  onClose: () => void;
  onGenerate: (config: WikiConfig) => void;
  initialUrl?: string;
}

export function ConfigCard({ onClose, onGenerate, initialUrl = "" }: ConfigCardProps) {
  const [config, setConfig] = useState<WikiConfig>({
    url: initialUrl,
    language: "English",
    provider: "google",
    model: "gemini-2.0-flash",
  });

  const urlInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    urlInputRef.current?.focus();
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const handleProviderChange = (provider: "google" | "openrouter") => {
    setConfig((prev) => ({
      ...prev,
      provider,
      model: MODELS[provider][0].value,
    }));
  };

  const canGenerate = config.url.trim().length > 0;

  const handleGenerate = () => {
    if (canGenerate) onGenerate(config);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && canGenerate) handleGenerate();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ backgroundColor: "rgba(44, 36, 32, 0.35)", backdropFilter: "blur(4px)" }}
      onClick={handleBackdropClick}
    >
      <div
        className="w-full max-w-lg relative"
        style={{
          backgroundColor: "#FFFDF9",
          borderRadius: "20px",
          border: "1px solid #E8E0D5",
          boxShadow: "0 8px 40px rgba(44, 36, 32, 0.18), 0 2px 8px rgba(44, 36, 32, 0.08)",
          animation: "cardIn 0.2s cubic-bezier(0.34, 1.4, 0.64, 1)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 pt-5 pb-4"
          style={{ borderBottom: "1px solid #F0EAE2" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: "#F0E8DE" }}
            >
              <GitBranch size={13} strokeWidth={1.8} style={{ color: "#C4714A" }} />
            </div>
            <span style={{ color: "#2C2420", fontSize: "14px", fontWeight: 600 }}>
              Configure Wiki Generation
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

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* URL input */}
          <Field label="Repository URL" icon={<GitBranch size={13} strokeWidth={1.7} />}>
            <div
              className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl"
              style={{
                backgroundColor: "#FAF7F2",
                border: "1.5px solid #EDE5D8",
                transition: "border-color 0.15s",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "#C4714A")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#EDE5D8")}
            >
              <span style={{ color: "#C4B8AB", display: "flex" }}>
                <GitBranch size={14} strokeWidth={1.7} />
              </span>
              <input
                ref={urlInputRef}
                type="text"
                value={config.url}
                onChange={(e) => setConfig((p) => ({ ...p, url: e.target.value }))}
                onKeyDown={handleKeyDown}
                placeholder="https://github.com/owner/repo"
                className="flex-1 bg-transparent outline-none"
                style={{ color: "#3A3228", fontSize: "14px", caretColor: "#C4714A" }}
              />
              {config.url && (
                <button
                  onClick={() => setConfig((p) => ({ ...p, url: "" }))}
                  style={{ color: "#C4B8AB", display: "flex" }}
                >
                  <X size={12} strokeWidth={2} />
                </button>
              )}
            </div>
          </Field>

          {/* Row: Language + Provider */}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Output language" icon={<Globe size={13} strokeWidth={1.7} />}>
              <SelectBox
                value={config.language}
                onChange={(v) => setConfig((p) => ({ ...p, language: v as "English" | "Chinese" }))}
                options={[
                  { value: "English", label: "English" },
                  { value: "Chinese", label: "中文 (Chinese)" },
                ]}
              />
            </Field>

            <Field label="Model provider" icon={<Cpu size={13} strokeWidth={1.7} />}>
              <ProviderToggle value={config.provider} onChange={handleProviderChange} />
            </Field>
          </div>

          {/* Model selection */}
          <Field label="Model" icon={<Layers size={13} strokeWidth={1.7} />}>
            <ModelSelect
              provider={config.provider}
              value={config.model}
              onChange={(v) => setConfig((p) => ({ ...p, model: v }))}
            />
          </Field>
        </div>

        {/* Footer */}
        <div className="px-6 pb-5 pt-1 flex items-center justify-between">
          <p style={{ color: "#B0A090", fontSize: "12px" }}>
            Public repos only · No account needed
          </p>
          <button
            onClick={handleGenerate}
            disabled={!canGenerate}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl transition-all"
            style={{
              backgroundColor: canGenerate ? "#C4714A" : "#EDE5D8",
              color: canGenerate ? "white" : "#B0A090",
              fontSize: "13.5px",
              fontWeight: 500,
              boxShadow: canGenerate ? "0 2px 8px rgba(196, 113, 74, 0.3)" : "none",
              cursor: canGenerate ? "pointer" : "not-allowed",
            }}
            onMouseEnter={(e) => {
              if (canGenerate) (e.currentTarget as HTMLElement).style.backgroundColor = "#B3623C";
            }}
            onMouseLeave={(e) => {
              if (canGenerate) (e.currentTarget as HTMLElement).style.backgroundColor = "#C4714A";
            }}
          >
            Generate Wiki
            <ArrowRight size={13} strokeWidth={2} />
          </button>
        </div>
      </div>

      <style>{`
        @keyframes cardIn {
          from { opacity: 0; transform: translateY(12px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)    scale(1); }
        }
      `}</style>
    </div>
  );
}

// ── sub-components ──────────────────────────────────────────────────────────

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <span style={{ color: "#B0A090", display: "flex" }}>{icon}</span>
        <label
          style={{
            color: "#7A6A5A",
            fontSize: "11.5px",
            fontWeight: 500,
            letterSpacing: "0.03em",
          }}
        >
          {label}
        </label>
      </div>
      {children}
    </div>
  );
}

function SelectBox({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl"
        style={{
          backgroundColor: "#FAF7F2",
          border: `1.5px solid ${open ? "#C4714A" : "#EDE5D8"}`,
          color: "#3A3228",
          fontSize: "13.5px",
          transition: "border-color 0.15s",
        }}
      >
        <span>{selected?.label}</span>
        <ChevronDown
          size={13}
          strokeWidth={2}
          style={{
            color: "#B0A090",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 right-0 mt-1.5 rounded-xl overflow-hidden z-10"
          style={{
            backgroundColor: "#FFFDF9",
            border: "1px solid #E8E0D5",
            boxShadow: "0 4px 20px rgba(44, 36, 32, 0.12)",
          }}
        >
          {options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              className="w-full flex items-center justify-between px-3.5 py-2.5 transition-colors text-left"
              style={{
                backgroundColor: value === opt.value ? "#F5F0E8" : "transparent",
                color: value === opt.value ? "#C4714A" : "#5A4E44",
                fontSize: "13.5px",
              }}
              onMouseEnter={(e) => {
                if (value !== opt.value)
                  (e.currentTarget as HTMLElement).style.backgroundColor = "#FAF7F2";
              }}
              onMouseLeave={(e) => {
                if (value !== opt.value)
                  (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              }}
            >
              {opt.label}
              {value === opt.value && (
                <Check size={12} strokeWidth={2.5} style={{ color: "#C4714A" }} />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ProviderToggle({
  value,
  onChange,
}: {
  value: "google" | "openrouter";
  onChange: (v: "google" | "openrouter") => void;
}) {
  return (
    <div className="flex p-0.5 rounded-xl" style={{ backgroundColor: "#F0EAE2" }}>
      {(["google", "openrouter"] as const).map((p) => {
        const active = value === p;
        return (
          <button
            key={p}
            onClick={() => onChange(p)}
            className="flex-1 py-2 rounded-lg transition-all"
            style={{
              backgroundColor: active ? "#FFFDF9" : "transparent",
              color: active ? "#2C2420" : "#9A8A7A",
              fontSize: "12.5px",
              fontWeight: active ? 600 : 400,
              boxShadow: active
                ? "0 1px 3px rgba(44,36,32,0.08), 0 0 0 1px rgba(44,36,32,0.05)"
                : "none",
              transition: "all 0.18s",
            }}
          >
            {p === "google" ? "Google" : "OpenRouter"}
          </button>
        );
      })}
    </div>
  );
}

const TAG_COLORS: Record<string, { bg: string; text: string }> = {
  Powerful:    { bg: "#F0E8DE", text: "#C4714A" },
  Fast:        { bg: "#EDF3EA", text: "#6B8F5E" },
  Popular:     { bg: "#EAF0F8", text: "#4A78B4" },
  Open:        { bg: "#F5EAF5", text: "#8A5AA0" },
  Lightweight: { bg: "#FAF3E0", text: "#9A7A30" },
  New:         { bg: "#EAF0F8", text: "#4A78B4" },
};

function ModelSelect({
  provider,
  value,
  onChange,
}: {
  provider: "google" | "openrouter";
  value: string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const models = MODELS[provider];
  const selected = models.find((m) => m.value === value) ?? models[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl"
        style={{
          backgroundColor: "#FAF7F2",
          border: `1.5px solid ${open ? "#C4714A" : "#EDE5D8"}`,
          color: "#3A3228",
          fontSize: "13.5px",
          transition: "border-color 0.15s",
        }}
      >
        <div className="flex items-center gap-2">
          <span>{selected.label}</span>
          {selected.tag && (
            <span
              className="px-1.5 py-0.5 rounded-md"
              style={{
                fontSize: "10px",
                fontWeight: 500,
                backgroundColor: TAG_COLORS[selected.tag]?.bg ?? "#F0EAE2",
                color: TAG_COLORS[selected.tag]?.text ?? "#7A6A5A",
              }}
            >
              {selected.tag}
            </span>
          )}
        </div>
        <ChevronDown
          size={13}
          strokeWidth={2}
          style={{
            color: "#B0A090",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 right-0 mt-1.5 rounded-xl overflow-hidden z-10"
          style={{
            backgroundColor: "#FFFDF9",
            border: "1px solid #E8E0D5",
            boxShadow: "0 4px 24px rgba(44, 36, 32, 0.14)",
          }}
        >
          <div
            className="px-3.5 pt-2.5 pb-1.5"
            style={{ borderBottom: "1px solid #F0EAE2" }}
          >
            <span
              style={{
                fontSize: "10.5px",
                color: "#B0A090",
                fontWeight: 500,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              {provider === "google" ? "Google AI" : "OpenRouter"}
            </span>
          </div>

          {models.map((model) => (
            <button
              key={model.value}
              onClick={() => { onChange(model.value); setOpen(false); }}
              className="w-full flex items-center justify-between px-3.5 py-2.5 transition-colors"
              style={{
                backgroundColor: value === model.value ? "#F5F0E8" : "transparent",
              }}
              onMouseEnter={(e) => {
                if (value !== model.value)
                  (e.currentTarget as HTMLElement).style.backgroundColor = "#FAF7F2";
              }}
              onMouseLeave={(e) => {
                if (value !== model.value)
                  (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              }}
            >
              <div className="flex items-center gap-2">
                <span
                  style={{
                    color: value === model.value ? "#C4714A" : "#5A4E44",
                    fontSize: "13.5px",
                  }}
                >
                  {model.label}
                </span>
                {model.tag && (
                  <span
                    className="px-1.5 py-0.5 rounded-md"
                    style={{
                      fontSize: "10px",
                      fontWeight: 500,
                      backgroundColor: TAG_COLORS[model.tag]?.bg ?? "#F0EAE2",
                      color: TAG_COLORS[model.tag]?.text ?? "#7A6A5A",
                    }}
                  >
                    {model.tag}
                  </span>
                )}
              </div>
              {value === model.value && (
                <Check size={12} strokeWidth={2.5} style={{ color: "#C4714A" }} />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
