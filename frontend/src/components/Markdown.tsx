"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

interface MarkdownProps {
  content: string;
}

export function Markdown({ content }: MarkdownProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const renderMermaid = async () => {
      if (!containerRef.current) return;
      const nodes = containerRef.current.querySelectorAll<HTMLElement>(
        "pre code.language-mermaid, pre code[class*='language-mermaid']"
      );
      if (nodes.length === 0) return;
      const mermaid = (await import("mermaid")).default;
      mermaid.initialize({
        startOnLoad: false,
        theme: "neutral",
        suppressErrorRendering: true,
        flowchart: { useMaxWidth: false },
        sequence: { useMaxWidth: false },
      });
      nodes.forEach(async (node, i) => {
        const pre = node.parentElement;
        if (!pre) return;
        const id = `mermaid-${Date.now()}-${i}`;
        try {
          const { svg } = await mermaid.render(id, node.textContent || "");
          const wrapper = document.createElement("div");
          wrapper.innerHTML = svg;
          wrapper.className = "my-4 flex justify-center overflow-x-auto";
          // Let the SVG use its intrinsic size instead of being clipped
          const svgEl = wrapper.querySelector("svg");
          if (svgEl) {
            svgEl.style.minWidth = "fit-content";
            svgEl.removeAttribute("height");
          }
          pre.replaceWith(wrapper);
        } catch {
          // leave as code block if render fails
        }
      });
    };
    renderMermaid();
  }, [content]);

  return (
    <div
      ref={containerRef}
      className="prose prose-sm max-w-none"
      style={{
        color: "#5A4E44",
        lineHeight: 1.75,
      }}
    >
      <style>{`
        .prose h1 { color: #2C2420; font-size: 1.6rem; font-weight: 600; letter-spacing: -0.02em; border-bottom: none; }
        .prose h2 { color: #2C2420; font-size: 1.1rem; font-weight: 600; padding-left: 10px; border-left: 2.5px solid #C4714A; margin-top: 2rem; margin-bottom: 0.5rem; }
        .prose h3 { color: #3A3228; font-size: 0.95rem; font-weight: 600; margin-top: 1.25rem; }
        .prose p { color: #5A4E44; font-size: 0.92rem; margin-bottom: 0.75rem; }
        .prose a { color: #C4714A; text-decoration: underline; }
        .prose code { background: #E8E0D5; color: #7A6A5A; padding: 2px 6px; border-radius: 4px; font-size: 0.82rem; font-family: var(--font-geist-mono), ui-monospace, monospace; }
        .prose pre { background: #2C2420; color: rgba(255,255,255,0.85); border-radius: 12px; padding: 1rem; overflow-x: auto; }
        .prose pre code { background: transparent; color: inherit; padding: 0; font-size: 0.8rem; }
        .prose ul, .prose ol { color: #5A4E44; }
        .prose li { margin-bottom: 0.25rem; font-size: 0.92rem; }
        .prose blockquote { border-left: 3px solid #C4714A; background: #F5F0E8; padding: 0.5rem 1rem; border-radius: 0 8px 8px 0; color: #5A4E44; }
        .prose table { border-collapse: collapse; width: 100%; }
        .prose th { background: #F0E8DE; color: #3A3228; font-weight: 600; padding: 0.5rem 0.75rem; border: 1px solid #E8E0D5; font-size: 0.85rem; }
        .prose td { padding: 0.45rem 0.75rem; border: 1px solid #E8E0D5; color: #5A4E44; font-size: 0.85rem; }
        .prose tr:nth-child(even) td { background: #FAF7F2; }
        .prose hr { border-color: #E8E0D5; }
        .prose strong { color: #3A3228; font-weight: 600; }
        .prose .mermaid-diagram svg { max-width: none; }
      `}</style>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
