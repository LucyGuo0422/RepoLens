"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";

export function Navbar() {
  return (
    <nav
      className="sticky top-0 z-50"
      style={{
        backgroundColor: "#FAF7F2",
        borderBottom: "1px solid #E8E0D5",
        backdropFilter: "blur(8px)",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "#C4714A" }}
          >
            <BookOpen size={14} color="white" strokeWidth={1.8} />
          </div>
          <span style={{ color: "#3A3228", fontSize: "15px", fontWeight: 600 }}>
            RepoLens
          </span>
        </Link>

        <div className="flex items-center gap-1">
          <Link
            href="/"
            className="px-3 py-1.5 rounded-lg transition-colors"
            style={{ color: "#7A6A5A", fontSize: "14px" }}
          >
            My Wikis
          </Link>
          <div
            className="w-7 h-7 rounded-full ml-2 flex items-center justify-center"
            style={{
              backgroundColor: "#8B9E7A",
              color: "white",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            R
          </div>
        </div>
      </div>
    </nav>
  );
}
