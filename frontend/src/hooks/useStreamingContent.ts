"use client";

import { useState, useCallback } from "react";

export function useStreamingContent() {
  const [content, setContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stream = useCallback(
    async (url: string, body: object): Promise<string> => {
      setContent("");
      setError(null);
      setIsStreaming(true);

      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let full = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          full += chunk;
          setContent(full);
        }

        setIsStreaming(false);
        return full;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Streaming failed";
        setError(msg);
        setIsStreaming(false);
        throw err;
      }
    },
    []
  );

  return { content, isStreaming, error, stream, setContent };
}

export async function fetchStream(
  url: string,
  body: object,
  onChunk: (accumulated: string) => void
): Promise<string> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let full = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    full += chunk;
    onChunk(full);
  }

  return full;
}

export interface SourceFile {
  file_path: string;
  chunks: { chunk_index: number; content: string; is_code: boolean }[];
}

const SOURCES_DELIMITER = "\n___SOURCES_END___\n";

export async function fetchStreamWithSources(
  url: string,
  body: object,
  onChunk: (accumulated: string) => void,
  onSources: (sources: SourceFile[]) => void
): Promise<string> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let sourcesParsed = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    if (!sourcesParsed) {
      const delimIdx = buffer.indexOf(SOURCES_DELIMITER);
      if (delimIdx !== -1) {
        const sourcesJson = buffer.slice(0, delimIdx);
        try {
          const parsed = JSON.parse(sourcesJson);
          onSources(parsed.sources ?? []);
        } catch {
          // If parsing fails, treat everything as answer text
        }
        sourcesParsed = true;
        answer = buffer.slice(delimIdx + SOURCES_DELIMITER.length);
        onChunk(answer);
      }
    } else {
      answer = buffer.slice(
        buffer.indexOf(SOURCES_DELIMITER) + SOURCES_DELIMITER.length
      );
      onChunk(answer);
    }
  }

  // Fallback: if delimiter never appeared, treat entire buffer as answer
  if (!sourcesParsed) {
    answer = buffer;
    onChunk(answer);
  }

  return answer;
}
