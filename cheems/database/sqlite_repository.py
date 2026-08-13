"""Repositorio SQLite para resultados de actividades."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cheems.domain.models import (
    GestureFrame,
    StoredHandObservation,
    StoredSession,
    StoredSessionEvent,
)
from cheems.security.crypto import MedicalDataCryptor


class SessionRepository:
    """Guarda sesiones, pacientes y observaciones de landmarks de forma local y cifrada."""

    def __init__(self, database_path: Path, cryptor: Optional[MedicalDataCryptor] = None) -> None:
        """Crea directorios necesarios e inicializa el esquema de SQLite con soporte de cifrado y multihilo."""
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._cryptor = cryptor or MedicalDataCryptor(key_path=database_path.parent / ".security_key")
        self._connection = sqlite3.connect(database_path, check_same_thread=False)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        """Crea tablas para pacientes, sesiones y observaciones con soporte criptográfico."""
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                encrypted_full_name TEXT NOT NULL,
                age_months INTEGER NOT NULL,
                evaluator TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
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

    def save_patient(self, patient_id: str, full_name: str, age_months: int, evaluator: str) -> None:
        """Guarda o actualiza un paciente cifrando su nombre e información identificable."""
        enc_name = self._cryptor.encrypt_text(full_name)
        self._connection.execute(
            """
            INSERT INTO patients (patient_id, encrypted_full_name, age_months, evaluator, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(patient_id) DO UPDATE SET
                encrypted_full_name=excluded.encrypted_full_name,
                age_months=excluded.age_months,
                evaluator=excluded.evaluator
            """,
            (patient_id, enc_name, age_months, evaluator, self._now()),
        )
        self._connection.commit()

    def get_patient(self, patient_id: str) -> Optional[dict[str, object]]:
        """Recupera y descifra los datos de un paciente."""
        row = self._connection.execute(
            "SELECT patient_id, encrypted_full_name, age_months, evaluator, created_at FROM patients WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "patient_id": row[0],
            "full_name": self._cryptor.decrypt_text(row[1]),
            "age_months": row[2],
            "evaluator": row[3],
            "created_at": row[4],
        }

    def list_patients(self) -> list[dict[str, object]]:
        """Lista todos los pacientes descifrando su nombre."""
        cursor = self._connection.execute(
            "SELECT patient_id, encrypted_full_name, age_months, evaluator, created_at FROM patients ORDER BY created_at DESC"
        )
        return [
            {
                "patient_id": row[0],
                "full_name": self._cryptor.decrypt_text(row[1]),
                "age_months": row[2],
                "evaluator": row[3],
                "created_at": row[4],
            }
            for row in cursor.fetchall()
        ]

    def start_session(self, session_id: str, instruction: str, source: str) -> None:
        """Registra el inicio de una sesión cifrando la instrucción/datos clínicos."""
        enc_instruction = self._cryptor.encrypt_text(instruction)
        self._connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, NULL, NULL)",
            (session_id, "evaluation_session", enc_instruction, source, self._now()),
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
        """Guarda el resumen final cifrado y confirma las observaciones pendientes."""
        raw_json = json.dumps(summary, ensure_ascii=False)
        enc_json = self._cryptor.encrypt_text(raw_json)
        self._connection.execute(
            "UPDATE sessions SET ended_at = ?, summary_json = ? WHERE id = ?",
            (self._now(), enc_json, session_id),
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
        """Carga una sesión y sus datos relacionados descifrando su contenido sensible."""
        session_row = self._connection.execute(
            """
            SELECT id, instruction, started_at, ended_at, summary_json
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if session_row is None:
            raise LookupError(f"No existe la sesión: {session_id}")

        dec_instruction = self._cryptor.decrypt_text(str(session_row[1]))
        dec_summary_str = self._cryptor.decrypt_text(session_row[4]) if session_row[4] else None
        parsed_summary = json.loads(dec_summary_str) if dec_summary_str else {}

        session = StoredSession(
            session_id=str(session_row[0]),
            instruction=dec_instruction or "",
            started_at=str(session_row[2]),
            ended_at=str(session_row[3]) if session_row[3] else None,
            summary=parsed_summary,
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
