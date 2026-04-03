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
