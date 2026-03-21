"""
Format-context node: group retrieved documents by file path into a context string.
"""
from collections import defaultdict

from api.state import ChatState


def format_context(state: ChatState) -> dict:
    """
    Group retrieved documents by file path and format them into a single context string.

    Documents sharing the same file_path are concatenated together under one
    header so the LLM sees coherent per-file blocks rather than scattered chunks.

    Args:
        state: Current ChatState containing retrieved_docs.

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
