# Eval Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a LangSmith-powered evaluation pipeline that measures RAG answer quality using 3 custom LLM-as-judge evaluators, with results visible in the LangSmith dashboard.

**Architecture:** Generate synthetic questions from existing Qdrant chunks, run each through the existing RAG graph via LangSmith `evaluate()`, score with 3 custom judges (relevance, groundedness, retrieval_relevance), and persist aggregate scores in SQLite. All detailed results are viewed in the LangSmith UI.

**Tech Stack:** LangSmith SDK, LangChain Google GenAI (structured output), SQLite

---

## File Structure

```
api/eval/                        # NEW — eval module
  __init__.py                    # empty
  evaluators.py                  # 3 custom LLM-as-judge functions
  dataset_gen.py                 # sample Qdrant chunks → generate questions
  runner.py                      # orchestrate full eval run via LangSmith SDK
  eval_cache.py                  # SQLite CRUD for eval_results table

api/api.py                       # MODIFY — add POST /eval/run, GET /eval/results
```

---

### Task 1: Setup — install dependency and env vars

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `api/eval/__init__.py`

- [ ] **Step 1: Install langsmith**

```bash
uv add langsmith
```

- [ ] **Step 2: Add env vars to `.env.example`**

Add these two lines at the end of `.env.example`:

```
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_TRACING=true
```

Also add these same values (with your real key) to your local `.env`.

- [ ] **Step 3: Create eval module init file**

Create `api/eval/__init__.py` as an empty file:

```python
```

- [ ] **Step 4: Commit**

```bash
git add api/eval/__init__.py pyproject.toml .env.example uv.lock
git commit -m "feat(eval): add langsmith dependency and eval module skeleton"
```

---

### Task 2: Eval SQLite cache

**Files:**
- Create: `api/eval/eval_cache.py`

This follows the same pattern as `api/wiki_cache.py` — a separate table in the same `~/.repolens/wiki_cache.db` database.

- [ ] **Step 1: Create `api/eval/eval_cache.py`**

```python
"""
SQLite-backed storage for evaluation results.

Schema (table: eval_results):
    id                      INTEGER PRIMARY KEY
    owner                   TEXT — GitHub owner
    repo                    TEXT — repository name
    num_questions           INTEGER — number of questions evaluated
    relevance_score         REAL — average answer relevance (0–1)
    groundedness_score      REAL — average groundedness (0–1)
    retrieval_relevance_score REAL — average retrieval relevance (0–1)
    langsmith_url           TEXT — link to LangSmith experiment
    run_at                  TEXT — ISO-8601 timestamp
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = os.path.expanduser("~/.repolens/wiki_cache.db")


def _connect() -> sqlite3.Connection:
    """
    Open the RepoLens SQLite database.

    Returns:
        sqlite3.Connection: A connection with row_factory set to sqlite3.Row.
    """
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """
    Create the eval_results table if it does not already exist.

    Args:
        conn: An open SQLite connection.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS eval_results (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            owner                     TEXT NOT NULL,
            repo                      TEXT NOT NULL,
            num_questions             INTEGER NOT NULL,
            relevance_score           REAL NOT NULL,
            groundedness_score        REAL NOT NULL,
            retrieval_relevance_score REAL NOT NULL,
            langsmith_url             TEXT NOT NULL DEFAULT '',
            run_at                    TEXT NOT NULL
        )
        """
    )
    conn.commit()


def save_eval_result(
    owner: str,
    repo: str,
    num_questions: int,
    relevance_score: float,
    groundedness_score: float,
    retrieval_relevance_score: float,
    langsmith_url: str = "",
) -> dict:
    """
    Save an evaluation result, replacing any previous result for the same repo.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        num_questions: Number of questions in the eval dataset.
        relevance_score: Average answer relevance score (0–1).
        groundedness_score: Average groundedness score (0–1).
        retrieval_relevance_score: Average retrieval relevance score (0–1).
        langsmith_url: URL to the LangSmith experiment dashboard.

    Returns:
        dict: The saved eval result.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        _ensure_table(conn)
        conn.execute("DELETE FROM eval_results WHERE owner=? AND repo=?", (owner, repo))
        conn.execute(
            """INSERT INTO eval_results
               (owner, repo, num_questions, relevance_score, groundedness_score,
                retrieval_relevance_score, langsmith_url, run_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (owner, repo, num_questions, relevance_score, groundedness_score,
             retrieval_relevance_score, langsmith_url, now),
        )
        conn.commit()
    return get_eval_result(owner, repo)


def get_eval_result(owner: str, repo: str) -> Optional[dict]:
    """
    Retrieve the most recent eval result for the given owner/repo.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.

    Returns:
        dict: Eval result with score fields, or None if no result exists.
    """
    with _connect() as conn:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT * FROM eval_results WHERE owner=? AND repo=? ORDER BY run_at DESC LIMIT 1",
            (owner, repo),
        ).fetchone()
    if row is None:
        return None
    return dict(row)
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
uv run python -c "from api.eval.eval_cache import save_eval_result, get_eval_result; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/eval/eval_cache.py
git commit -m "feat(eval): add SQLite cache for evaluation results"
```

---

### Task 3: Custom evaluators

**Files:**
- Create: `api/eval/evaluators.py`

Three LLM-as-judge functions using Gemini Flash with structured output. Each takes `(inputs, outputs)` from LangSmith and returns `{"key": str, "score": float}`.

- [ ] **Step 1: Create `api/eval/evaluators.py`**

```python
"""
Custom LLM-as-judge evaluators for RAG quality scoring.

Three evaluators:
    relevance            — Does the answer address the question?
    groundedness         — Is the answer supported by retrieved context?
    retrieval_relevance  — Did the retriever fetch useful chunks?

Each function follows the LangSmith evaluator signature:
    (inputs: dict, outputs: dict) -> dict with {"key": str, "score": float}
"""

import os
from typing_extensions import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# ---------------------------------------------------------------------------
# Judge LLM — non-streaming, temperature=0 for deterministic grading
# ---------------------------------------------------------------------------

_judge_llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
    streaming=False,
)


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------

class RelevanceGrade(TypedDict):
    """Structured output for the relevance judge."""

    reasoning: Annotated[str, ..., "Step-by-step reasoning for the grade"]
    relevant: Annotated[bool, ..., "True if the answer addresses the question"]


class GroundednessGrade(TypedDict):
    """Structured output for the groundedness judge."""

    reasoning: Annotated[str, ..., "Step-by-step reasoning for the grade"]
    grounded: Annotated[bool, ..., "True if every claim is supported by context"]


class RetrievalRelevanceGrade(TypedDict):
    """Structured output for the retrieval relevance judge."""

    reasoning: Annotated[str, ..., "Step-by-step reasoning for the grade"]
    relevant: Annotated[bool, ..., "True if retrieved docs are relevant to the question"]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_RELEVANCE_INSTRUCTIONS = (
    "You are grading whether an AI assistant's answer addresses the question asked.\n"
    "Grade True if the answer is on-topic and attempts to answer the question.\n"
    "Grade False if the answer is off-topic, refuses to answer, or ignores the question.\n"
    "Explain your reasoning step by step before giving a final verdict."
)

_GROUNDEDNESS_INSTRUCTIONS = (
    "You are checking whether an AI assistant's answer is supported by the provided context.\n"
    "Grade True if every factual claim in the answer can be found in or inferred from the context.\n"
    "Grade False if the answer contains claims not present in the context (hallucination).\n"
    "Explain your reasoning step by step before giving a final verdict."
)

_RETRIEVAL_RELEVANCE_INSTRUCTIONS = (
    "You are checking whether retrieved documents are relevant to a question.\n"
    "Grade True if the documents contain information that could help answer the question.\n"
    "Grade False if the documents are mostly unrelated to the question.\n"
    "Explain your reasoning step by step before giving a final verdict."
)


# ---------------------------------------------------------------------------
# Judge instances with structured output
# ---------------------------------------------------------------------------

_relevance_judge = _judge_llm.with_structured_output(RelevanceGrade)
_groundedness_judge = _judge_llm.with_structured_output(GroundednessGrade)
_retrieval_relevance_judge = _judge_llm.with_structured_output(RetrievalRelevanceGrade)


# ---------------------------------------------------------------------------
# Evaluator functions (LangSmith-compatible signatures)
# ---------------------------------------------------------------------------


def relevance(inputs: dict, outputs: dict) -> dict:
    """
    Judge whether the answer addresses the question.

    Args:
        inputs: Must contain "question" (str).
        outputs: Must contain "answer" (str).

    Returns:
        dict: {"key": "relevance", "score": 1.0 or 0.0}
    """
    prompt = f"QUESTION: {inputs['question']}\nANSWER: {outputs['answer']}"
    grade = _relevance_judge.invoke([
        {"role": "system", "content": _RELEVANCE_INSTRUCTIONS},
        {"role": "user", "content": prompt},
    ])
    return {"key": "relevance", "score": 1.0 if grade["relevant"] else 0.0}


def groundedness(inputs: dict, outputs: dict) -> dict:
    """
    Judge whether the answer is supported by the retrieved documents.

    Args:
        inputs: Not used directly (question available but not needed).
        outputs: Must contain "answer" (str) and "documents" (list of dicts
            with "page_content" key).

    Returns:
        dict: {"key": "groundedness", "score": 1.0 or 0.0}
    """
    docs_text = "\n\n".join(d["page_content"] for d in outputs.get("documents", []))
    prompt = f"CONTEXT:\n{docs_text}\n\nANSWER: {outputs['answer']}"
    grade = _groundedness_judge.invoke([
        {"role": "system", "content": _GROUNDEDNESS_INSTRUCTIONS},
        {"role": "user", "content": prompt},
    ])
    return {"key": "groundedness", "score": 1.0 if grade["grounded"] else 0.0}


def retrieval_relevance(inputs: dict, outputs: dict) -> dict:
    """
    Judge whether the retrieved documents are relevant to the question.

    Args:
        inputs: Must contain "question" (str).
        outputs: Must contain "documents" (list of dicts with "page_content" key).

    Returns:
        dict: {"key": "retrieval_relevance", "score": 1.0 or 0.0}
    """
    docs_text = "\n\n".join(d["page_content"] for d in outputs.get("documents", []))
    prompt = f"QUESTION: {inputs['question']}\n\nRETRIEVED DOCUMENTS:\n{docs_text}"
    grade = _retrieval_relevance_judge.invoke([
        {"role": "system", "content": _RETRIEVAL_RELEVANCE_INSTRUCTIONS},
        {"role": "user", "content": prompt},
    ])
    return {"key": "retrieval_relevance", "score": 1.0 if grade["relevant"] else 0.0}
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
uv run python -c "from api.eval.evaluators import relevance, groundedness, retrieval_relevance; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/eval/evaluators.py
git commit -m "feat(eval): add 3 custom LLM-as-judge evaluators"
```

---

### Task 4: Synthetic dataset generation

**Files:**
- Create: `api/eval/dataset_gen.py`

Samples random chunks from the existing Qdrant collection for a repo, then asks Gemini to generate one question per chunk.

- [ ] **Step 1: Create `api/eval/dataset_gen.py`**

```python
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
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
uv run python -c "from api.eval.dataset_gen import generate_eval_questions; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/eval/dataset_gen.py
git commit -m "feat(eval): add synthetic question generation from Qdrant chunks"
```

---

### Task 5: Eval runner

**Files:**
- Create: `api/eval/runner.py`

Orchestrates the full evaluation: generate questions → upload to LangSmith dataset → run RAG graph via `evaluate()` → collect scores → save to SQLite.

- [ ] **Step 1: Create `api/eval/runner.py`**

```python
"""
Eval runner: orchestrate the full LangSmith evaluation pipeline.

1. Generate synthetic questions from Qdrant chunks
2. Create/update a LangSmith dataset
3. Run each question through the existing RAG graph
4. Score with 3 custom evaluators
5. Aggregate and persist results
"""

from langsmith import Client
from langsmith import evaluate as ls_evaluate

from api.eval.dataset_gen import generate_eval_questions
from api.eval.eval_cache import save_eval_result
from api.eval.evaluators import groundedness, relevance, retrieval_relevance
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
    questions = generate_eval_questions(repo_url, n=num_questions)
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
        inputs=[{"question": q["question"], "repo_url": q["repo_url"]} for q in questions],
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
        result = graph.invoke({
            "repo_url": inputs["repo_url"],
            "query": inputs["question"],
            "language": "English",
            "messages": [],
            "retrieved_docs": [],
            "context_text": "",
            "answer": "",
        })
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
```

- [ ] **Step 2: Verify the module imports cleanly**

```bash
uv run python -c "from api.eval.runner import run_eval; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/eval/runner.py
git commit -m "feat(eval): add eval runner with LangSmith evaluate() orchestration"
```

---

### Task 6: API endpoints

**Files:**
- Modify: `api/api.py` — add `POST /eval/run` and `GET /eval/results`
- Modify: `frontend/next.config.ts` — add `/eval/*` rewrite

- [ ] **Step 1: Add imports and request model to `api/api.py`**

Add these imports near the top of `api/api.py`, after the existing imports:

```python
from api.eval.eval_cache import get_eval_result
from api.eval.runner import run_eval
```

Add this request model after the `DeepResearchRequest` class (around line 503):

```python
class EvalRunRequest(BaseModel):
    """Request body for the /eval/run endpoint."""

    repo_url: str
    provider: str = "google"
    model: str | None = None
    num_questions: int = 30
```

- [ ] **Step 2: Add the two eval endpoints to `api/api.py`**

Add these at the end of the file, after the `chat_deep_research` endpoint:

```python
# ---------------------------------------------------------------------------
# Eval endpoints
# ---------------------------------------------------------------------------


@app.post("/eval/run")
async def eval_run_endpoint(req: EvalRunRequest):
    """
    Run the evaluation pipeline for a repository.

    Generates synthetic questions, runs them through the RAG graph,
    scores with 3 custom evaluators via LangSmith, and returns
    aggregated scores.

    Args:
        req: EvalRunRequest with repo_url, provider, model, and num_questions.

    Returns:
        dict: Aggregated eval scores.

    Raises:
        HTTPException: 400 if repo_url is invalid; 500 if eval fails.
    """
    # Parse owner/repo from URL
    parts = req.repo_url.rstrip("/").split("github.com/")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub repo URL")
    segments = parts[-1].strip("/").split("/")
    if len(segments) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub repo URL")
    owner, repo = segments[0], segments[1]

    loop = asyncio.get_event_loop()
    try:
        scores = await loop.run_in_executor(
            None, run_eval, owner, repo, req.repo_url, req.provider, req.model, req.num_questions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eval failed: {exc}") from exc
    return scores


@app.get("/eval/results")
def eval_results_endpoint(owner: str, repo: str):
    """
    Retrieve the most recent evaluation result for a repository.

    Args:
        owner: GitHub repository owner (query param).
        repo: GitHub repository name (query param).

    Returns:
        dict: Eval result with score fields.

    Raises:
        HTTPException: 404 if no eval results exist.
    """
    result = get_eval_result(owner, repo)
    if result is None:
        raise HTTPException(status_code=404, detail="No eval results found")
    return result
```

- [ ] **Step 3: Test the endpoints with curl**

Start the backend, then test:

```bash
# Check eval results (should 404 — no results yet)
curl http://localhost:8002/eval/results?owner=fastapi&repo=fastapi
# Expected: {"detail":"No eval results found"}

# Run eval (use a small repo you've already indexed)
curl -X POST http://localhost:8002/eval/run \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/OWNER/REPO", "num_questions": 5}' \
  --max-time 300
# Expected: JSON with relevance_score, groundedness_score, retrieval_relevance_score
```

Replace `OWNER/REPO` with a repo you have already indexed in Qdrant. Use `num_questions: 5` for a quick test.

- [ ] **Step 4: Commit**

```bash
git add api/api.py
git commit -m "feat(eval): add POST /eval/run and GET /eval/results endpoints"
```

---

### Task 7: End-to-end test

**Files:** None — this is a manual verification task.

- [ ] **Step 1: Start the backend**

```bash
uv run uvicorn api.api:app --host 0.0.0.0 --port 8002 --reload
```

- [ ] **Step 2: Run eval via API**

Pick a repo you have already indexed (has an existing Qdrant collection). Run with `num_questions: 5` for speed:

```bash
curl -X POST http://localhost:8002/eval/run \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/OWNER/REPO", "num_questions": 5}' \
  --max-time 300
```

Replace `OWNER/REPO` with a repo you have already indexed in Qdrant.

Verify:
- Returns JSON with `relevance_score`, `groundedness_score`, `retrieval_relevance_score`
- All scores are between 0.0 and 1.0
- `num_questions` matches what you requested

- [ ] **Step 3: Check LangSmith dashboard**

Go to [smith.langchain.com](https://smith.langchain.com). Verify:
- A dataset named `repolens-OWNER-REPO` exists with your questions
- An experiment with prefix `repolens-OWNER-REPO` exists
- Each row shows the 3 evaluator scores
- You can click into a row and see the full RAG trace

- [ ] **Step 4: Check cached results**

```bash
curl "http://localhost:8002/eval/results?owner=OWNER&repo=REPO"
```

Verify it returns the same scores as Step 2.
