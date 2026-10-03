from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS camera_devices (
    device_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}',
    capabilities_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_camera_devices_last_seen
ON camera_devices(last_seen);
"""


class Database:
    """Small thread-safe SQLite adapter for device metadata.

    Live connection state deliberately remains in memory; SQLite stores device
    identity and configuration so names and roles survive server restarts.
    """

    def __init__(self, path: Path):
        self.path = path
        self._write_lock = Lock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def initialise(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock, self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def upsert_device(
        self,
        device_id: str,
        name: str,
        role: str,
        settings: dict[str, Any],
        capabilities: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO camera_devices
                    (device_id, name, role, first_seen, last_seen,
                     settings_json, capabilities_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    name = excluded.name,
                    role = excluded.role,
                    last_seen = excluded.last_seen,
                    settings_json = excluded.settings_json,
                    capabilities_json = excluded.capabilities_json
                """,
                (
                    device_id,
                    name,
                    role,
                    now,
                    now,
                    json.dumps(settings),
                    json.dumps(capabilities),
                ),
            )
            connection.commit()

    def touch_device(self, device_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock, self.connect() as connection:
            connection.execute(
                "UPDATE camera_devices SET last_seen = ? WHERE device_id = ?",
                (now, device_id),
            )
            connection.commit()

    def rename_device(self, device_id: str, name: str, role: str) -> None:
        with self._write_lock, self.connect() as connection:
            cursor = connection.execute(
                "UPDATE camera_devices SET name = ?, role = ? WHERE device_id = ?",
                (name, role, device_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(device_id)
            connection.commit()

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM camera_devices WHERE device_id = ?", (device_id,)
            ).fetchone()
        return self._decode_row(row) if row else None

    def list_known_devices(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM camera_devices ORDER BY last_seen DESC"
            ).fetchall()
        return [self._decode_row(row) for row in rows]

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["settings"] = json.loads(result.pop("settings_json"))
        result["capabilities"] = json.loads(result.pop("capabilities_json"))
        return result
