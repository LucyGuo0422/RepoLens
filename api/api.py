import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.checkpointer import get_checkpointer
from api.graphs.rag_graph import build_rag_graph
from api.data_pipeline import get_repo_context
from api.llm import get_llm
from api.prompts import WIKI_STRUCTURE_PROMPT

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

    llm = get_llm(provider=req.provider, model=req.model)
    response = await llm.ainvoke(prompt)
    raw_xml: str = response.content if hasattr(response, "content") else str(response)

    try:
        structure = _parse_wiki_structure(raw_xml)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"wiki_structure": structure}


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
        """Yield answer tokens from the graph's final state."""
        result = await graph.ainvoke(
            initial_state, config={"configurable": {"thread_id": thread_id}}
        )
        answer: str = result.get("answer", "")
        if not answer:
            raise HTTPException(status_code=500, detail="No answer generated")
        # Stream word-by-word so the client sees progressive output
        for word in answer.split(" "):
            yield word + " "

    return StreamingResponse(token_generator(), media_type="text/plain")
