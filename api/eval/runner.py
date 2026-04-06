"""
Eval runner: orchestrate the full LangSmith evaluation pipeline.

1. Generate synthetic questions from Qdrant chunks
2. Create/update a LangSmith dataset
3. Run each question through the existing RAG graph
4. Score with 3 custom evaluators
5. Aggregate and persist results
"""

import asyncio

from langsmith import Client
from langsmith import evaluate as ls_evaluate

from api.eval.dataset_gen import generate_eval_questions
from api.eval.eval_cache import save_eval_result
from api.eval.evaluators import build_evaluators
from api.graphs.rag_graph import build_rag_graph
from api.vectorstore import load_or_build_vectorstore


def run_eval(
    owner: str,
    repo: str,
    repo_url: str,
    provider: str = "google",
    model: str | None = None,
    num_questions: int = 30,
) -> dict:
    """
    Run the full evaluation pipeline for a repository.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        repo_url: Full GitHub URL.
        provider: LLM provider for the RAG graph.
        model: Model ID for the RAG graph; uses provider default if None.
        num_questions: Number of synthetic questions to generate.

    Returns:
        dict: Aggregated scores with keys relevance_score, groundedness_score,
            retrieval_relevance_score, num_questions, langsmith_url, run_at.

    Raises:
        ValueError: If no questions could be generated.
    """
    # Ensure vectorstore is built
    load_or_build_vectorstore(repo_url)

    # --- 1. Generate synthetic questions ---
    print(f"[eval] Generating {num_questions} questions for {owner}/{repo}")
    questions = generate_eval_questions(repo_url, n=num_questions, provider=provider, model=model)
    if not questions:
        raise ValueError("No eval questions could be generated — is the Qdrant collection empty?")

    # --- 2. Create/update LangSmith dataset ---
    ls_client = Client()
    dataset_name = f"repolens-{owner}-{repo}"

    # Delete existing dataset to start fresh each run
    try:
        existing = ls_client.read_dataset(dataset_name=dataset_name)
        ls_client.delete_dataset(dataset_id=existing.id)
    except Exception:
        pass

    dataset = ls_client.create_dataset(
        dataset_name,
        description=f"Eval dataset for {owner}/{repo}",
    )
    ls_client.create_examples(
        inputs=[
            {"question": q["question"], "repo_url": q["repo_url"], "category": q.get("category", "direct")}
            for q in questions
        ],
        dataset_id=dataset.id,
    )
    print(f"[eval] Uploaded {len(questions)} examples to LangSmith dataset '{dataset_name}'")

    # --- 3. Define target function ---
    graph = build_rag_graph(provider=provider, model=model, checkpointer=None)

    def predict(inputs: dict) -> dict:
        """
        Run the RAG graph for one question and return answer + retrieved docs.

        Args:
            inputs: Dict with "question" and "repo_url" keys.

        Returns:
            dict: {"answer": str, "documents": list[dict]}
        """
        result = asyncio.run(graph.ainvoke({
            "repo_url": inputs["repo_url"],
            "query": inputs["question"],
            "language": "English",
            "messages": [],
            "retrieved_docs": [],
            "context_text": "",
            "answer": "",
        }))
        return {
            "answer": result.get("answer", ""),
            "documents": [
                {
                    "page_content": d.page_content,
                    "file_path": d.metadata.get("file_path", ""),
                }
                for d in result.get("retrieved_docs", [])
            ],
        }

    # --- 4. Run evaluation ---
    relevance, groundedness, retrieval_relevance = build_evaluators(provider=provider, model=model)

    # Track scores locally since the LangSmith results API varies by version
    collected: dict[str, list[float]] = {
        "relevance": [],
        "groundedness": [],
        "retrieval_relevance": [],
    }

    def _tracking(fn, key):
        """Wrap an evaluator to collect scores in the collected dict."""
        def wrapper(inputs, outputs):
            result = fn(inputs, outputs)
            score = result.get("score", 0.0) if isinstance(result, dict) else float(result)
            collected[key].append(score)
            return result
        wrapper.__name__ = key
        return wrapper

    experiment_prefix = f"repolens-{owner}-{repo}"
    print(f"[eval] Running LangSmith evaluate() with prefix '{experiment_prefix}'")

    ls_evaluate(
        predict,
        data=dataset_name,
        evaluators=[
            _tracking(relevance, "relevance"),
            _tracking(groundedness, "groundedness"),
            _tracking(retrieval_relevance, "retrieval_relevance"),
        ],
        experiment_prefix=experiment_prefix,
    )

    # --- 5. Aggregate and persist ---
    def _mean(vals: list[float]) -> float:
        """
        Compute the mean of a list of floats, returning 0.0 for empty lists.

        Args:
            vals: List of float scores.

        Returns:
            float: Mean value rounded to 4 decimal places, or 0.0 if list is empty.
        """
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    langsmith_url = f"https://smith.langchain.com/"
    scores = save_eval_result(
        owner=owner,
        repo=repo,
        num_questions=len(questions),
        relevance_score=_mean(collected["relevance"]),
        groundedness_score=_mean(collected["groundedness"]),
        retrieval_relevance_score=_mean(collected["retrieval_relevance"]),
        langsmith_url=langsmith_url,
    )

    print(
        f"[eval] Done — relevance={scores['relevance_score']:.2f} "
        f"groundedness={scores['groundedness_score']:.2f} "
        f"retrieval_relevance={scores['retrieval_relevance_score']:.2f}"
    )
    return scores
