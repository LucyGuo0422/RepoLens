"""
BM25 keyword index: build and cache a BM25 index per repo from Qdrant payloads.
"""

import threading

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from api.vectorstore import get_collection_name, get_qdrant_client

_bm25_cache: dict[str, tuple] = {}
_bm25_lock = threading.Lock()


def _scroll_all_docs(collection_name: str) -> list:
    """
    Scroll all points from a Qdrant collection.

    Args:
        collection_name: Name of the Qdrant collection.

    Returns:
        list: All point records with payloads.
    """
    client = get_qdrant_client()
    all_points = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=200,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(points)
        if offset is None:
            break
    return all_points


def get_bm25_index(repo_url: str) -> tuple[BM25Okapi, list[Document]]:
    """
    Return a cached BM25 index and document list for the given repo.

    Builds the index on first call by scrolling all documents from Qdrant
    and tokenizing them. Subsequent calls return the cached result.

    Args:
        repo_url: GitHub repository URL.

    Returns:
        tuple: (BM25Okapi index, list of LangChain Documents)
    """
    collection_name = get_collection_name(repo_url)

    if collection_name in _bm25_cache:
        return _bm25_cache[collection_name]

    with _bm25_lock:
        if collection_name in _bm25_cache:
            return _bm25_cache[collection_name]

        print(f"  Building BM25 index for '{collection_name}'...")
        points = _scroll_all_docs(collection_name)

        docs = []
        tokenized_corpus = []
        for p in points:
            content = p.payload.get("page_content", "")
            metadata = p.payload.get("metadata", {})
            if content.strip():
                docs.append(Document(page_content=content, metadata=metadata))
                tokenized_corpus.append(content.lower().split())

        bm25 = BM25Okapi(tokenized_corpus)
        print(f"  BM25 index built: {len(docs)} documents")

        _bm25_cache[collection_name] = (bm25, docs)
        return _bm25_cache[collection_name]


def bm25_search(repo_url: str, query: str, k: int = 20) -> list[Document]:
    """
    Search the BM25 index for a repo and return the top-k documents.

    Args:
        repo_url: GitHub repository URL.
        query: Search query string.
        k: Number of results to return.

    Returns:
        list[Document]: Top-k documents ranked by BM25 score.
    """
    bm25, docs = get_bm25_index(repo_url)
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [docs[i] for i in top_indices]
