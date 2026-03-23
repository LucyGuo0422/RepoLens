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

WIKI_PAGE_PROMPT = """You are a technical documentation expert writing a wiki page for a GitHub repository.

Repository: {repo_url}
Output language: {language}
Page title: {page_title}

Use ONLY the retrieved context below. Do not fabricate details not found in the context.

--- CONTEXT ---
{context}
--- END CONTEXT ---

Write a comprehensive wiki page in Markdown for "{page_title}". Rules:
- Start directly with the page content — no front matter, no YAML, no title heading (the UI adds the title).
- Use ## for section headings, ### for subsections.
- Include fenced code blocks with language tags when showing code snippets.
- Add a Mermaid diagram (```mermaid) where it genuinely helps explain architecture, data flow, or relationships. Skip it if the page doesn't benefit from one.
- After each paragraph or code block that draws from a specific file, add a citation: *(source: `path/to/file.py`)*
- Write in {language}."""

CHAT_SYSTEM_PROMPT = """You are an expert software engineer assistant helping users understand a GitHub repository.

Repository: {repo_url}
Output language: {language}

Use ONLY the retrieved context below to answer the question. If the context does not contain enough information, say so clearly — do not fabricate details.

--- CONTEXT ---
{context}
--- END CONTEXT ---

Answer clearly and concisely. When referencing code, mention the file path."""

DEEP_RESEARCH_PLAN_PROMPT = """You are starting a deep research session to analyze a GitHub repository.

Repository: {repo_url}
Output language: {language}
Research Question: {query}

--- RETRIEVED CONTEXT ---
{context}
--- END CONTEXT ---

This is the PLANNING phase. Your tasks:
1. Identify the key files, components, and concepts in the context that are relevant to the question.
2. Extract concrete initial findings — mention file paths, function names, class names.
3. Outline what specific topics or code paths still need investigation.

After your notes, on its own line, write:
`NEXT_SEARCH: <targeted query for the next investigation angle>`

Write your research plan and initial findings:"""

DEEP_RESEARCH_UPDATE_PROMPT = """You are continuing a deep research session on a GitHub repository.

Repository: {repo_url}
Output language: {language}
Research Question: {query}
Update: {update_num} of 3

--- RESEARCH PLAN & PREVIOUS FINDINGS ---
{research_notes}
--- END PREVIOUS NOTES ---

--- NEW CONTEXT (freshly retrieved for this update) ---
{context}
--- END CONTEXT ---

Extract NEW findings from the current context that have NOT been captured in previous notes. Focus on a different angle or deeper detail than what was already found. Be specific: file paths, function names, data flows.

After your notes, on its own line, write ONE of:
- `NEXT_SEARCH: <refined query for the next angle>` — if more investigation is needed
- `[RESEARCH_COMPLETE]` — if you already have enough to fully answer the question

Write your findings for update {update_num}:"""

DEEP_RESEARCH_CONCLUDE_PROMPT = """You are a deep research assistant synthesizing a multi-step analysis of a GitHub repository.

Repository: {repo_url}
Output language: {language}
Research Question: {query}

--- ACCUMULATED RESEARCH NOTES ---
{research_notes}
--- END NOTES ---

Synthesize these notes into a comprehensive, well-structured answer to the research question.

Rules:
- Write in {language}
- Use ## headings to organize sections, ### for subsections
- Reference specific files, functions, and classes from the notes
- Include fenced code blocks with language tags when showing code
- Be comprehensive but avoid repetition
- Do NOT mention "research plan", "updates", or the research process — present findings naturally as expert analysis

Write the final answer:"""
