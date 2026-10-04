"""app/services/storage.py: Embedded SQLite repository for generated roadmaps."""

from pathlib import Path
import sqlite3
from typing import Protocol

from app.schemas.roadmap import ProjectRoadmap


class RoadmapRepository(Protocol):
    """Abstract protocol for roadmap persistence."""

    def save(self, roadmap: ProjectRoadmap) -> None:
        ...

    def get_by_id(self, roadmap_id: str) -> ProjectRoadmap | None:
        ...


class SQLiteRoadmapRepository:
    """Thread-safe SQLite storage engine running in WAL mode."""

    def __init__(self, db_path: Path | str = "data/roadmaps.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roadmaps (
                    roadmap_id TEXT PRIMARY KEY,
                    project_title TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def save(self, roadmap: ProjectRoadmap) -> None:
        """Persists a validated roadmap payload idempotently."""
        payload = roadmap.model_dump_json()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO roadmaps (roadmap_id, project_title, domain, payload_json)
                VALUES (?, ?, ?, ?);
                """,
                (roadmap.roadmap_id, roadmap.project_title, roadmap.domain, payload),
            )

    def get_by_id(self, roadmap_id: str) -> ProjectRoadmap | None:
        """Retrieves and deserializes a roadmap by UUID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT payload_json FROM roadmaps WHERE roadmap_id = ?;",
                (roadmap_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return ProjectRoadmap.model_validate_json(row[0])