"""Tiny database layer: PostgreSQL in production, SQLite as a zero-setup fallback.

Set DATABASE_URL=postgresql://user:pass@host:5432/dbname to use PostgreSQL.
If it is unset, a local SQLite file (data/samsung.db) is used so the project
runs anywhere. SQL in the code base uses `?` placeholders for both back ends.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_SQLITE = Path(__file__).resolve().parent.parent / "data" / "samsung.db"


class Database:
    def __init__(self, url: str | None = None):
        url = url or os.getenv("DATABASE_URL") or ""
        self._lock = threading.RLock()
        self._transaction_depth = 0
        if url.startswith(("postgres://", "postgresql://")):
            import psycopg2  # imported lazily so SQLite users need nothing extra

            self.kind = "postgres"
            self.conn = psycopg2.connect(url)
            self.conn.autocommit = True
        else:
            self.kind = "sqlite"
            path = url.replace("sqlite:///", "") if url else str(DEFAULT_SQLITE)
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")

    # -- helpers -----------------------------------------------------------
    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.kind == "postgres" else sql

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(self._sql(sql), tuple(params))
            if self.kind == "sqlite" and self._transaction_depth == 0:
                self.conn.commit()
            cur.close()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(self._sql(sql), tuple(params))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            return rows

    def insert_returning_id(self, sql: str, params: Iterable[Any] = ()) -> int:
        """Run an INSERT ... ON CONFLICT ... RETURNING id and return the id."""
        rows = self.query(sql + " RETURNING id", params)
        return rows[0]["id"]

    def init_schema(self) -> None:
        ddl = "\n".join(line.split("--")[0] for line in SCHEMA_PATH.read_text().splitlines())
        if self.kind == "sqlite":
            ddl = ddl.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            self.execute(stmt)

    @contextmanager
    def transaction(self):
        """Run a group of writes atomically on the shared connection."""
        with self._lock:
            outermost = self._transaction_depth == 0
            if outermost and self.kind == "postgres":
                self.conn.autocommit = False
            self._transaction_depth += 1
            try:
                yield
            except Exception:
                self._transaction_depth -= 1
                if outermost:
                    self.conn.rollback()
                    if self.kind == "postgres":
                        self.conn.autocommit = True
                raise
            else:
                self._transaction_depth -= 1
                if outermost:
                    self.conn.commit()
                    if self.kind == "postgres":
                        self.conn.autocommit = True

    def close(self) -> None:
        self.conn.close()
