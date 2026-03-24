import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def _is_quota_error(exc: Exception) -> bool:
    """Return True if the exception is a Gemini/OpenAI 429 quota-exhaustion error."""
    return "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "quota" in str(exc).lower()

from api.checkpointer import get_checkpointer
from api.data_pipeline import get_repo_context
from api.graphs.deep_research_graph import build_deep_research_graph
from api.graphs.rag_graph import build_rag_graph
from api.graphs.wiki_page_graph import build_wiki_page_graph
from api.llm import get_llm
from api.prompts import WIKI_STRUCTURE_PROMPT
from api.wiki_cache import delete_wiki, get_wiki, list_wikis, save_wiki

CONFIG_DIR = Path(__file__).parent / "config"

app = FastAPI(title="RepoLens API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """
    Check that the API server is running.

    Returns:
        dict: {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/models/config")
def models_config():
    """
    Return the available LLM providers and models from config/generator.json.

    Returns:
        dict: Providers list with their models and temperature settings.
    """
    return json.loads((CONFIG_DIR / "generator.json").read_text())


@app.get("/lang/config")
def lang_config():
    """
    Return the list of supported output languages.

    Returns:
        dict: Languages list with code and display name for each language.
    """
    return {
        "languages": [
            {"code": "English",    "name": "English"},
            {"code": "Chinese",    "name": "中文"},
        ]
    }


class WikiStructureRequest(BaseModel):
    """Request body for the /wiki/structure endpoint."""

    repo_url: str
    language: str = "English"
    provider: str = "google"
    model: str | None = None


def _parse_wiki_structure(xml_text: str) -> dict:
    """
    Parse the LLM's XML response into a WikiStructure dict.

    Expects a <wiki_structure> root element containing <page> children,
    each with <title>, <description>, <sections>, and <file_paths> sub-elements.

    Args:
        xml_text: Raw XML string returned by the LLM.

    Returns:
        dict: {"pages": [{"title": str, "description": str,
                          "sections": [str], "file_paths": [str]}, ...]}

    Raises:
        ValueError: If the XML cannot be parsed or is missing required elements.
    """
    # Strip any accidental leading/trailing whitespace or markdown fences
    xml_text = xml_text.strip()
    if xml_text.startswith("```"):
        lines = xml_text.splitlines()
        xml_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    # Escape bare & that the LLM forgot to write as &amp;
    # Matches & not already followed by a valid XML entity reference
    xml_text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", xml_text)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"LLM returned invalid XML: {exc}\n\nRaw output:\n{xml_text}") from exc

    pages = []
    for page_el in root.findall("page"):
        title = (page_el.findtext("title") or "").strip()
        description = (page_el.findtext("description") or "").strip()

        sections: List[str] = [
            s.text.strip()
            for s in (page_el.find("sections") or [])
            if s.text and s.text.strip()
        ]
        file_paths: List[str] = [
            f.text.strip()
            for f in (page_el.find("file_paths") or [])
            if f.text and f.text.strip()
        ]

        pages.append({
            "title": title,
            "description": description,
            "sections": sections,
            "file_paths": file_paths,
        })

    return {"pages": pages}


@app.post("/wiki/structure")
async def wiki_structure(req: WikiStructureRequest):
    """
    Generate a structured wiki page plan for a GitHub repository.

    Clones the repository to extract its file tree and README, then calls
    the LLM directly (no graph, no streaming) with a structured prompt.
    The LLM returns XML which is parsed into a list of wiki pages.

    Args:
        req: WikiStructureRequest with repo_url, language, provider, and model.

    Returns:
        dict: {"wiki_structure": {"pages": [...]}} where each page has
            title, description, sections (list of str), and file_paths (list of str).

    Raises:
        HTTPException: 400 if the repo cannot be cloned; 500 if LLM output
            cannot be parsed as valid XML.
    """
    try:
        file_tree, readme = get_repo_context(req.repo_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to clone repository: {exc}") from exc

    # Escape literal braces in user-supplied content so .format() doesn't
    # mistake them for template placeholders (common in READMEs and file trees)
    prompt = WIKI_STRUCTURE_PROMPT.format(
        repo_url=req.repo_url,
        file_tree=file_tree.replace("{", "{{").replace("}", "}}"),
        readme=readme.replace("{", "{{").replace("}", "}}"),
    )

    model_label = f"{req.provider}/{req.model or 'default'}"
    llm = get_llm(provider=req.provider, model=req.model)
    try:
        response = await llm.ainvoke(prompt)
    except Exception as exc:
        if _is_quota_error(exc):
            raise HTTPException(status_code=429, detail="LLM quota exhausted — wait a minute or switch to OpenRouter.") from exc
        raise HTTPException(status_code=500, detail=f"LLM error ({model_label}): {exc}") from exc
    raw_xml: str = response.content if hasattr(response, "content") else str(response)

    try:
        structure = _parse_wiki_structure(raw_xml)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"wiki_structure": structure}


class WikiPageRequest(BaseModel):
    """Request body for the /wiki/generate-page endpoint."""

    repo_url: str
    page_title: str
    file_paths: List[str] = []
    language: str = "English"
    provider: str = "google"
    model: str | None = None


@app.post("/wiki/generate-page")
async def wiki_generate_page(req: WikiPageRequest):
    """
    Generate markdown content for one wiki page and stream it token by token.

    Runs the wiki page graph (retrieve → format_context → generate_page) using
    the page title as the retrieval query, then streams the resulting markdown
    via a plain-text StreamingResponse.

    Args:
        req: WikiPageRequest with repo_url, page_title, file_paths, language,
            provider, and model.

    Returns:
        StreamingResponse: text/plain stream of markdown tokens.

    Raises:
        HTTPException: 500 if the graph fails to produce content.
    """
    graph = build_wiki_page_graph(provider=req.provider, model=req.model)

    initial_state = {
        "repo_url": req.repo_url,
        "language": req.language,
        "page_title": req.page_title,
        "file_paths": req.file_paths,
        "retrieved_docs": [],
        "context_text": "",
        "page_content": "",
    }

    async def token_generator() -> AsyncGenerator[str, None]:
        """Yield LLM tokens in real time via astream_events."""
        has_content = False
        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token:
                        has_content = True
                        yield token
        except Exception as exc:
            if _is_quota_error(exc):
                yield "\n\n**Error:** LLM quota exhausted — wait a minute or switch to OpenRouter in settings."
                return
            raise
        if not has_content:
            yield "\n\n**Error:** No content generated."

    return StreamingResponse(token_generator(), media_type="text/plain")


# ---------------------------------------------------------------------------
# Wiki cache endpoints
# ---------------------------------------------------------------------------


@app.get("/wiki/cache")
def wiki_cache_get(owner: str, repo: str, language: str = "English"):
    """
    Fetch a cached wiki for the given owner/repo/language.

    Args:
        owner: GitHub repository owner (query param).
        repo: GitHub repository name (query param).
        language: Output language code (query param, default "English").

    Returns:
        dict: Cached wiki with keys ``owner``, ``repo``, ``language``,
            ``wiki_structure``, ``pages``, ``created_at``, ``updated_at``.

    Raises:
        HTTPException: 404 if no cache entry exists for the given key.
    """
    entry = get_wiki(owner, repo, language)
    if entry is None:
        raise HTTPException(status_code=404, detail="No cached wiki found")
    return entry


class WikiCacheSaveRequest(BaseModel):
    """Request body for POST /wiki/cache."""

    owner: str
    repo: str
    language: str = "English"
    wiki_structure: dict
    pages: dict


@app.post("/wiki/cache")
def wiki_cache_save(req: WikiCacheSaveRequest):
    """
    Save (or overwrite) a completed wiki in the cache.

    Args:
        req: WikiCacheSaveRequest with owner, repo, language, wiki_structure, and pages.

    Returns:
        dict: The saved cache entry.
    """
    return save_wiki(
        owner=req.owner,
        repo=req.repo,
        language=req.language,
        wiki_structure=req.wiki_structure,
        pages=req.pages,
    )


@app.delete("/wiki/cache")
def wiki_cache_delete(owner: str, repo: str, language: str | None = None):
    """
    Delete cached wiki entries for an owner/repo, optionally for one language only.

    Args:
        owner: GitHub repository owner (query param).
        repo: GitHub repository name (query param).
        language: If provided, only that language variant is deleted;
            if omitted, all language variants are deleted.

    Returns:
        dict: {"deleted": <number of rows removed>}
    """
    count = delete_wiki(owner, repo, language)
    return {"deleted": count}


@app.get("/api/processed_projects")
def processed_projects():
    """
    List all repositories that have a cached wiki.

    Returns:
        dict: {"projects": [{"owner", "repo", "language", "page_count",
                             "created_at", "updated_at"}, ...]}
    """
    return {"projects": list_wikis()}


def _build_sources_payload(docs) -> list[dict]:
    """
    Convert retrieved LangChain Documents into a JSON-serializable sources list.

    Groups documents by file_path and includes truncated chunk content so the
    frontend can display related code snippets alongside the answer.

    Args:
        docs: List of LangChain Document objects with metadata.

    Returns:
        list[dict]: Each dict has ``file_path`` and ``chunks`` (list of
            ``content``, ``is_code``, ``chunk_index``).
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for doc in docs:
        path = doc.metadata.get("file_path", "unknown")
        groups[path].append({
            "chunk_index": doc.metadata.get("chunk_index", 0),
            "content": doc.page_content[:500],
            "is_code": doc.metadata.get("is_code", False),
        })
    return [
        {
            "file_path": path,
            "chunks": sorted(chunks, key=lambda c: c["chunk_index"]),
        }
        for path, chunks in groups.items()
    ]


class ChatRequest(BaseModel):
    """Request body for the /chat/stream endpoint."""

    repo_url: str
    query: str
    provider: str = "google"
    model: str | None = None
    language: str = "English"
    session_id: str = "default"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Run the RAG chat graph and stream the LLM answer token by token.

    Builds (or loads) the Qdrant vectorstore for the given repo, runs the
    retrieve → format_context → generate graph, and streams the generated
    answer via a plain-text StreamingResponse.

    Args:
        req: ChatRequest with repo_url, query, provider, model, language, and session_id.

    Returns:
        StreamingResponse: text/plain stream of answer tokens.

    Raises:
        HTTPException: 500 if the graph fails to produce an answer.
    """
    # thread_id scopes conversation memory per repo + session
    owner_repo = req.repo_url.rstrip("/").split("github.com/")[-1].replace("/", "__")
    thread_id = f"{owner_repo}__{req.session_id}"

    checkpointer = await get_checkpointer()
    graph = build_rag_graph(
        provider=req.provider, model=req.model, checkpointer=checkpointer
    )

    initial_state = {
        "repo_url": req.repo_url,
        "query": req.query,
        "language": req.language,
        "messages": [],
        "retrieved_docs": [],
        "context_text": "",
        "answer": "",
    }

    async def token_generator() -> AsyncGenerator[str, None]:
        """Yield sources JSON prefix, then LLM tokens in real time."""
        has_content = False
        sources_sent = False
        try:
            async for event in graph.astream_events(
                initial_state,
                config={"configurable": {"thread_id": thread_id}},
                version="v2",
            ):
                # Emit sources once, right after the retrieve node finishes
                if (
                    not sources_sent
                    and event["event"] == "on_chain_end"
                    and event.get("name") == "retrieve"
                ):
                    docs = event.get("data", {}).get("output", {}).get("retrieved_docs", [])
                    payload = _build_sources_payload(docs)
                    yield json.dumps({"sources": payload}) + "\n___SOURCES_END___\n"
                    sources_sent = True

                if event["event"] == "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token:
                        has_content = True
                        yield token
        except Exception as exc:
            if _is_quota_error(exc):
                if not sources_sent:
                    yield json.dumps({"sources": []}) + "\n___SOURCES_END___\n"
                yield "\n\n**Error:** LLM quota exhausted — wait a minute or switch to OpenRouter in settings."
                return
            raise
        if not has_content:
            if not sources_sent:
                yield json.dumps({"sources": []}) + "\n___SOURCES_END___\n"
            yield "\n\n**Error:** No answer generated."

    return StreamingResponse(token_generator(), media_type="text/plain")


class DeepResearchRequest(BaseModel):
    """Request body for the /chat/deep-research endpoint."""

    repo_url: str
    query: str
    provider: str = "google"
    model: str | None = None
    language: str = "English"


@app.post("/chat/deep-research")
async def chat_deep_research(req: DeepResearchRequest):
    """
    Run the deep research graph and stream all iterations plus the final answer.

    Runs up to 5 retrieve → research iterations, emitting a brief progress
    marker after each plan/update node completes, then streams the final
    synthesised answer from the conclude node.

    Args:
        req: DeepResearchRequest with repo_url, query, provider, model, and language.

    Returns:
        StreamingResponse: text/plain stream of all iteration tokens and the
            final answer, with ``## Iteration N`` and ``## Final Answer``
            headers separating each phase.

    Raises:
        HTTPException: 500 if the graph fails to produce any output.
    """
    graph = build_deep_research_graph(provider=req.provider, model=req.model)

    initial_state = {
        "repo_url": req.repo_url,
        "query": req.query,
        "language": req.language,
        "messages": [],
        "retrieved_docs": [],
        "context_text": "",
        "answer": "",
        "iteration": 1,
        "research_notes": [],
        "is_done": False,
    }

    async def token_generator() -> AsyncGenerator[str, None]:
        """Stream sources early, then progress markers and final answer tokens."""
        has_content = False
        sources_emitted = False
        all_docs: list = []
        iteration_num = 0
        in_conclude = False

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                # Accumulate retrieved docs from every retrieve iteration
                if (
                    event["event"] == "on_chain_end"
                    and event.get("name") == "retrieve"
                ):
                    docs = event.get("data", {}).get("output", {}).get("retrieved_docs", [])
                    all_docs.extend(docs)

                    # Emit sources + delimiter after the first retrieve so the
                    # frontend immediately starts showing streamed content.
                    if not sources_emitted:
                        sources_emitted = True
                        payload = _build_sources_payload(docs)
                        yield json.dumps({"sources": payload}) + "\n___SOURCES_END___\n"

                # Emit a brief progress marker after each plan/update completes
                if event["event"] == "on_chain_end" and event.get("name") in ("plan", "update"):
                    iteration_num += 1
                    yield f"*Analyzing codebase — iteration {iteration_num} complete…*\n\n"
                    has_content = True

                # Track when conclude starts so we can stream its tokens
                if event["event"] == "on_chain_start" and event.get("name") == "conclude":
                    in_conclude = True

                # Stream conclude's LLM tokens in real time
                if in_conclude and event["event"] == "on_chat_model_stream":
                    token = event["data"]["chunk"].content
                    if token:
                        has_content = True
                        yield token

        except Exception as exc:
            if _is_quota_error(exc):
                if not sources_emitted:
                    yield json.dumps({"sources": []}) + "\n___SOURCES_END___\n"
                yield "\n\n**Error:** LLM quota exhausted — wait a minute or switch to OpenRouter in settings."
                return
            raise

        if not has_content:
            if not sources_emitted:
                yield json.dumps({"sources": []}) + "\n___SOURCES_END___\n"
            yield "\n\n**Error:** No content generated."

    return StreamingResponse(token_generator(), media_type="text/plain")
