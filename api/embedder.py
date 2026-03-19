import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

_CONFIG_PATH = Path(__file__).parent / "config" / "embedder.json"
_config = json.loads(_CONFIG_PATH.read_text())

DEFAULT_PROVIDER: str = _config["provider"]
PROVIDERS: dict = _config["providers"]


def get_embedding_dim(provider: str = DEFAULT_PROVIDER) -> int:
    """
    Return the vector dimension for the given embedding provider.

    Args:
        provider: Embedding provider name — "google" or "openai".

    Returns:
        int: Number of dimensions produced by the provider's embedding model.

    Raises:
        ValueError: If provider is not found in embedder.json.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported embedding provider: {provider}")
    return PROVIDERS[provider]["dim"]


def get_embedder(provider: str = DEFAULT_PROVIDER) -> GoogleGenerativeAIEmbeddings | OpenAIEmbeddings:
    """
    Return a LangChain embeddings model for the given provider.

    Provider and model are read from api/config/embedder.json.

    Args:
        provider: Embedding provider — "google" (gemini-embedding-001) or
                  "openai" (text-embedding-3-small). Defaults to the value
                  set in embedder.json.

    Returns:
        GoogleGenerativeAIEmbeddings | OpenAIEmbeddings: Configured embeddings model.

    Raises:
        ValueError: If provider is not "google" or "openai".
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported embedding provider: {provider}")

    model = PROVIDERS[provider]["model"]

    if provider == "google":
        return GoogleGenerativeAIEmbeddings(
            model=model,
            google_api_key=GOOGLE_API_KEY,
        )
    elif provider == "openai":
        return OpenAIEmbeddings(
            model=model,
            openai_api_key=OPENAI_API_KEY,
            dimensions=PROVIDERS[provider]["dim"],
        )
