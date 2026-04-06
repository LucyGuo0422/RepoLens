"""
Synthetic eval dataset generation.

Samples chunks from an existing Qdrant collection and uses an LLM to
generate questions of varying difficulty across four categories:
    direct     — straightforward question the chunk directly answers
    rephrased  — same intent as direct, but reworded with different vocabulary
    conceptual — asks about design intent / architecture, not surface details
    negative   — asks something the chunk *cannot* answer (tests hallucination)
"""

import random

from api.llm import get_llm
from api.vectorstore import get_collection_name, get_qdrant_client

# ---------------------------------------------------------------------------
# Category prompts
# ---------------------------------------------------------------------------

_CATEGORY_PROMPTS = {
    "direct": (
        "Given the following code or documentation snippet from a GitHub repository, "
        "write ONE specific question that this content directly answers.\n"
        "The question should sound natural, as if a developer is exploring an "
        "unfamiliar codebase.\n"
        "Return ONLY the question text, nothing else.\n\n"
        "CONTENT:\n{content}"
    ),
    "rephrased": (
        "Given the following code or documentation snippet from a GitHub repository:\n\n"
        "CONTENT:\n{content}\n\n"
        "Step 1: Think of a question this content answers.\n"
        "Step 2: Rewrite that question using completely different words and phrasing. "
        "Do NOT reuse any variable names, function names, or technical terms from the snippet.\n"
        "Return ONLY the final rephrased question, nothing else."
    ),
    "conceptual": (
        "Given the following code or documentation snippet from a GitHub repository:\n\n"
        "CONTENT:\n{content}\n\n"
        "Write ONE question about the design intent, architectural choice, or "
        "reasoning behind this code — NOT about what the code literally does.\n"
        "For example: why was this pattern chosen, what problem does this design solve, "
        "what trade-offs does this approach have.\n"
        "Return ONLY the question text, nothing else."
    ),
    "negative": (
        "Given the following code or documentation snippet from a GitHub repository:\n\n"
        "CONTENT:\n{content}\n\n"
        "Write ONE question that is related to the same topic area but CANNOT be "
        "answered from this content alone. The question should sound plausible "
        "and natural — a developer might reasonably ask it, but the answer is "
        "not present in the snippet.\n"
        "Return ONLY the question text, nothing else."
    ),
}

_CATEGORIES = list(_CATEGORY_PROMPTS.keys())


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------


def generate_eval_questions(
    repo_url: str,
    n: int = 30,
    provider: str = "google",
    model: str | None = None,
) -> list[dict]:
    """
    Generate n synthetic questions from sampled repo chunks across 4 categories.

    Each chunk is assigned a random category (direct, rephrased, conceptual,
    negative) so the final dataset covers a range of difficulty levels.

    Args:
        repo_url: GitHub repository URL (collection must already exist).
        n: Number of questions to generate.
        provider: LLM provider — "google" or "openrouter".
        model: Specific model ID; uses provider default if None.

    Returns:
        list[dict]: Each dict has "question" (str), "repo_url" (str),
            and "category" (str).
    """
    llm = get_llm(provider, model, temperature=0.3)
    chunks = sample_chunks(repo_url, n)
    questions: list[dict] = []

    for chunk in chunks:
        content = chunk["page_content"][:800]
        category = random.choice(_CATEGORIES)
        prompt = _CATEGORY_PROMPTS[category].format(content=content)
        try:
            response = llm.invoke(prompt)
            question = response.content.strip()
            if question:
                questions.append({
                    "question": question,
                    "repo_url": repo_url,
                    "category": category,
                })
        except Exception as exc:
            print(f"  [eval] Question generation failed ({category}): {exc}")
            continue

    # Log category distribution
    counts = {c: 0 for c in _CATEGORIES}
    for q in questions:
        counts[q["category"]] += 1
    dist = " | ".join(f"{c}: {counts[c]}" for c in _CATEGORIES)
    print(f"  Generated {len(questions)} eval questions from {len(chunks)} chunks ({dist})")
    return questions
