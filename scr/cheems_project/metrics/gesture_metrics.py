"""Cálculos descriptivos para una actividad de gestos."""

from collections import Counter
from math import hypot
from typing import Any

from cheems_project.domain.models import GestureFrame


class GestureMetrics:
    """Acumula métricas reproducibles sin realizar interpretación clínica."""

    def __init__(self) -> None:
        """Inicializa contadores, posiciones previas y métricas ADOS-2."""
        self._frames_processed = 0
        self._frames_with_hands = 0
        self._gesture_counts: Counter[str] = Counter()
        self._wrist_distance: Counter[str] = Counter()
        self._previous_wrists: dict[str, tuple[float, float]] = {}

        # Métricas inspiradas en ADOS-2
        self._history: dict[str, list[tuple[int, float, float]]] = {}  # side -> historial (timestamp_ms, x, y)
        self._stereotypy_count_by_side: Counter[str] = Counter()
        self._last_stereotypy_time: dict[str, int] = {}  # side -> timestamp_ms de último evento
        self._last_detected_timestamp_ms = -1
        self._last_frame_timestamp_ms = -1
        self._last_stereotypy_side = ""

        self._pending_attempt_start: int | None = None
        self._latencies: list[int] = []
        self._attempt_gestures: list[str] = []

        self._social_gestures = {"Pointing_Up", "Open_Palm"}
        self._social_gesture_counts: Counter[str] = Counter()

    def mark_attempt(self, timestamp_ms: int) -> None:
        """Inicia el temporizador de latencia para un nuevo intento de imitación."""
        self._pending_attempt_start = timestamp_ms

    @property
    def stereotypy_counts(self) -> dict[str, int]:
        """Devuelve el conteo de estereotipias por mano."""
        return dict(self._stereotypy_count_by_side)

    @property
    def last_stereotypy_side(self) -> str:
        """Devuelve el lado donde se detectó la última estereotipia."""
        return self._last_stereotypy_side

    @property
    def is_stereotypy_active(self) -> bool:
        """Devuelve True si hubo una estereotipia en los últimos 1500 ms."""
        if self._last_detected_timestamp_ms == -1:
            return False
        return (self._last_frame_timestamp_ms - self._last_detected_timestamp_ms) <= 1500

    @property
    def last_latency_ms(self) -> int | None:
        """Devuelve la latencia del último intento resuelto."""
        return self._latencies[-1] if self._latencies else None

    def update(self, frame: GestureFrame) -> None:
        """Actualiza conteos, distancia recorrida y detecta métricas conductuales."""
        self._frames_processed += 1
        self._last_frame_timestamp_ms = frame.timestamp_ms
        if frame.hands:
            self._frames_with_hands += 1

        # Resolver intento de imitación pendiente
        if self._pending_attempt_start is not None:
            for hand in frame.hands:
                # Si realiza algún gesto intencional reconocido
                if hand.gesture not in ("None", "Unrecognized", "") and hand.gesture_score > 0.5:
                    latency = frame.timestamp_ms - self._pending_attempt_start
                    self._latencies.append(latency)
                    self._attempt_gestures.append(hand.gesture)
                    self._pending_attempt_start = None
                    break

        for hand in frame.hands:
            self._gesture_counts[hand.gesture] += 1

            # Filtrar y contar gestos de relevancia social
            if hand.gesture in self._social_gestures:
                self._social_gesture_counts[hand.gesture] += 1

            current_wrist = (hand.wrist.x, hand.wrist.y)
            previous_wrist = self._previous_wrists.get(hand.side)
            if previous_wrist is not None:
                self._wrist_distance[hand.side] += hypot(
                    current_wrist[0] - previous_wrist[0],
                    current_wrist[1] - previous_wrist[1],
                )
            self._previous_wrists[hand.side] = current_wrist

            # Evaluar y registrar estereotipias motoras
            if self._detect_stereotypy(hand.side, frame.timestamp_ms, hand.wrist):
                self._stereotypy_count_by_side[hand.side] += 1
                self._last_detected_timestamp_ms = frame.timestamp_ms
                self._last_stereotypy_side = hand.side

    def _detect_stereotypy(self, side: str, timestamp_ms: int, wrist: LandmarkPoint) -> bool:
        """Algoritmo en línea para detectar oscilaciones motoras rápidas y repetitivas."""
        if side not in self._history:
            self._history[side] = []

        self._history[side].append((timestamp_ms, wrist.x, wrist.y))

        # Filtrar historial para mantener solo los últimos 1500 ms
        self._history[side] = [pt for pt in self._history[side] if timestamp_ms - pt[0] <= 1500]

        history = self._history[side]
        if len(history) < 15:
            return False

        total_path = 0.0
        sign_changes_x = 0
        sign_changes_y = 0

        prev_pt = history[0]
        dx_list = []
        dy_list = []

        for pt in history[1:]:
            dist = hypot(pt[1] - prev_pt[1], pt[2] - prev_pt[2])
            total_path += dist
            dx_list.append(pt[1] - prev_pt[1])
            dy_list.append(pt[2] - prev_pt[2])
            prev_pt = pt

        first_pt = history[0]
        last_pt = history[-1]
        net_displacement = hypot(last_pt[1] - first_pt[1], last_pt[2] - first_pt[2])

        # Contar cambios en la dirección del movimiento
        for i in range(len(dx_list) - 1):
            if dx_list[i] * dx_list[i + 1] < 0 and abs(dx_list[i]) > 0.002:
                sign_changes_x += 1
            if dy_list[i] * dy_list[i + 1] < 0 and abs(dy_list[i]) > 0.002:
                sign_changes_y += 1

        duration_sec = (last_pt[0] - first_pt[0]) / 1000.0
        if duration_sec <= 0:
            return False

        avg_speed = total_path / duration_sec

        # Criterio clínico de aleteo (estereotipia):
        # 1. Velocidad promedio de muñeca alta (> 0.4 de la pantalla por segundo)
        # 2. Trayectoria total recorrida significativa (> 0.15) para evitar ruido estático
        # 3. Trayectoria total mucho mayor que el desplazamiento neto (oscila sobre el mismo eje)
        # 4. Frecuencia de cambio de dirección alta (mínimo 5 cambios)
        is_oscillating = (
            avg_speed > 0.4 and
            total_path > 0.15 and
            (total_path / (net_displacement + 0.01)) > 4.0 and
            (sign_changes_x + sign_changes_y) >= 5
        )

        if is_oscillating:
            last_event = self._last_stereotypy_time.get(side, 0)
            # Evitar registrar múltiples eventos de la misma estereotipia en menos de 2 segundos
            if timestamp_ms - last_event > 2000:
                self._last_stereotypy_time[side] = timestamp_ms
                return True

        return False

    def summary(self) -> dict[str, Any]:
        """Devuelve métricas agregadas enriquecidas con indicadores de ADOS-2."""
        detection_rate = 0.0
        if self._frames_processed:
            detection_rate = self._frames_with_hands / self._frames_processed

        avg_latency = 0.0
        if self._latencies:
            avg_latency = sum(self._latencies) / len(self._latencies)

        return {
            "frames_processed": self._frames_processed,
            "frames_with_hands": self._frames_with_hands,
            "hand_detection_rate": round(detection_rate, 4),
            "gesture_counts": dict(self._gesture_counts),
            "wrist_distance_normalized": {
                side: round(distance, 4)
                for side, distance in self._wrist_distance.items()
            },
            # Indicadores inspirados en ADOS-2
            "stereotypy_counts": dict(self._stereotypy_count_by_side),
            "total_stereotypy_events": sum(self._stereotypy_count_by_side.values()),
            "social_gesture_counts": dict(self._social_gesture_counts),
            "imitation_attempts_count": len(self._latencies) + (1 if self._pending_attempt_start is not None else 0),
            "resolved_attempts_count": len(self._latencies),
            "average_latency_ms": round(avg_latency, 2),
            "latencies_list_ms": self._latencies,
            "resolved_gestures": self._attempt_gestures,
        }
