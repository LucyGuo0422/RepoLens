"""
Retrieve node: similarity-search the Qdrant vectorstore for the current query.
"""
from api.state import ChatState
from api.vectorstore import load_or_build_vectorstore

_TOP_K = 20


def retrieve(state: ChatState) -> dict:
    """
    Retrieve the top-20 most relevant documents from Qdrant for the current query.

    Args:
        state: Current ChatState containing repo_url and query.

    Returns:
        dict: {"retrieved_docs": List[Document]} to merge into state.
    """
    vs = load_or_build_vectorstore(state["repo_url"])
    docs = vs.similarity_search(state["query"], k=_TOP_K)
    return {"retrieved_docs": docs}
