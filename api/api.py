import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.checkpointer import get_checkpointer
from api.graphs.rag_graph import build_rag_graph

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
