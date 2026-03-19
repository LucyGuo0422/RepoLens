"""
Test script: inspect what's stored in a Qdrant collection for a repo.
Usage: uv run scripts/inspect_qdrant.py https://github.com/owner/repo "search query"
"""
import sys
from api.vectorstore import get_qdrant_client, get_collection_name, load_or_build_vectorstore


def main():
    repo_url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/anthropics/anthropic-sdk-python"
    query = sys.argv[2] if len(sys.argv) > 2 else "how does this work"

    name = get_collection_name(repo_url)
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    if name not in collections:
        print(f"Collection '{name}' not found. Run scripts/index_repo.py first.")
        return

    count = client.count(name).count
    print(f"Collection '{name}' has {count} chunks\n")

    vs = load_or_build_vectorstore(repo_url)
    retriever = vs.as_retriever(search_kwargs={"k": 5})
    docs = retriever.invoke(query)

    print(f"Top results for query: '{query}'\n" + "=" * 60)
    for doc in docs:
        print(f"\n[{doc.metadata.get('file_path', 'unknown')}]")
        print(doc.page_content[:300])
        print("...")


if __name__ == "__main__":
    main()
