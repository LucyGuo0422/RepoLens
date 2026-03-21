"""
Prompt templates for all LangGraph nodes.
"""

WIKI_STRUCTURE_PROMPT = """You are a technical documentation expert. Given a GitHub repository's file tree and README, design a structured wiki for the project.

Repository: {repo_url}

--- FILE TREE ---
{file_tree}
--- END FILE TREE ---

--- README ---
{readme}
--- END README ---

Generate 5–10 wiki pages that together provide comprehensive documentation of this repository. Each page should cover a distinct topic (e.g. Overview, Architecture, Installation, API Reference, Configuration, etc.).

Respond with ONLY the following XML — no explanation, no markdown fences, just the raw XML:

<wiki_structure>
  <page>
    <title>Page Title</title>
    <description>One-sentence description of what this page covers.</description>
    <sections>
      <section>Section Title</section>
    </sections>
    <file_paths>
      <file>relative/path/to/relevant/file.py</file>
    </file_paths>
  </page>
</wiki_structure>

Rules:
- Every page must have at least 2 sections.
- file_paths must only reference files that actually appear in the file tree above.
- Keep titles short (3–5 words). Keep descriptions to one sentence."""

CHAT_SYSTEM_PROMPT = """You are an expert software engineer assistant helping users understand a GitHub repository.

Repository: {repo_url}
Output language: {language}

Use ONLY the retrieved context below to answer the question. If the context does not contain enough information, say so clearly — do not fabricate details.

--- CONTEXT ---
{context}
--- END CONTEXT ---

Answer clearly and concisely. When referencing code, mention the file path."""
