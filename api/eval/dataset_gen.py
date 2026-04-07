"""
Synthetic eval dataset generation.

Samples chunks from an existing Qdrant collection and uses an LLM to
generate questions across six categories with fixed distribution:
    direct      (4) — straightforward question the chunk directly answers
    rephrased   (4) — same intent as direct, reworded with different vocabulary
    conceptual  (3) — asks about design intent / architecture
    negative    (3) — asks something the chunk cannot answer (tests hallucination)
    cross_file  (3) — requires understanding across multiple files
    keyword     (3) — uses exact identifiers (function/class names) from the code
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
    "cross_file": (
        "Below are code snippets from different files in the same GitHub repository.\n\n"
        "{content}\n\n"
        "Write ONE question that requires understanding ALL of these snippets together "
        "to answer fully. The question should be about how these components interact, "
        "how data flows between them, or what they accomplish as a system.\n"
        "Return ONLY the question text, nothing else."
    ),
    "keyword": (
        "Given the following code or documentation snippet from a GitHub repository:\n\n"
        "CONTENT:\n{content}\n\n"
        "Step 1: Identify the most important specific identifier in this snippet "
        "(a function name, class name, variable name, config key, or CLI flag).\n"
        "Step 2: Write ONE question that uses that exact identifier by name. "
        "The question should ask what it does, how it works, or where it is used.\n"
        "For example: 'What does the load_or_build_vectorstore function do?' or "
        "'What is the _TOP_K variable used for?'\n"
        "Return ONLY the question text, nothing else."
    ),
}

# Fixed distribution: category -> count (total = 20)
_CATEGORY_DISTRIBUTION = {
    "direct": 4,
    "rephrased": 4,
    "conceptual": 3,
    "negative": 3,
    "cross_file": 3,
    "keyword": 3,
}


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------


def _scroll_all_chunks(repo_url: str) -> list[dict]:
    """
    Scroll all chunks from the Qdrant collection for a repo.

    Args:
        repo_url: GitHub repository URL.

    Returns:
        list[dict]: Each dict has "page_content" (str) and "file_path" (str).
    """
    client = get_qdrant_client()
    collection_name = get_collection_name(repo_url)
    all_points = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=200,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(points)
        if offset is None:
            break

    results = []
    for p in all_points:
        content = p.payload.get("page_content", "")
        metadata = p.payload.get("metadata", {})
        if content.strip():
            results.append({
                "page_content": content,
                "file_path": metadata.get("file_path", "unknown"),
            })
    return results


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


def _sample_cross_file_groups(all_chunks: list[dict], n: int = 3) -> list[list[dict]]:
    """
    Sample n groups of 2-3 chunks from different files for cross-file questions.

    Args:
        all_chunks: All chunks from the repo.
        n: Number of cross-file groups to create.

    Returns:
        list[list[dict]]: Each inner list has 2-3 chunks from different files.
    """
    by_file: dict[str, list[dict]] = {}
    for chunk in all_chunks:
        by_file.setdefault(chunk["file_path"], []).append(chunk)

    file_paths = list(by_file.keys())
    if len(file_paths) < 2:
        return []

    groups = []
    for _ in range(n):
        num_files = min(random.choice([2, 3]), len(file_paths))
        selected_files = random.sample(file_paths, num_files)
        group = [random.choice(by_file[f]) for f in selected_files]
        groups.append(group)
    return groups



# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------


def _format_cross_file_content(group: list[dict]) -> str:
    """
    Format a group of chunks from different files into a single prompt string.

    Args:
        group: List of chunks, each from a different file.

    Returns:
        str: Formatted string with file headers and content.
    """
    parts = []
    for chunk in group:
        parts.append(f"--- {chunk['file_path']} ---\n{chunk['page_content'][:400]}")
    return "\n\n".join(parts)


def generate_eval_questions(
    repo_url: str,
    n: int = 20,
    provider: str = "google",
    model: str | None = None,
) -> list[dict]:
    """
    Generate synthetic questions across 6 categories with fixed distribution.

    Categories: direct (4), rephrased (4), conceptual (3), negative (3),
    cross_file (3), readme (3). If README chunks are unavailable, those
    slots are redistributed to other categories.

    Args:
        repo_url: GitHub repository URL (collection must already exist).
        n: Target number of questions (default 20, actual may vary slightly).
        provider: LLM provider — "google" or "openrouter".
        model: Specific model ID; uses provider default if None.

    Returns:
        list[dict]: Each dict has "question" (str), "repo_url" (str),
            and "category" (str).
    """
    llm = get_llm(provider, model, temperature=0.3)

    # Scale distribution if n != 20
    scale = n / 20.0
    distribution = {k: max(1, round(v * scale)) for k, v in _CATEGORY_DISTRIBUTION.items()}

    # Pre-fetch all chunks for cross-file sampling
    all_chunks = _scroll_all_chunks(repo_url)
    if not all_chunks:
        return []

    # Prepare inputs for each category (extra for backfill)
    single_categories = ["direct", "rephrased", "conceptual", "negative", "keyword"]
    single_count = sum(distribution[c] for c in single_categories)
    single_chunks = sample_chunks(repo_url, n=single_count + 10)
    cross_file_groups = _sample_cross_file_groups(all_chunks, n=distribution["cross_file"])

    questions: list[dict] = []
    failed_slots = 0

    # --- Single-chunk categories ---
    chunk_idx = 0
    for category in single_categories:
        for _ in range(distribution[category]):
            if chunk_idx >= len(single_chunks):
                break
            content = single_chunks[chunk_idx]["page_content"][:800]
            chunk_idx += 1
            prompt = _CATEGORY_PROMPTS[category].format(content=content)
            q = _call_llm(llm, prompt, category, repo_url)
            if q:
                questions.append(q)
            else:
                failed_slots += 1

    # --- Cross-file ---
    for group in cross_file_groups:
        content = _format_cross_file_content(group)
        prompt = _CATEGORY_PROMPTS["cross_file"].format(content=content)
        q = _call_llm(llm, prompt, "cross_file", repo_url)
        if q:
            questions.append(q)
        else:
            failed_slots += 1

    # --- Backfill failed slots with direct questions ---
    if failed_slots > 0 and chunk_idx < len(single_chunks):
        print(f"  [eval] Backfilling {failed_slots} failed slots with direct questions")
        for _ in range(failed_slots):
            if chunk_idx >= len(single_chunks):
                break
            content = single_chunks[chunk_idx]["page_content"][:800]
            chunk_idx += 1
            prompt = _CATEGORY_PROMPTS["direct"].format(content=content)
            q = _call_llm(llm, prompt, "direct", repo_url)
            if q:
                questions.append(q)

    # Log category distribution
    counts = {c: 0 for c in _CATEGORY_PROMPTS}
    for q in questions:
        counts[q["category"]] += 1
    dist = " | ".join(f"{c}: {counts[c]}" for c in _CATEGORY_PROMPTS)
    print(f"  Generated {len(questions)} eval questions ({dist})")
    return questions


def _call_llm(llm, prompt: str, category: str, repo_url: str) -> dict | None:
    """
    Call the LLM to generate one question and return a formatted dict.

    Args:
        llm: LangChain chat model instance.
        prompt: The formatted prompt string.
        category: Question category name.
        repo_url: GitHub repository URL.

    Returns:
        dict: {"question": str, "repo_url": str, "category": str}, or None on failure.
    """
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        question = content.strip() if content else ""
        if question:
            return {"question": question, "repo_url": repo_url, "category": category}
        print(f"  [eval] LLM returned empty response for ({category}), raw: {repr(content)}")
    except Exception as exc:
        print(f"  [eval] Question generation failed ({category}): {exc}")
    return None
