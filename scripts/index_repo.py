"""
Test script: index a public GitHub repo into Qdrant and verify chunks are stored.
Usage: uv run scripts/index_repo.py https://github.com/owner/repo
"""
import sys
from api.vectorstore import load_or_build_vectorstore, get_collection_name, get_qdrant_client


def main():
    repo_url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/anthropics/anthropic-sdk-python"
    print(f"Indexing: {repo_url}")
    vs = load_or_build_vectorstore(repo_url)
    client = get_qdrant_client()
    name = get_collection_name(repo_url)
    count = client.count(name).count
    print(f"Stored {count} chunks in collection '{name}'")


if __name__ == "__main__":
    main()
