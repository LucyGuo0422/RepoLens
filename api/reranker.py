"""
Cross-encoder reranker: re-score retrieved documents against the query.

Uses a lightweight cross-encoder model (ms-marco-MiniLM) that takes
(query, document) pairs as input and produces a relevance score.
Much more accurate than bi-encoder similarity but too slow to run
on the full corpus — only used on the top-k candidates from retrieval.
"""

import threading

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker: CrossEncoder | None = None
_reranker_lock = threading.Lock()


def _get_reranker() -> CrossEncoder:
    """
    Return a cached CrossEncoder instance, loading the model on first call.

    Returns:
        CrossEncoder: The loaded cross-encoder model.
    """
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                print(f"  Loading reranker model '{_MODEL_NAME}'...")
                _reranker = CrossEncoder(_MODEL_NAME)
                print("  Reranker model loaded.")
    return _reranker


def rerank(query: str, docs: list[Document], top_n: int = 10) -> list[Document]:
    """
    Re-score and re-order documents using a cross-encoder model.

    Args:
        query: The search query.
        docs: Candidate documents from retrieval.
        top_n: Number of top documents to return after reranking.

    Returns:
        list[Document]: Top-n documents sorted by cross-encoder score.
    """
    if not docs:
        return []

    model = _get_reranker()
    pairs = [[query, doc.page_content] for doc in docs]
    scores = model.predict(pairs)

    scored = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_n]]
