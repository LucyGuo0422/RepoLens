"""
Retrieve node: hybrid search (dense + BM25) with Reciprocal Rank Fusion.
"""
from langchain_core.documents import Document

from api.bm25_index import bm25_search
from api.state import ChatState
from api.vectorstore import load_or_build_vectorstore

_TOP_K = 20
_RRF_K = 60


def _reciprocal_rank_fusion(
    dense_docs: list[Document],
    sparse_docs: list[Document],
    k: int = _RRF_K,
    top_n: int = _TOP_K,
) -> list[Document]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.

    RRF score for document d = sum(1 / (k + rank_i(d))) across all lists
    where rank_i is the 1-based rank in list i. Documents are identified
    by their page_content for deduplication.

    Args:
        dense_docs: Documents from dense (vector) search, in rank order.
        sparse_docs: Documents from sparse (BM25) search, in rank order.
        k: RRF constant (default 60, standard value from the RRF paper).
        top_n: Number of results to return.

    Returns:
        list[Document]: Top-n documents sorted by fused score.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for rank, doc in enumerate(dense_docs, start=1):
        key = doc.page_content
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        doc_map[key] = doc

    for rank, doc in enumerate(sparse_docs, start=1):
        key = doc.page_content
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        if key not in doc_map:
            doc_map[key] = doc

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys[:top_n]]


def retrieve(state: ChatState) -> dict:
    """
    Retrieve documents using hybrid search (dense + BM25) with RRF fusion.

    Runs dense vector search and BM25 keyword search in parallel,
    then merges the two result lists using Reciprocal Rank Fusion.

    Args:
        state: Current ChatState containing repo_url and query.

    Returns:
        dict: {"retrieved_docs": List[Document]} to merge into state.
    """
    repo_url = state["repo_url"]
    query = state["query"]

    # Dense search (vector similarity)
    vs = load_or_build_vectorstore(repo_url)
    dense_docs = vs.similarity_search(query, k=_TOP_K)

    # Sparse search (BM25 keyword matching)
    sparse_docs = bm25_search(repo_url, query, k=_TOP_K)

    # Fuse with RRF
    merged = _reciprocal_rank_fusion(dense_docs, sparse_docs)

    return {"retrieved_docs": merged}


def retrieve_dense_only(state: ChatState) -> dict:
    """
    Retrieve documents using dense vector search only (no BM25).

    Args:
        state: Current ChatState containing repo_url and query.

    Returns:
        dict: {"retrieved_docs": List[Document]} to merge into state.
    """
    vs = load_or_build_vectorstore(state["repo_url"])
    docs = vs.similarity_search(state["query"], k=_TOP_K)
    return {"retrieved_docs": docs}
