"""
Research nodes for the deep research graph: plan, update, and conclude.

Three distinct roles:
  plan    — iteration 1: lay out the investigation strategy and extract initial findings
  update  — iterations 2–4: dig a new angle each time, guided by NEXT_SEARCH directives
  conclude — final step: synthesise all accumulated notes into a polished answer
"""
import re
from collections import defaultdict

from langchain_core.messages import HumanMessage

from api.llm import get_llm
from api.prompts import (
    DEEP_RESEARCH_CONCLUDE_PROMPT,
    DEEP_RESEARCH_PLAN_PROMPT,
    DEEP_RESEARCH_UPDATE_PROMPT,
)
from api.state import DeepResearchState

# Keep the combined research notes under ~12 000 chars to avoid Gemini context errors
_MAX_NOTES_CHARS = 12_000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_notes(notes: list[str]) -> str:
    """
    Format accumulated research notes with role-aware labels.

    The first note is labelled ``[Research Plan]``; subsequent notes are
    labelled ``[Update 1]``, ``[Update 2]``, etc.

    Args:
        notes: List of note strings in chronological order.

    Returns:
        str: Formatted multi-section string, or "None yet." if empty.
    """
    if not notes:
        return "None yet."
    parts: list[str] = []
    for i, note in enumerate(notes):
        label = "[Research Plan]" if i == 0 else f"[Update {i}]"
        parts.append(f"{label}\n{note}")
    return "\n\n".join(parts)


def _truncate_notes(notes: list[str], max_chars: int = _MAX_NOTES_CHARS) -> str:
    """
    Format and truncate research notes to stay within the LLM context budget.

    Trims from the oldest notes first so the most recent findings are always
    preserved.

    Args:
        notes: List of per-step note strings.
        max_chars: Maximum total character length for the returned string.

    Returns:
        str: Formatted notes string within the character limit.
    """
    formatted = _format_notes(notes)
    if len(formatted) <= max_chars:
        return formatted
    trimmed = formatted[-max_chars:]
    # Snap to the start of the next complete label block
    cut_idx = re.search(r"\[(Research Plan|Update \d+)\]", trimmed)
    if cut_idx and cut_idx.start() > 0:
        trimmed = trimmed[cut_idx.start():]
    return f"[Earlier notes omitted for length]\n\n{trimmed}"


def _parse_llm_response(raw: str, current_query: str) -> tuple[str, str, bool]:
    """
    Parse the structured directives from a research node LLM response.

    Extracts an optional ``NEXT_SEARCH:`` refined query and detects the
    ``[RESEARCH_COMPLETE]`` early-exit signal, then strips both from the
    note text that will be stored.

    Args:
        raw: Raw LLM response string.
        current_query: The query used for this iteration, returned unchanged
            if no ``NEXT_SEARCH:`` directive is present.

    Returns:
        tuple: (notes_text, next_query, is_done) where notes_text is the
            cleaned note, next_query is the refined or original query, and
            is_done is True when early completion was signalled.
    """
    is_done = "[RESEARCH_COMPLETE]" in raw
    notes_text = raw.replace("[RESEARCH_COMPLETE]", "").strip()

    next_query = current_query
    match = re.search(r"NEXT_SEARCH:\s*(.+)$", notes_text, re.MULTILINE)
    if match:
        next_query = match.group(1).strip()
        notes_text = notes_text[: match.start()].strip()

    return notes_text, next_query, is_done


# ---------------------------------------------------------------------------
# Context formatting (typed for DeepResearchState)
# ---------------------------------------------------------------------------


def format_context_for_research(state: DeepResearchState) -> dict:
    """
    Group retrieved documents by file path into a single context string.

    Identical in behaviour to the standard format_context node but typed
    against DeepResearchState so it can be used in the deep research graph.

    Args:
        state: Current DeepResearchState containing retrieved_docs.

    Returns:
        dict: {"context_text": str} to merge into state.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for doc in state["retrieved_docs"]:
        path = doc.metadata.get("file_path", "unknown")
        groups[path].append(doc.page_content)

    parts: list[str] = []
    for path, chunks in groups.items():
        parts.append(f"### {path}\n" + "\n\n".join(chunks))

    return {"context_text": "\n\n---\n\n".join(parts)}


# ---------------------------------------------------------------------------
# Research nodes
# ---------------------------------------------------------------------------


async def plan_node(
    state: DeepResearchState,
    provider: str = "google",
    model: str | None = None,
) -> dict:
    """
    Iteration 1 — plan the investigation and extract initial findings.

    Analyses the first batch of retrieved documents to identify relevant
    components, sets the direction for subsequent update iterations, and
    emits a ``NEXT_SEARCH:`` directive to guide the next retrieval.

    Args:
        state: Current DeepResearchState with repo_url, query, language,
            and context_text.
        provider: LLM provider to use — "google" or "openrouter".
        model: Specific model ID; falls back to provider default if None.

    Returns:
        dict: Updates to merge into state — answer, research_notes (with plan
            appended), iteration incremented to 2, is_done, and query.
    """
    llm = get_llm(provider, model)

    prompt = DEEP_RESEARCH_PLAN_PROMPT.format(
        repo_url=state["repo_url"],
        language=state["language"],
        query=state["query"],
        context=state["context_text"],
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    notes_text, next_query, is_done = _parse_llm_response(
        response.content, state["query"]
    )

    return {
        "answer": notes_text,
        "research_notes": [notes_text],
        "iteration": 2,
        "is_done": is_done,
        "query": next_query,
    }


async def update_node(
    state: DeepResearchState,
    provider: str = "google",
    model: str | None = None,
) -> dict:
    """
    Iterations 2–4 — dig a new angle and accumulate findings.

    Uses the refined query produced by the previous node to retrieve a fresh
    set of documents, then extracts findings that complement (not duplicate)
    what was already captured.  Can signal early completion via
    ``[RESEARCH_COMPLETE]``.

    Args:
        state: Current DeepResearchState with repo_url, query, language,
            context_text, research_notes, and iteration.
        provider: LLM provider to use — "google" or "openrouter".
        model: Specific model ID; falls back to provider default if None.

    Returns:
        dict: Updates to merge into state — answer, research_notes (with this
            update appended), iteration incremented, is_done, and query.
    """
    llm = get_llm(provider, model)

    # update_num counts updates only (iteration 2 = update 1, etc.)
    update_num = state["iteration"] - 1

    prompt = DEEP_RESEARCH_UPDATE_PROMPT.format(
        repo_url=state["repo_url"],
        language=state["language"],
        query=state["query"],
        update_num=update_num,
        research_notes=_truncate_notes(state["research_notes"]),
        context=state["context_text"],
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    notes_text, next_query, is_done = _parse_llm_response(
        response.content, state["query"]
    )

    new_iteration = state["iteration"] + 1
    # Force conclusion after update 1 (plan + 1 update + conclude = 3 LLM calls total)
    if new_iteration > 2:
        is_done = True

    return {
        "answer": notes_text,
        "research_notes": state["research_notes"] + [notes_text],
        "iteration": new_iteration,
        "is_done": is_done,
        "query": next_query,
    }


async def conclude_node(
    state: DeepResearchState,
    provider: str = "google",
    model: str | None = None,
) -> dict:
    """
    Final step — synthesise all accumulated notes into a polished answer.

    Receives the research plan and all update notes and calls the LLM once
    more to produce a comprehensive, user-facing response.  Notes are
    truncated to ``_MAX_NOTES_CHARS`` to avoid context-window errors.

    Args:
        state: Current DeepResearchState with repo_url, query, language,
            and research_notes.
        provider: LLM provider to use — "google" or "openrouter".
        model: Specific model ID; falls back to provider default if None.

    Returns:
        dict: {"answer": str} — the final synthesized answer.
    """
    llm = get_llm(provider, model)

    prompt = DEEP_RESEARCH_CONCLUDE_PROMPT.format(
        repo_url=state["repo_url"],
        language=state["language"],
        query=state["query"],
        research_notes=_truncate_notes(state["research_notes"]),
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"answer": response.content}
