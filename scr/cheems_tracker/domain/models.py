"""Modelos tipados para observaciones y resultados de sesiones."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LandmarkPoint:
    """Representa un landmark normalizado de una mano."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class HandObservation:
    """Describe una mano detectada en un cuadro de video."""

    side: str
    side_score: float
    gesture: str
    gesture_score: float
    landmarks: tuple[LandmarkPoint, ...]

    @property
    def wrist(self) -> LandmarkPoint:
        """Devuelve el landmark de la muñeca, índice cero de MediaPipe."""
        return self.landmarks[0]


@dataclass(frozen=True)
class GestureFrame:
    """Agrupa las manos detectadas y el timestamp de un cuadro."""

    timestamp_ms: int
    hands: tuple[HandObservation, ...]


@dataclass(frozen=True)
class SessionResult:
    """Contiene el resumen final no clínico de una actividad."""

    session_id: str
    summary: dict[str, Any]


@dataclass(frozen=True)
class StoredSession:
    """Representa una sesión recuperada desde SQLite para generar reportes."""

    session_id: str
    instruction: str
    started_at: str
    ended_at: str | None
    summary: dict[str, Any]


@dataclass(frozen=True)
class StoredHandObservation:
    """Contiene los campos persistidos de una mano detectada."""

    timestamp_ms: int
    side: str
    gesture: str
    gesture_score: float
    wrist_x: float
    wrist_y: float


@dataclass(frozen=True)
class StoredSessionEvent:
    """Representa una acción explícita marcada por el terapeuta."""

    timestamp_ms: int
    event_type: str
