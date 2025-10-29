from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass
class CacheItem:
    id: int
    payload: Dict
    created_at: float


class OfflineCache:
    """Durable payload cache ensuring data is preserved while offline."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(db_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                size_bytes INTEGER NOT NULL
            )
            """
        )
        self._connection.commit()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, payload: Dict) -> None:
        encoded = json.dumps(payload, separators=(",", ":"))
        with self._lock:
            self._connection.execute(
                "INSERT INTO queue (payload, created_at, size_bytes) VALUES (?, ?, ?)",
                (encoded, time.time(), len(encoded.encode("utf-8"))),
            )
            self._connection.commit()

    def get_batch(self, limit: int) -> List[CacheItem]:
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT id, payload, created_at FROM queue ORDER BY id ASC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [CacheItem(id=row[0], payload=json.loads(row[1]), created_at=row[2]) for row in rows]

    def remove(self, ids: Iterable[int]) -> None:
        if not ids:
            return
        with self._lock:
            self._connection.executemany("DELETE FROM queue WHERE id = ?", [(item_id,) for item_id in ids])
            self._connection.commit()

    def total_size_bytes(self) -> int:
        cursor = self._connection.cursor()
        cursor.execute("SELECT SUM(size_bytes) FROM queue")
        result = cursor.fetchone()[0]
        return int(result or 0)

    def count(self) -> int:
        cursor = self._connection.cursor()
        cursor.execute("SELECT COUNT(1) FROM queue")
        result = cursor.fetchone()[0]
        return int(result or 0)

    def trim_to_limit(self, limit_bytes: int) -> int:
        """Trim oldest entries until total size fits within limit."""
        removed = 0
        while self.total_size_bytes() > limit_bytes:
            cursor = self._connection.cursor()
            cursor.execute("SELECT id FROM queue ORDER BY id ASC LIMIT 50")
            ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                break
            self.remove(ids)
            removed += len(ids)
        return removed

    def close(self) -> None:
        with self._lock:
            self._connection.close()
