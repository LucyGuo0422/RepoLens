"""
Synthetic eval dataset generation.

Samples chunks from an existing Qdrant collection and uses an LLM to
generate one question per chunk that the chunk directly answers.
"""

import os
import random

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from api.vectorstore import get_collection_name, get_qdrant_client

load_dotenv()

_question_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3,
    streaming=False,
)

_QUESTION_PROMPT = (
    "Given the following code or documentation snippet from a GitHub repository, "
    "write ONE specific question that this content directly answers.\n"
    "The question should sound natural, as if a developer is exploring an "
    "unfamiliar codebase.\n"
    "Return ONLY the question text, nothing else.\n\n"
    "CONTENT:\n{content}"
)


def sample_chunks(repo_url: str, n: int = 30) -> list[dict]:
    """
    Sample n random chunks from the Qdrant collection for a repo.

    Args:
        repo_url: GitHub repository URL (collection must already exist).
        n: Number of chunks to sample.

    Returns:
        list[dict]: Each dict has "page_content" (str) and "file_path" (str).
    """
    client = get_qdrant_client()
    collection_name = get_collection_name(repo_url)
    total = client.count(collection_name).count
    if total == 0:
        return []

    # Scroll more than needed, then randomly sample
    limit = min(n * 3, total)
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    sampled = random.sample(points, min(n, len(points)))
    results = []
    for p in sampled:
        content = p.payload.get("page_content", "")
        metadata = p.payload.get("metadata", {})
        if content.strip():
            results.append({
                "page_content": content,
                "file_path": metadata.get("file_path", "unknown"),
            })
    return results


def generate_eval_questions(repo_url: str, n: int = 30) -> list[dict]:
    """
    Generate n synthetic questions from sampled repo chunks.

    Samples chunks from the Qdrant collection, then calls the LLM to
    generate one question per chunk. Skips chunks that fail to produce
    a question.

    Args:
        repo_url: GitHub repository URL (collection must already exist).
        n: Number of questions to generate.

    Returns:
        list[dict]: Each dict has "question" (str) and "repo_url" (str).
    """
    chunks = sample_chunks(repo_url, n)
    questions: list[dict] = []

    for chunk in chunks:
        content = chunk["page_content"][:800]
        prompt = _QUESTION_PROMPT.format(content=content)
        try:
            response = _question_llm.invoke(prompt)
            question = response.content.strip()
            if question:
                questions.append({"question": question, "repo_url": repo_url})
        except Exception:
            continue

    print(f"  Generated {len(questions)} eval questions from {len(chunks)} chunks")
    return questions
