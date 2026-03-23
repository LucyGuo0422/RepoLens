"""
Generate node: call the LLM with context and write the answer to state.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from api.llm import get_llm
from api.prompts import CHAT_SYSTEM_PROMPT
from api.state import ChatState


async def generate(state: ChatState, provider: str = "google", model: str | None = None) -> dict:
    """
    Call the LLM to answer the user query using the formatted context.

    Args:
        state: Current ChatState with query, context_text, repo_url, and language.
        provider: LLM provider to use — "google" or "openrouter".
        model: Specific model ID; falls back to provider default if None.

    Returns:
        dict: {"answer": str, "messages": [HumanMessage, AIMessage]} to merge into state.
    """
    llm = get_llm(provider, model)

    system_content = CHAT_SYSTEM_PROMPT.format(
        repo_url=state["repo_url"],
        language=state["language"],
        context=state["context_text"],
    )

    response = await llm.ainvoke([
        SystemMessage(content=system_content),
        HumanMessage(content=state["query"]),
    ])

    return {
        "answer": response.content,
        "messages": [
            HumanMessage(content=state["query"]),
            response,
        ],
    }
