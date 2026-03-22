"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

interface WikiPage {
  title: string;
  description?: string;
}

interface WikiTreeViewProps {
  pages: WikiPage[];
  activePage: string;
  onSelect: (title: string) => void;
  pageContents?: Record<string, string>;
  onScrollToHeading?: (heading: string) => void;
}

function extractHeadings(markdown: string): string[] {
  return markdown
    .split("\n")
    .filter((line) => /^##\s+/.test(line))
    .map((line) => line.replace(/^##\s+/, "").trim());
}

export function WikiTreeView({
  pages,
  activePage,
  onSelect,
  pageContents,
  onScrollToHeading,
}: WikiTreeViewProps) {
  const [expandedPages, setExpandedPages] = useState<Set<string>>(
    new Set([activePage])
  );

  function toggleExpand(title: string) {
    setExpandedPages((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
  }

  function handlePageClick(title: string) {
    onSelect(title);
    setExpandedPages((prev) => new Set(prev).add(title));
  }

  return (
    <nav className="space-y-0.5">
      {pages.map((page) => {
        const isActive = activePage === page.title;
        const isExpanded = expandedPages.has(page.title);
        const headings =
          pageContents?.[page.title]
            ? extractHeadings(pageContents[page.title])
            : [];

        return (
          <div key={page.title}>
            <div className="flex items-center">
              {/* Expand/collapse toggle */}
              <button
                onClick={() => toggleExpand(page.title)}
                className="p-1 rounded"
                style={{ color: "#B0A090", flexShrink: 0 }}
              >
                {headings.length > 0 ? (
                  isExpanded ? (
                    <ChevronDown size={12} strokeWidth={2} />
                  ) : (
                    <ChevronRight size={12} strokeWidth={2} />
                  )
                ) : (
                  <span style={{ width: 12, display: "inline-block" }} />
                )}
              </button>

              {/* Page title */}
              <button
                onClick={() => handlePageClick(page.title)}
                className="flex-1 text-left px-2 py-1.5 rounded-lg transition-all truncate"
                style={{
                  backgroundColor: isActive ? "#F0E8DE" : "transparent",
                  color: isActive ? "#C4714A" : "#5A4E44",
                  fontSize: "13.5px",
                  fontWeight: isActive ? 600 : 500,
                  borderLeft: isActive
                    ? "2px solid #C4714A"
                    : "2px solid transparent",
                }}
              >
                {page.title}
              </button>
            </div>

            {/* Headings sub-items */}
            {isExpanded && headings.length > 0 && (
              <div className="ml-5 pl-3 space-y-px" style={{ borderLeft: "1px solid #E8E0D5" }}>
                {headings.map((heading) => (
                  <button
                    key={heading}
                    onClick={() => {
                      if (activePage !== page.title) onSelect(page.title);
                      onScrollToHeading?.(heading);
                    }}
                    className="w-full text-left px-2 py-1 rounded transition-all truncate"
                    style={{
                      color: "#9A8A7A",
                      fontSize: "12.5px",
                      fontWeight: 400,
                    }}
                    onMouseEnter={(e) =>
                      ((e.currentTarget as HTMLElement).style.backgroundColor = "#F0E8DE")
                    }
                    onMouseLeave={(e) =>
                      ((e.currentTarget as HTMLElement).style.backgroundColor = "transparent")
                    }
                  >
                    {heading}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}
