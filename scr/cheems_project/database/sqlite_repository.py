"""Repositorio SQLite para resultados de actividades."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cheems_project.domain.models import (
    GestureFrame,
    StoredHandObservation,
    StoredSession,
    StoredSessionEvent,
)


class SessionRepository:
    """Guarda sesiones y observaciones de landmarks de forma local."""

    def __init__(self, database_path: Path) -> None:
        """Crea directorios necesarios e inicializa el esquema de SQLite."""
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(database_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        """Crea tablas mínimas para sesiones y observaciones de manos."""
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                activity_name TEXT NOT NULL,
                instruction TEXT NOT NULL,
                source TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                summary_json TEXT
            );
            CREATE TABLE IF NOT EXISTS hand_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                side TEXT NOT NULL,
                side_score REAL NOT NULL,
                gesture TEXT NOT NULL,
                gesture_score REAL NOT NULL,
                wrist_x REAL NOT NULL,
                wrist_y REAL NOT NULL,
                wrist_z REAL NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS session_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            """
        )
        self._connection.commit()

    def start_session(self, session_id: str, instruction: str, source: str) -> None:
        """Registra el inicio de una sesión de actividad."""
        self._connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, NULL, NULL)",
            (session_id, "gesture_imitation", instruction, source, self._now()),
        )
        self._connection.commit()

    def record_frame(self, session_id: str, frame: GestureFrame) -> None:
        """Almacena una observación resumida por cada mano detectada."""
        rows = [
            (
                session_id,
                frame.timestamp_ms,
                hand.side,
                hand.side_score,
                hand.gesture,
                hand.gesture_score,
                hand.wrist.x,
                hand.wrist.y,
                hand.wrist.z,
            )
            for hand in frame.hands
        ]
        if rows:
            # Se persiste una fila por mano, no imágenes ni video del menor.
            self._connection.executemany(
                """
                INSERT INTO hand_observations (
                    session_id, timestamp_ms, side, side_score, gesture,
                    gesture_score, wrist_x, wrist_y, wrist_z
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def record_event(self, session_id: str, timestamp_ms: int, event_type: str) -> None:
        """Registra una acción explícita del terapeuta durante la sesión."""
        self._connection.execute(
            "INSERT INTO session_events (session_id, timestamp_ms, event_type) VALUES (?, ?, ?)",
            (session_id, timestamp_ms, event_type),
        )

    def finish_session(self, session_id: str, summary: dict[str, object]) -> None:
        """Guarda el resumen final y confirma las observaciones pendientes."""
        self._connection.execute(
            "UPDATE sessions SET ended_at = ?, summary_json = ? WHERE id = ?",
            (self._now(), json.dumps(summary, ensure_ascii=False), session_id),
        )
        self._connection.commit()

    def latest_session_id(self) -> str:
        """Devuelve el identificador de la sesión terminada más reciente."""
        row = self._connection.execute(
            """
            SELECT id FROM sessions
            WHERE ended_at IS NOT NULL
            ORDER BY ended_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            raise LookupError("No hay sesiones finalizadas para generar un reporte.")
        return str(row[0])

    def load_report_data(
        self,
        session_id: str,
    ) -> tuple[StoredSession, list[StoredHandObservation], list[StoredSessionEvent]]:
        """Carga una sesión y sus datos relacionados para visualización."""
        session_row = self._connection.execute(
            """
            SELECT id, instruction, started_at, ended_at, summary_json
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if session_row is None:
            raise LookupError(f"No existe la sesión: {session_id}")

        session = StoredSession(
            session_id=str(session_row[0]),
            instruction=str(session_row[1]),
            started_at=str(session_row[2]),
            ended_at=str(session_row[3]) if session_row[3] else None,
            summary=json.loads(session_row[4]) if session_row[4] else {},
        )
        observations = [
            StoredHandObservation(
                timestamp_ms=int(row[0]),
                side=str(row[1]),
                gesture=str(row[2]),
                gesture_score=float(row[3]),
                wrist_x=float(row[4]),
                wrist_y=float(row[5]),
            )
            for row in self._connection.execute(
                """
                SELECT timestamp_ms, side, gesture, gesture_score, wrist_x, wrist_y
                FROM hand_observations WHERE session_id = ? ORDER BY timestamp_ms
                """,
                (session_id,),
            )
        ]
        events = [
            StoredSessionEvent(timestamp_ms=int(row[0]), event_type=str(row[1]))
            for row in self._connection.execute(
                """
                SELECT timestamp_ms, event_type
                FROM session_events WHERE session_id = ? ORDER BY timestamp_ms
                """,
                (session_id,),
            )
        ]
        return session, observations, events

    def close(self) -> None:
        """Cierra la conexión SQLite de la aplicación."""
        self._connection.close()

    @staticmethod
    def _now() -> str:
        """Devuelve la hora UTC en formato ISO para comparaciones consistentes."""
        return datetime.now(timezone.utc).isoformat()
