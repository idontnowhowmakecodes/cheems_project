"""
Acumulador de Métricas por Sesión/Ítem para CHEEMS.

Mantiene dos niveles de buffer:
  1. sliding_window  — últimos N frames para estimado en tiempo real (UI en vivo)
  2. item_buffer     — TODOS los frames desde inicio del ítem (juicio final preciso)

La separación garantiza que la sugerencia en vivo pueda oscilar libremente sin
contaminar la estadística final, que se calcula solo cuando el especialista
pulsa "Finalizar Actividad".
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Dict, List, Optional


# Tamaño de la ventana deslizante para el estimado en tiempo real
SLIDING_WINDOW_FRAMES = 90   # ≈ 3 segundos a 30 fps


class MetricsAccumulator:
    """
    Acumulador de métricas biométricas con doble buffer.

    Uso típico:
        acc = MetricsAccumulator()
        # En cada frame:
        acc.push_frame(processed_frame.to_flat_metrics())
        estimate = acc.get_realtime_estimate()   # → UI en vivo
        # Al finalizar el ítem:
        final = acc.get_final_stats()            # → AISuggestionEngine final
        acc.reset_item()                         # → preparar siguiente ítem
    """

    def __init__(self, sliding_window: int = SLIDING_WINDOW_FRAMES) -> None:
        self._sliding: deque[Dict[str, float]] = deque(maxlen=sliding_window)
        self._item_buffer: List[Dict[str, float]] = []
        self._item_start_time: float = time.time()
        self._frame_count_total: int = 0

    # ─────────────────────────── Ingesta ─────────────────────────────────
    def push_frame(self, metrics: Dict[str, float]) -> None:
        """Agrega métricas de un frame a ambos buffers."""
        self._sliding.append(metrics)
        self._item_buffer.append(metrics)
        self._frame_count_total += 1

    # ─────────────────────────── Estimado en vivo ────────────────────────
    def get_realtime_estimate(self) -> Dict[str, float]:
        """
        Retorna el promedio de los últimos N frames (ventana deslizante).
        
        Propósito: mostrar en la UI durante la evaluación como "estimado".
        Puede fluctuar — no debe usarse para decisiones clínicas.
        """
        if not self._sliding:
            return {}
        return self._compute_averages(list(self._sliding))

    # ─────────────────────────── Juicio Final ────────────────────────────
    def get_final_stats(self) -> Dict[str, Any]:
        """
        Calcula estadísticas completas de TODO el ítem (desde reset_item()).

        Incluye: media, desviación estándar, máximo, percentil 75,
        y métricas clínicas derivadas como attention_duration_pct.

        Propósito: base para el veredicto definitivo de la IA.
        """
        if not self._item_buffer:
            return self._empty_stats()

        buf = self._item_buffer
        n = len(buf)
        elapsed = time.time() - self._item_start_time

        # Extraer todas las claves presentes
        all_keys = set(k for frame in buf for k in frame)

        stats: Dict[str, Any] = {
            "frame_count": n,
            "duration_seconds": round(elapsed, 2),
        }

        for key in all_keys:
            values = [frame.get(key, 0.0) for frame in buf]
            mean_v = sum(values) / n
            variance = sum((v - mean_v) ** 2 for v in values) / n
            std_v = math.sqrt(variance)
            max_v = max(values)
            sorted_v = sorted(values)
            p75 = sorted_v[int(0.75 * n)]

            stats[f"{key}_mean"] = round(mean_v, 4)
            stats[f"{key}_std"]  = round(std_v, 4)
            stats[f"{key}_max"]  = round(max_v, 4)
            stats[f"{key}_p75"]  = round(p75, 4)

        # ── Métricas clínicas derivadas (proporciones de tiempo) ──────────
        # Porcentaje del tiempo que el paciente mantuvo atención visual
        attn_frames = sum(1 for frame in buf if frame.get("attention_on", 0.0) > 0.5)
        stats["attention_duration_pct"] = round(attn_frames / n, 4)

        # Porcentaje del tiempo con flapping detectado
        flap_frames = sum(1 for frame in buf if frame.get("flapping_detected", 0.0) > 0.3)
        stats["flapping_duration_pct"] = round(flap_frames / n, 4)

        # Frecuencia media de flapping (solo cuando está activo)
        flap_freqs = [frame.get("flapping_freq_hz", 0.0) for frame in buf if frame.get("flapping_detected", 0.0) > 0.3]
        stats["flapping_freq_mean_hz"] = round(sum(flap_freqs) / len(flap_freqs), 2) if flap_freqs else 0.0

        # Porcentaje del tiempo con rocking detectado
        rock_frames = sum(1 for frame in buf if frame.get("rocking_detected", 0.0) > 0.3)
        stats["rocking_duration_pct"] = round(rock_frames / n, 4)

        # Señalamiento: max en toda la sesión
        stats["pointing_peak"] = round(max(frame.get("pointing_score", 0.0) for frame in buf), 4)

        # Hands detected ratio (frames con manos visibles)
        hands_frames = sum(1 for frame in buf if frame.get("hand_count", 0.0) >= 1.0)
        stats["hands_visible_pct"] = round(hands_frames / n, 4)

        return stats

    # ─────────────────────────── Control de Estado ───────────────────────
    def reset_item(self) -> None:
        """
        Reinicia el buffer del ítem para la siguiente actividad.
        Preserva la ventana deslizante (se reinicia sola por deque).
        """
        self._item_buffer.clear()
        self._item_start_time = time.time()
        self._sliding.clear()

    def frame_count(self) -> int:
        """Número de frames acumulados en el ítem actual."""
        return len(self._item_buffer)

    def duration_seconds(self) -> float:
        """Segundos transcurridos desde el inicio del ítem."""
        return round(time.time() - self._item_start_time, 2)

    # ─────────────────────────── Helpers ─────────────────────────────────
    @staticmethod
    def _compute_averages(frames: List[Dict[str, float]]) -> Dict[str, float]:
        if not frames:
            return {}
        n = len(frames)
        all_keys = set(k for f in frames for k in f)
        return {
            key: round(sum(f.get(key, 0.0) for f in frames) / n, 4)
            for key in all_keys
        }

    @staticmethod
    def _empty_stats() -> Dict[str, Any]:
        return {
            "frame_count": 0,
            "duration_seconds": 0.0,
            "attention_duration_pct": 0.0,
            "flapping_duration_pct": 0.0,
            "flapping_freq_mean_hz": 0.0,
            "rocking_duration_pct": 0.0,
            "pointing_peak": 0.0,
            "hands_visible_pct": 0.0,
        }
