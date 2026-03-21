"""
Generate-page node: call the LLM to produce a markdown wiki page.
"""
from api.llm import get_llm
from api.prompts import WIKI_PAGE_PROMPT
from api.state import WikiPageState


async def generate_page(
    state: WikiPageState,
    provider: str = "google",
    model: str | None = None,
) -> dict:
    """
    Call the LLM asynchronously to generate markdown content for one wiki page.

    Using ainvoke instead of invoke lets multiple wiki pages be generated in
    parallel when the frontend fires concurrent requests — no thread pool needed.

    Args:
        state: Current WikiPageState with repo_url, language, page_title, and context_text.
        provider: LLM provider to use — "google" or "openrouter".
        model: Specific model ID; falls back to provider default if None.

    Returns:
        dict: {"page_content": str} to merge into state.
    """
    llm = get_llm(provider, model)

    # Escape braces in context so .format() doesn't misinterpret them
    prompt = WIKI_PAGE_PROMPT.format(
        repo_url=state["repo_url"],
        language=state["language"],
        page_title=state["page_title"],
        context=state["context_text"].replace("{", "{{").replace("}", "}}"),
    )

    response = await llm.ainvoke(prompt)
    return {"page_content": response.content}
