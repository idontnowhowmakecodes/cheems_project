"""Cálculos descriptivos para una actividad de gestos."""

from collections import Counter
from math import hypot
from typing import Any

from cheems_project.domain.models import GestureFrame


class GestureMetrics:
    """Acumula métricas reproducibles sin realizar interpretación clínica."""

    def __init__(self) -> None:
        """Inicializa contadores y posiciones previas de muñecas."""
        self._frames_processed = 0
        self._frames_with_hands = 0
        self._gesture_counts: Counter[str] = Counter()
        self._wrist_distance: Counter[str] = Counter()
        self._previous_wrists: dict[str, tuple[float, float]] = {}

    def update(self, frame: GestureFrame) -> None:
        """Actualiza conteos y distancia normalizada recorrida por muñeca."""
        self._frames_processed += 1
        if frame.hands:
            self._frames_with_hands += 1
        for hand in frame.hands:
            self._gesture_counts[hand.gesture] += 1
            current_wrist = (hand.wrist.x, hand.wrist.y)
            previous_wrist = self._previous_wrists.get(hand.side)
            if previous_wrist is not None:
                self._wrist_distance[hand.side] += hypot(
                    current_wrist[0] - previous_wrist[0],
                    current_wrist[1] - previous_wrist[1],
                )
            self._previous_wrists[hand.side] = current_wrist

    def summary(self) -> dict[str, Any]:
        """Devuelve métricas agregadas aptas para almacenamiento y gráficos."""
        detection_rate = 0.0
        if self._frames_processed:
            detection_rate = self._frames_with_hands / self._frames_processed
        return {
            "frames_processed": self._frames_processed,
            "frames_with_hands": self._frames_with_hands,
            "hand_detection_rate": round(detection_rate, 4),
            "gesture_counts": dict(self._gesture_counts),
            "wrist_distance_normalized": {
                side: round(distance, 4)
                for side, distance in self._wrist_distance.items()
            },
        }
