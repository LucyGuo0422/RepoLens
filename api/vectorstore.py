"""
Qdrant vectorstore helpers: build or load a per-repo collection.
"""
import os
import threading
import time
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from api.data_pipeline import load_repo_documents
from api.embedder import DEFAULT_PROVIDER, get_embedder, get_embedding_dim

# Embed this many documents per API call.
_EMBED_BATCH_SIZE = 20
# Google free tier: 5 RPM → need ≥12s between batches. OpenAI has no meaningful delay needed.
_BATCH_DELAY: dict[str, float] = {
    "google": 13.0,
    "openai": 0.5,
}

load_dotenv()

QDRANT_PATH = os.path.expanduser("~/.repolens/qdrant")
_qdrant_client: QdrantClient | None = None
_qdrant_lock = threading.Lock()


def get_collection_name(repo_url: str) -> str:
    """
    Derive a Qdrant collection name from a GitHub repository URL.

    For example, "https://github.com/anthropics/anthropic-sdk-python"
    becomes "github__anthropics__anthropic-sdk-python".

    Args:
        repo_url: HTTPS URL of the GitHub repository.

    Returns:
        str: Safe collection name suitable for Qdrant.
    """
    parsed = urlparse(repo_url.rstrip("/"))
    # parsed.path is e.g. "/anthropics/anthropic-sdk-python"
    parts = parsed.path.strip("/").split("/")
    owner = parts[0] if len(parts) > 0 else "unknown"
    repo = parts[1] if len(parts) > 1 else "unknown"
    # Strip optional .git suffix
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"github__{owner}__{repo}"


def get_qdrant_client() -> QdrantClient:
    """
    Return a shared QdrantClient for the local on-disk store.

    The local Qdrant file backend only supports one open client at a time,
    so this function returns a module-level singleton to prevent lock conflicts.
    A threading lock with double-checked locking ensures only one thread ever
    creates the client, which is important for the deep research graph where
    the retrieve node is invoked repeatedly from a thread pool.

    Returns:
        QdrantClient: Singleton client configured to use ~/.repolens/qdrant/.
    """
    global _qdrant_client
    if _qdrant_client is None:
        with _qdrant_lock:
            if _qdrant_client is None:
                Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
                _qdrant_client = QdrantClient(path=QDRANT_PATH)
    return _qdrant_client


def _add_documents_with_retry(
    vs: QdrantVectorStore,
    docs: List[Document],
    provider: str = DEFAULT_PROVIDER,
    max_retries: int = 5,
) -> None:
    """
    Add documents to a QdrantVectorStore in small batches with exponential backoff.

    Batching limits embedding API calls per second; backoff handles 429 responses.

    Args:
        vs: The QdrantVectorStore to insert documents into.
        docs: List of documents to embed and store.
        provider: Embedding provider name, used to select the appropriate batch delay.
        max_retries: Maximum retry attempts per batch on rate-limit errors.
    """
    batch_delay = _BATCH_DELAY.get(provider, 0.5)
    total = len(docs)
    for start in range(0, total, _EMBED_BATCH_SIZE):
        batch = docs[start: start + _EMBED_BATCH_SIZE]
        batch_num = start // _EMBED_BATCH_SIZE + 1
        total_batches = (total + _EMBED_BATCH_SIZE - 1) // _EMBED_BATCH_SIZE
        print(f"  Embedding batch {batch_num}/{total_batches} ({len(batch)} docs)...")

        for attempt in range(max_retries):
            try:
                vs.add_documents(batch)
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait = batch_delay * (2 ** attempt)
                    print(f"  Rate limited — waiting {wait:.0f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError(f"Failed to embed batch {batch_num} after {max_retries} retries")

        if start + _EMBED_BATCH_SIZE < total:
            time.sleep(batch_delay)


def load_or_build_vectorstore(repo_url: str) -> QdrantVectorStore:
    """
    Return a QdrantVectorStore for the given repo, building it if necessary.

    If the Qdrant collection already contains vectors it is loaded directly;
    otherwise the repo is cloned, chunked, embedded, and stored first.

    Args:
        repo_url: HTTPS URL of a public GitHub repository.

    Returns:
        QdrantVectorStore: Ready-to-query LangChain vectorstore.
    """
    collection_name = get_collection_name(repo_url)
    embedder = get_embedder(DEFAULT_PROVIDER)
    client = get_qdrant_client()
    expected_dim = get_embedding_dim(DEFAULT_PROVIDER)

    existing = {c.name for c in client.get_collections().collections}

    # Check if existing collection has a mismatched vector dimension and drop it if so
    if collection_name in existing:
        info = client.get_collection(collection_name)
        actual_dim = info.config.params.vectors.size
        if actual_dim != expected_dim:
            print(f"  Dimension mismatch ({actual_dim} → {expected_dim}) — recreating collection")
            client.delete_collection(collection_name)
            existing.discard(collection_name)

    if collection_name in existing and client.count(collection_name).count > 0:
        print(f"Loading existing collection '{collection_name}'")
        return QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embedder,
        )

    # Build from scratch
    print(f"Building collection '{collection_name}' for {repo_url}")
    docs = load_repo_documents(repo_url)

    if not docs:
        raise ValueError(f"No indexable documents found in {repo_url}")

    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=expected_dim, distance=Distance.COSINE),
        )

    vs = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedder,
    )
    _add_documents_with_retry(vs, docs, provider=DEFAULT_PROVIDER)
    print(f"Indexed {len(docs)} chunks into '{collection_name}'")
    return vs
