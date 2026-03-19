import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
