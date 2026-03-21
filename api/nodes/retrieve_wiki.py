"""
Retrieve node for wiki page generation: semantic search + file-path pinning.
"""
from langchain_core.documents import Document
from qdrant_client.models import FieldCondition, Filter, MatchValue

from api.state import WikiPageState
from api.vectorstore import get_collection_name, get_qdrant_client, load_or_build_vectorstore

_TOP_K = 20
_MAX_CHUNKS_PER_FILE = 50  # guard against huge files flooding the context


def retrieve_wiki(state: WikiPageState) -> dict:
    """
    Retrieve documents for a wiki page using two complementary strategies.

    1. Semantic search — similarity_search(page_title, k=20) finds broadly
       relevant chunks even if they aren't in the explicitly listed files.
    2. File-path pinning — scroll Qdrant with a metadata filter to guarantee
       every chunk from the planned file_paths is included, regardless of
       whether it ranked in the top-20 by similarity.

    Results are merged and deduplicated by (file_path, chunk_index).
    Pinned file docs are prepended so they appear first in the context.

    Args:
        state: Current WikiPageState containing repo_url, page_title, and file_paths.

    Returns:
        dict: {"retrieved_docs": List[Document]} to merge into state.
    """
    vs = load_or_build_vectorstore(state["repo_url"])

    # 1. Semantic search on page title
    semantic_docs = vs.similarity_search(state["page_title"], k=_TOP_K)

    # 2. Pinned file-path docs via Qdrant metadata filter
    pinned_docs: list[Document] = []
    file_paths: list[str] = state.get("file_paths") or []
    if file_paths:
        client = get_qdrant_client()
        collection = get_collection_name(state["repo_url"])
        for file_path in file_paths:
            points, _ = client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[FieldCondition(
                        key="metadata.file_path",
                        match=MatchValue(value=file_path),
                    )]
                ),
                with_payload=True,
                with_vectors=False,
                limit=_MAX_CHUNKS_PER_FILE,
            )
            for point in points:
                payload = point.payload or {}
                pinned_docs.append(Document(
                    page_content=payload.get("page_content", ""),
                    metadata=payload.get("metadata", {}),
                ))

    # 3. Merge: pinned first, then semantic; dedup by (file_path, chunk_index)
    seen: set[tuple] = set()
    merged: list[Document] = []
    for doc in pinned_docs + semantic_docs:
        key = (
            doc.metadata.get("file_path", ""),
            doc.metadata.get("chunk_index", doc.page_content[:80]),
        )
        if key not in seen:
            seen.add(key)
            merged.append(doc)

    return {"retrieved_docs": merged}
