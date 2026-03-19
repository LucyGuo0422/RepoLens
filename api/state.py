from typing import TypedDict, List, Annotated
from langchain_core.documents import Document
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    """
    LangGraph state for the RAG chat graph.

    Args:
        repo_url: GitHub repository URL being queried.
        query: Current user question.
        language: Output language (e.g. "English", "Chinese").
        messages: Full conversation history; auto-appended by add_messages.
        retrieved_docs: Documents returned by the Qdrant retriever.
        context_text: Retrieved docs formatted into a single context string.
        answer: LLM-generated answer to the query.
    """
    repo_url: str
    query: str
    language: str
    messages: Annotated[list, add_messages]
    retrieved_docs: List[Document]
    context_text: str
    answer: str


class DeepResearchState(TypedDict):
    """
    LangGraph state for the 5-iteration deep research graph.

    Args:
        repo_url: GitHub repository URL being researched.
        query: Original user question driving the research.
        language: Output language (e.g. "English", "Chinese").
        messages: Full conversation history; auto-appended by add_messages.
        retrieved_docs: Documents returned by the Qdrant retriever.
        context_text: Retrieved docs formatted into a single context string.
        answer: Latest LLM output for the current iteration.
        iteration: Current iteration number (1-5).
        research_notes: Accumulated findings from all completed iterations.
        is_done: True when the LLM signals research is complete before iteration 5.
    """
    repo_url: str
    query: str
    language: str
    messages: Annotated[list, add_messages]
    retrieved_docs: List[Document]
    context_text: str
    answer: str
    iteration: int
    research_notes: List[str]
    is_done: bool


class WikiPageState(TypedDict):
    """
    LangGraph state for the wiki page generation graph.

    Args:
        repo_url: GitHub repository URL the wiki is being generated for.
        language: Output language (e.g. "English", "Chinese").
        page_title: Title of the wiki page being generated.
        file_paths: Relevant source files for this page, from the wiki structure plan.
        retrieved_docs: Documents returned by the Qdrant retriever.
        context_text: Retrieved docs formatted into a single context string.
        page_content: Generated markdown content for the wiki page.
    """
    repo_url: str
    language: str
    page_title: str
    file_paths: List[str]
    retrieved_docs: List[Document]
    context_text: str
    page_content: str
