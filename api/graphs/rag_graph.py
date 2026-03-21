"""
RAG chat graph: retrieve → format_context → generate.
"""
from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver  # noqa: F401 — kept for type hint
from langgraph.graph import END, StateGraph

from api.nodes.format_context import format_context
from api.nodes.generate import generate
from api.nodes.retrieve import retrieve
from api.state import ChatState


def build_rag_graph(
    provider: str = "google",
    model: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """
    Build and compile the RAG chat LangGraph.

    The graph runs three nodes in sequence:
      1. retrieve       — similarity-search Qdrant for top-20 docs
      2. format_context — group docs by file path into a context string
      3. generate       — call the LLM and write the answer to state

    Args:
        provider: LLM provider to pass to the generate node.
        model: Specific model ID for the generate node; uses provider default if None.
        checkpointer: Optional LangGraph checkpointer for conversation memory.

    Returns:
        CompiledGraph: A compiled LangGraph ready to invoke or stream.
    """
    generate_node = partial(generate, provider=provider, model=model)

    graph = StateGraph(ChatState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("format_context", format_context)
    graph.add_node("generate", generate_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "format_context")
    graph.add_edge("format_context", "generate")
    graph.add_edge("generate", END)

    return graph.compile(checkpointer=checkpointer)
