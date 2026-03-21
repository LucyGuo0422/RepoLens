"""
LangGraph checkpointer: SQLite-backed conversation memory.
"""
import os
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_DB_PATH = os.path.expanduser("~/.repolens/checkpoints.db")
_checkpointer: AsyncSqliteSaver | None = None
_conn: aiosqlite.Connection | None = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """
    Return a shared AsyncSqliteSaver backed by ~/.deepwiki/checkpoints.db.

    Opens the aiosqlite connection on first call and reuses it on subsequent calls.
    The database directory is created if it does not exist.

    Returns:
        AsyncSqliteSaver: LangGraph async checkpointer for persistent conversation memory.
    """
    global _checkpointer, _conn
    if _checkpointer is None:
        Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(_DB_PATH)
        _checkpointer = AsyncSqliteSaver(_conn)
        await _checkpointer.setup()
    return _checkpointer
