"""
Wiki page graph: retrieve → format_context → generate_page.
"""
from functools import partial

from langgraph.graph import END, StateGraph

from api.nodes.format_context import format_context
from api.nodes.generate_page import generate_page
from api.nodes.retrieve_wiki import retrieve_wiki
from api.state import WikiPageState


def build_wiki_page_graph(
    provider: str = "google",
    model: str | None = None,
):
    """
    Build and compile the wiki page generation LangGraph.

    The graph runs three nodes in sequence:
      1. retrieve       — similarity-search Qdrant using the page title
      2. format_context — group docs by file path into a context string
      3. generate_page  — call the LLM and write markdown to state

    Args:
        provider: LLM provider to pass to the generate_page node.
        model: Specific model ID; uses provider default if None.

    Returns:
        CompiledGraph: A compiled LangGraph ready to invoke.
    """
    generate_page_node = partial(generate_page, provider=provider, model=model)

    graph = StateGraph(WikiPageState)
    graph.add_node("retrieve", retrieve_wiki)
    graph.add_node("format_context", format_context)
    graph.add_node("generate_page", generate_page_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "format_context")
    graph.add_edge("format_context", "generate_page")
    graph.add_edge("generate_page", END)

    return graph.compile()
