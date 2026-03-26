"""
Deep research graph: retrieve → format_context → plan/update → conclude.

Three LLM calls total:
  1. retrieve + format_context + plan    — iteration 1: strategy & initial findings
  2. retrieve + format_context + update  — iteration 2: new angle (forced conclude after)
  3. conclude                            — synthesise all notes into final answer
"""
from functools import partial

from langgraph.graph import END, StateGraph

from api.nodes.research_nodes import (
    conclude_node,
    format_context_for_research,
    plan_node,
    update_node,
)
from api.state import DeepResearchState
from api.vectorstore import load_or_build_vectorstore

_TOP_K = 20


def _retrieve(state: DeepResearchState) -> dict:
    """
    Retrieve the top-20 most relevant documents from Qdrant for the current query.

    Uses ``state["query"]`` which is refined by each research node so every
    loop iteration fetches documents from a different angle.

    Args:
        state: Current DeepResearchState containing repo_url and query.

    Returns:
        dict: {"retrieved_docs": List[Document]} to merge into state.
    """
    vs = load_or_build_vectorstore(state["repo_url"])
    docs = vs.similarity_search(state["query"], k=_TOP_K)
    return {"retrieved_docs": docs}


def _route_research(state: DeepResearchState) -> str:
    """
    Route after format_context: send iteration 1 to plan, all others to update.

    Args:
        state: Current DeepResearchState with iteration field.

    Returns:
        str: "plan" on the first iteration, "update" on subsequent ones.
    """
    return "plan" if state["iteration"] == 1 else "update"


def _should_conclude(state: DeepResearchState) -> str:
    """
    Decide whether to run another update iteration or move to conclusion.

    Concludes when the LLM signals early completion (is_done) or after
    the single update iteration (iteration > 2).

    Args:
        state: Current DeepResearchState with is_done and iteration fields.

    Returns:
        str: "conclude" if research is complete, "retrieve" to loop again.
    """
    if state["is_done"]:
        return "conclude"
    return "retrieve"


def build_deep_research_graph(
    provider: str = "google",
    model: str | None = None,
):
    """
    Build and compile the deep research LangGraph.

    Graph layout (three LLM calls total):
      retrieve → format_context → [route] → plan   (iteration 1)
                                          → update  (iteration 2, then forced conclude)
      plan   → [check] → conclude | retrieve
      update → [check] → conclude | retrieve
      conclude → END

    Args:
        provider: LLM provider to pass to all research nodes.
        model: Specific model ID; uses provider default if None.

    Returns:
        CompiledGraph: A compiled LangGraph ready to invoke or stream.
    """
    plan = partial(plan_node, provider=provider, model=model)
    update = partial(update_node, provider=provider, model=model)
    conclude = partial(conclude_node, provider=provider, model=model)

    graph = StateGraph(DeepResearchState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("format_context", format_context_for_research)
    graph.add_node("plan", plan)
    graph.add_node("update", update)
    graph.add_node("conclude", conclude)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "format_context")
    graph.add_conditional_edges("format_context", _route_research, {
        "plan": "plan",
        "update": "update",
    })
    graph.add_conditional_edges("plan", _should_conclude, {
        "retrieve": "retrieve",
        "conclude": "conclude",
    })
    graph.add_conditional_edges("update", _should_conclude, {
        "retrieve": "retrieve",
        "conclude": "conclude",
    })
    graph.add_edge("conclude", END)

    return graph.compile()
