"""
SQLite-backed cache for generated wiki content.

Schema (table: wiki_cache):
    owner       TEXT  — GitHub owner (e.g. "langchain-ai")
    repo        TEXT  — repository name (e.g. "langgraph")
    language    TEXT  — output language code (e.g. "English")
    wiki_structure  TEXT  — JSON-encoded wiki structure (pages plan)
    pages       TEXT  — JSON-encoded dict of {page_title: markdown_content}
    created_at  TEXT  — ISO-8601 timestamp of first save
    updated_at  TEXT  — ISO-8601 timestamp of last save

Primary key is (owner, repo, language).
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = os.path.expanduser("~/.repolens/wiki_cache.db")


def _connect() -> sqlite3.Connection:
    """
    Open (and if necessary create) the wiki cache SQLite database.

    Returns:
        sqlite3.Connection: A connection with row_factory set to sqlite3.Row.
    """
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """
    Create the wiki_cache table if it does not already exist.

    Args:
        conn: An open SQLite connection.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_cache (
            owner           TEXT NOT NULL,
            repo            TEXT NOT NULL,
            language        TEXT NOT NULL,
            wiki_structure  TEXT NOT NULL DEFAULT '{}',
            pages           TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            PRIMARY KEY (owner, repo, language)
        )
        """
    )
    conn.commit()


def get_wiki(owner: str, repo: str, language: str) -> Optional[dict]:
    """
    Retrieve a cached wiki for the given owner/repo/language combination.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        language: Output language code.

    Returns:
        dict: Cached wiki data with keys ``owner``, ``repo``, ``language``,
            ``wiki_structure``, ``pages``, ``created_at``, ``updated_at``;
            or ``None`` if no cache entry exists.
    """
    with _connect() as conn:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT * FROM wiki_cache WHERE owner=? AND repo=? AND language=?",
            (owner, repo, language),
        ).fetchone()

    if row is None:
        return None

    return {
        "owner": row["owner"],
        "repo": row["repo"],
        "language": row["language"],
        "wiki_structure": json.loads(row["wiki_structure"]),
        "pages": json.loads(row["pages"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def save_wiki(
    owner: str,
    repo: str,
    language: str,
    wiki_structure: dict,
    pages: dict,
) -> dict:
    """
    Insert or replace a wiki cache entry.

    If an entry for (owner, repo, language) already exists it is overwritten;
    ``created_at`` is preserved on updates.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        language: Output language code.
        wiki_structure: Wiki page plan (dict with a ``pages`` list).
        pages: Mapping of page title to generated markdown content.

    Returns:
        dict: The saved cache entry (same shape as :func:`get_wiki`).
    """
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        _ensure_table(conn)

        existing = conn.execute(
            "SELECT created_at FROM wiki_cache WHERE owner=? AND repo=? AND language=?",
            (owner, repo, language),
        ).fetchone()

        created_at = existing["created_at"] if existing else now

        conn.execute(
            """
            INSERT OR REPLACE INTO wiki_cache
                (owner, repo, language, wiki_structure, pages, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner,
                repo,
                language,
                json.dumps(wiki_structure),
                json.dumps(pages),
                created_at,
                now,
            ),
        )
        conn.commit()

    return {
        "owner": owner,
        "repo": repo,
        "language": language,
        "wiki_structure": wiki_structure,
        "pages": pages,
        "created_at": created_at,
        "updated_at": now,
    }


def delete_wiki(owner: str, repo: str, language: Optional[str] = None) -> int:
    """
    Delete cached wiki entries for the given owner/repo, optionally filtered by language.

    Args:
        owner: GitHub repository owner.
        repo: GitHub repository name.
        language: If provided, only the entry for that language is deleted;
            if ``None``, all language variants are deleted.

    Returns:
        int: Number of rows deleted.
    """
    with _connect() as conn:
        _ensure_table(conn)

        if language is not None:
            cursor = conn.execute(
                "DELETE FROM wiki_cache WHERE owner=? AND repo=? AND language=?",
                (owner, repo, language),
            )
        else:
            cursor = conn.execute(
                "DELETE FROM wiki_cache WHERE owner=? AND repo=?",
                (owner, repo),
            )

        conn.commit()
        return cursor.rowcount


def list_wikis() -> list[dict]:
    """
    Return a summary of all cached wikis (without full page content).

    Returns:
        list[dict]: Each entry has keys ``owner``, ``repo``, ``language``,
            ``page_count``, ``created_at``, ``updated_at``.
    """
    with _connect() as conn:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT owner, repo, language, pages, created_at, updated_at FROM wiki_cache ORDER BY updated_at DESC"
        ).fetchall()

    result = []
    for row in rows:
        pages = json.loads(row["pages"])
        result.append(
            {
                "owner": row["owner"],
                "repo": row["repo"],
                "language": row["language"],
                "page_count": len(pages),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return result
